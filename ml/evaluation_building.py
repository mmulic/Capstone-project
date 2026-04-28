"""Per-building crop evaluation pipeline.

For each post-disaster label JSON in labels_dir:
  - Load building polygons from features.xy (pixel coordinates)
  - Crop each building from the pre and post disaster images
  - Send the crop pair to Gemini for per-building damage prediction
  - Compare prediction against the ground truth subtype from the label JSON
  - Write per-building results to CSV and aggregated metrics to JSON
"""

from __future__ import annotations

import csv
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

try:
    from .cropping import crop_building
    from .inference import DEFAULT_MODEL_NAME, create_client
    from .inference_building import predict_building_damage
    from .labeling import LABEL_ORDER, SUBTYPE_TO_LABEL, is_valid_damage_label
except ImportError:
    from cropping import crop_building
    from inference import DEFAULT_MODEL_NAME, create_client
    from inference_building import predict_building_damage
    from labeling import LABEL_ORDER, SUBTYPE_TO_LABEL, is_valid_damage_label

IMAGES_DIR = Path(__file__).resolve().parent / "data" / "test" / "images"
LABELS_DIR = Path(__file__).resolve().parent / "data" / "test" / "labels"


def _load_buildings(label_json: Path) -> list[dict]:
    """Return list of building dicts with keys: uid, wkt, ground_truth_label."""
    data = json.loads(label_json.read_text(encoding="utf-8"))
    xy_features = data.get("features", {}).get("xy", [])
    buildings = []
    for feature in xy_features:
        props = feature.get("properties", {})
        uid = props.get("uid", "")
        subtype = props.get("subtype", "")
        label = SUBTYPE_TO_LABEL.get(subtype)  # None if not a damage subtype
        wkt = feature.get("wkt", "")
        if wkt and label:
            buildings.append({"uid": uid, "wkt": wkt, "ground_truth_label": label})
    return buildings


def _safe_bool_match(ground_truth: str, predicted: str | None) -> bool | None:
    if not is_valid_damage_label(ground_truth) or not is_valid_damage_label(predicted):
        return None
    return ground_truth == predicted


def _compute_metrics(scored_rows: list[dict]) -> dict:
    if not scored_rows:
        empty = {label: {"precision": None, "recall": None, "f1": None, "support": 0} for label in LABEL_ORDER}
        return {
            "accuracy": None,
            "macro_precision": None,
            "macro_recall": None,
            "macro_f1": None,
            "per_class": empty,
            "confusion_matrix": [[0] * len(LABEL_ORDER) for _ in LABEL_ORDER],
        }

    y_true = [r["ground_truth_label"] for r in scored_rows]
    y_pred = [r["predicted_label"] for r in scored_rows]

    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=LABEL_ORDER, average=None, zero_division=0
    )
    macro_p, macro_r, macro_f, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=LABEL_ORDER, average="macro", zero_division=0
    )
    matrix = confusion_matrix(y_true, y_pred, labels=LABEL_ORDER)

    per_class = {
        label: {
            "precision": float(precision[i]),
            "recall": float(recall[i]),
            "f1": float(f1[i]),
            "support": int(support[i]),
        }
        for i, label in enumerate(LABEL_ORDER)
    }
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_precision": float(macro_p),
        "macro_recall": float(macro_r),
        "macro_f1": float(macro_f),
        "per_class": per_class,
        "confusion_matrix": matrix.tolist(),
    }


def _build_summary(results: list[dict], model_used: str | None) -> dict:
    scored = [r for r in results if r["included_in_metrics"]]
    metrics = _compute_metrics(scored)

    mismatch_counter: Counter = Counter()
    for r in scored:
        if r["match"] is False:
            mismatch_counter[(r["ground_truth_label"], r["predicted_label"])] += 1

    summary = {
        "model_used": model_used,
        "label_order": LABEL_ORDER,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "num_buildings_total": len(results),
        "num_buildings_scored": len(scored),
        "num_buildings_error": sum(bool(r["error"]) for r in results),
        "num_buildings_invalid_prediction": sum(not r["predicted_label_valid"] for r in results),
        "most_common_error_pairs": [
            {"ground_truth": gt, "predicted": pred, "count": count}
            for (gt, pred), count in mismatch_counter.most_common(10)
        ],
    }
    summary.update(metrics)
    return summary


def _format_metric(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.4f}"


def print_summary(metrics: dict) -> None:
    print("\nBuilding-level evaluation summary")
    print(f"  model_used                    : {metrics['model_used']}")
    print(f"  num_buildings_total           : {metrics['num_buildings_total']}")
    print(f"  num_buildings_scored          : {metrics['num_buildings_scored']}")
    print(f"  num_buildings_error           : {metrics['num_buildings_error']}")
    print(f"  num_buildings_invalid_pred    : {metrics['num_buildings_invalid_prediction']}")
    print(f"  accuracy                      : {_format_metric(metrics['accuracy'])}")
    print(f"  macro_precision               : {_format_metric(metrics['macro_precision'])}")
    print(f"  macro_recall                  : {_format_metric(metrics['macro_recall'])}")
    print(f"  macro_f1                      : {_format_metric(metrics['macro_f1'])}")
    print("\nConfusion matrix")
    print("  labels:", ", ".join(metrics["label_order"]))
    for label, row in zip(metrics["label_order"], metrics["confusion_matrix"]):
        print(f"  {label:12s} {row}")
    print("\nMost common error pairs")
    for item in metrics.get("most_common_error_pairs") or []:
        print(f"  {item['ground_truth']} -> {item['predicted']}: {item['count']}")


def evaluate_building_crops(
    labels_dir: Path = LABELS_DIR,
    images_dir: Path = IMAGES_DIR,
    output_csv: Path | None = None,
    preferred_model: str = DEFAULT_MODEL_NAME,
    limit: int | None = None,
    sleep_seconds: float = 0.0,
    disaster_filter: str | None = None,
    crop_padding: int = 16,
    fail_fast: bool = False,
) -> tuple[list[dict], dict]:
    """Evaluate Gemini per-building damage predictions against xBD ground-truth labels.

    Iterates all post-disaster label JSONs in labels_dir, crops each annotated
    building polygon from the matching image pair, and calls Gemini for a
    per-building damage assessment.

    Args:
        labels_dir: Directory containing xBD label JSON files.
        images_dir: Directory containing pre/post disaster PNG images.
        output_csv: Path to write per-building results CSV (and _metrics.json alongside it).
        preferred_model: Gemini model name.
        limit: Stop after this many buildings (None = all).
        sleep_seconds: Seconds to sleep between Gemini calls (rate limiting).
        disaster_filter: If set, only process JSONs whose filename starts with this string.
        crop_padding: Pixel padding added around each building bounding box.
        fail_fast: Raise on first error.
    """
    labels_dir = Path(labels_dir)
    images_dir = Path(images_dir)

    if output_csv is None:
        output_csv = Path(__file__).resolve().parent / "results" / "building_eval_results.csv"
    output_csv = Path(output_csv)
    metrics_path = output_csv.with_name(f"{output_csv.stem}_metrics.json")

    # Collect all post-disaster label JSONs
    all_jsons = sorted(labels_dir.glob("*_post_disaster.json"))
    if disaster_filter:
        all_jsons = [p for p in all_jsons if p.name.startswith(disaster_filter)]

    create_client()
    results: list[dict] = []
    model_used: str | None = None
    total_processed = 0

    for label_json in all_jsons:
        if limit is not None and total_processed >= limit:
            break

        core_id = label_json.stem.replace("_post_disaster", "")
        pre_image_path = images_dir / f"{core_id}_pre_disaster.png"
        post_image_path = images_dir / f"{core_id}_post_disaster.png"

        if not post_image_path.exists():
            print(f"[SKIP] missing post image: {post_image_path.name}")
            continue
        if not pre_image_path.exists():
            print(f"[SKIP] missing pre image: {pre_image_path.name}")
            continue

        buildings = _load_buildings(label_json)
        if not buildings:
            continue

        for b_idx, building in enumerate(buildings):
            if limit is not None and total_processed >= limit:
                break

            uid = building["uid"]
            wkt = building["wkt"]
            ground_truth_label = building["ground_truth_label"]

            error_text = None
            prediction = {
                "label": None,
                "reason": None,
                "raw_text": "",
                "normalized_text": "",
                "model_used": None,
                "parse_ok": False,
                "error": None,
            }

            try:
                pre_crop = crop_building(pre_image_path, wkt, padding=crop_padding)
                post_crop = crop_building(post_image_path, wkt, padding=crop_padding)
            except Exception as exc:
                error_text = f"crop_error: {exc}"
                pre_crop = post_crop = None

            if error_text is None:
                prediction = predict_building_damage(
                    pre_crop=pre_crop,
                    post_crop=post_crop,
                    preferred_model=preferred_model,
                )
                model_used = prediction.get("model_used") or model_used

            error_text = error_text or prediction.get("error")
            predicted_label = prediction.get("label")
            predicted_label_valid = is_valid_damage_label(predicted_label)
            included_in_metrics = is_valid_damage_label(ground_truth_label) and predicted_label_valid

            result = {
                "core_id": core_id,
                "building_index": b_idx,
                "building_uid": uid,
                "ground_truth_label": ground_truth_label,
                "predicted_label": predicted_label,
                "match": _safe_bool_match(ground_truth_label, predicted_label),
                "reason": prediction.get("reason"),
                "parse_ok": prediction.get("parse_ok", False),
                "error": error_text,
                "included_in_metrics": included_in_metrics,
                "predicted_label_valid": predicted_label_valid,
                "model_used": prediction.get("model_used"),
                "pre_image": str(pre_image_path),
                "post_image": str(post_image_path),
                "label_json": str(label_json),
                "raw_response": prediction.get("raw_text", ""),
            }
            results.append(result)
            total_processed += 1

            status = "scored" if included_in_metrics else "skipped"
            print(
                f"[{total_processed}] {core_id} bld={b_idx} uid={uid[:8]}... "
                f"gt={ground_truth_label} pred={predicted_label} {status}"
            )

            if error_text and fail_fast:
                raise RuntimeError(f"Fail-fast on {core_id} bld={b_idx}: {error_text}")

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

    # Write CSV
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "core_id",
        "building_index",
        "building_uid",
        "ground_truth_label",
        "predicted_label",
        "match",
        "reason",
        "parse_ok",
        "error",
        "included_in_metrics",
        "predicted_label_valid",
        "model_used",
        "pre_image",
        "post_image",
        "label_json",
        "raw_response",
    ]
    with output_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    metrics = _build_summary(results, model_used)
    with metrics_path.open("w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)

    print_summary(metrics)
    print(f"\nSaved results CSV  : {output_csv}")
    print(f"Saved metrics JSON : {metrics_path}")
    return results, metrics
