import json
import csv
import time
from collections import Counter
from datetime import datetime, UTC
from pathlib import Path

from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

try:
    from .inference import DEFAULT_MODEL_NAME, create_client, predict_damage
    from .labeling import LABEL_ORDER, is_valid_damage_label, overall_label_from_target_mask
    from .paths import resolve_manifest_path
except ImportError:
    from inference import DEFAULT_MODEL_NAME, create_client, predict_damage
    from labeling import LABEL_ORDER, is_valid_damage_label, overall_label_from_target_mask
    from paths import resolve_manifest_path

REQUIRED_COLUMNS = {"core_id", "pre_image", "post_image", "target_mask"}


def _validate_manifest(manifest_path: Path) -> list[dict]:
    manifest_path = Path(manifest_path)
    if not manifest_path.exists():
        raise RuntimeError(f"Manifest file not found: {manifest_path}")

    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        return []

    missing_columns = REQUIRED_COLUMNS.difference(rows[0].keys())
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise RuntimeError(f"Manifest missing required columns: {missing}")
    return rows


def _safe_bool_match(ground_truth_label: str, predicted_label: str | None) -> bool | None:
    if not is_valid_damage_label(ground_truth_label) or not is_valid_damage_label(predicted_label):
        return None
    return ground_truth_label == predicted_label


def _compute_metrics(scored_rows: list[dict]) -> dict:
    if not scored_rows:
        empty_per_class = {
            label: {"precision": None, "recall": None, "f1": None, "support": 0}
            for label in LABEL_ORDER
        }
        return {
            "accuracy": None,
            "macro_precision": None,
            "macro_recall": None,
            "macro_f1": None,
            "per_class": empty_per_class,
            "confusion_matrix": [[0 for _ in LABEL_ORDER] for _ in LABEL_ORDER],
        }

    y_true = [row["ground_truth_label"] for row in scored_rows]
    y_pred = [row["predicted_label"] for row in scored_rows]

    precision, recall, f1, support = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=LABEL_ORDER,
        average=None,
        zero_division=0,
    )
    macro_precision, macro_recall, macro_f1, _ = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=LABEL_ORDER,
        average="macro",
        zero_division=0,
    )
    matrix = confusion_matrix(y_true, y_pred, labels=LABEL_ORDER)

    per_class = {}
    for idx, label in enumerate(LABEL_ORDER):
        per_class[label] = {
            "precision": float(precision[idx]),
            "recall": float(recall[idx]),
            "f1": float(f1[idx]),
            "support": int(support[idx]),
        }

    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_precision": float(macro_precision),
        "macro_recall": float(macro_recall),
        "macro_f1": float(macro_f1),
        "per_class": per_class,
        "confusion_matrix": matrix.tolist(),
    }


def _build_summary(results: list[dict], manifest_path: Path, model_used: str | None) -> dict:
    scored_rows = [row for row in results if row["included_in_metrics"] is True]
    metrics = _compute_metrics(scored_rows)

    mismatch_counter = Counter()
    for row in scored_rows:
        if row["match"] is False:
            mismatch_counter[(row["ground_truth_label"], row["predicted_label"])] += 1

    summary = {
        "manifest_path": str(manifest_path),
        "model_used": model_used,
        "label_order": LABEL_ORDER,
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "num_rows_total": int(len(results)),
        "num_rows_scored": int(len(scored_rows)),
        "num_rows_prediction_error": int(sum(bool(row["error"]) for row in results)),
        "num_rows_invalid_prediction": int(sum(row["predicted_label_valid"] is False for row in results)),
        "num_rows_unknown_ground_truth": int(sum(row["ground_truth_label"] == "unknown" for row in results)),
        "most_common_error_pairs": [
            {"ground_truth": gt, "predicted": pred, "count": count}
            for (gt, pred), count in mismatch_counter.most_common(10)
        ],
    }
    summary.update(metrics)
    return summary


def _format_metric(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def print_summary(metrics: dict) -> None:
    print("\nEvaluation summary")
    print(f"  manifest_path               : {metrics['manifest_path']}")
    print(f"  model_used                  : {metrics['model_used']}")
    print(f"  num_rows_total              : {metrics['num_rows_total']}")
    print(f"  num_rows_scored             : {metrics['num_rows_scored']}")
    print(f"  num_rows_unknown_ground_truth: {metrics['num_rows_unknown_ground_truth']}")
    print(f"  num_rows_invalid_prediction : {metrics['num_rows_invalid_prediction']}")
    print(f"  num_rows_prediction_error   : {metrics['num_rows_prediction_error']}")
    print(f"  accuracy                    : {_format_metric(metrics['accuracy'])}")
    print(f"  macro_precision             : {_format_metric(metrics['macro_precision'])}")
    print(f"  macro_recall                : {_format_metric(metrics['macro_recall'])}")
    print(f"  macro_f1                    : {_format_metric(metrics['macro_f1'])}")

    print("\nConfusion matrix")
    print("  labels:", ", ".join(metrics["label_order"]))
    for label, row in zip(metrics["label_order"], metrics["confusion_matrix"]):
        print(f"  {label:12s} {row}")

    print("\nMost common error pairs")
    if not metrics["most_common_error_pairs"]:
        print("  none")
    else:
        for item in metrics["most_common_error_pairs"]:
            print(
                f"  {item['ground_truth']} -> {item['predicted']}: {item['count']}"
            )


def evaluate_manifest(
    manifest_path: Path,
    output_csv: Path,
    preferred_model: str = DEFAULT_MODEL_NAME,
    limit: int | None = None,
    row_offset: int = 0,
    fail_fast: bool = False,
    sleep_seconds: float = 0.0,
) -> tuple[list[dict], dict]:
    manifest_path = Path(manifest_path)
    output_csv = Path(output_csv)
    metrics_path = output_csv.with_name(f"{output_csv.stem}_metrics.json")

    rows = _validate_manifest(manifest_path)
    if row_offset:
        rows = rows[row_offset:]
    if limit is not None:
        rows = rows[:limit]

    client = create_client()
    results = []
    model_used = None

    for index, row in enumerate(rows):
        core_id = row["core_id"]
        pre_path = resolve_manifest_path(row["pre_image"])
        post_path = resolve_manifest_path(row["post_image"])
        target_mask = resolve_manifest_path(row["target_mask"])

        ground_truth_label = "unknown"
        row_error = None

        if not pre_path.exists():
            row_error = f"missing_pre_image: {pre_path}"
        elif not post_path.exists():
            row_error = f"missing_post_image: {post_path}"
        elif not target_mask.exists():
            row_error = f"missing_target_mask: {target_mask}"
        else:
            ground_truth_label = overall_label_from_target_mask(target_mask)

        prediction = {
            "label": None,
            "reason": None,
            "raw_text": "",
            "normalized_text": "",
            "model_used": None,
            "parse_ok": False,
            "error": None,
        }

        if row_error is None:
            prediction = predict_damage(
                pre_path=pre_path,
                post_path=post_path,
                preferred_model=preferred_model,
                client=client,
            )
            model_used = prediction.get("model_used") or model_used

        error_text = row_error or prediction.get("error")
        predicted_label = prediction.get("label")
        ground_truth_valid = is_valid_damage_label(ground_truth_label)
        predicted_label_valid = is_valid_damage_label(predicted_label)
        included_in_metrics = ground_truth_valid and predicted_label_valid

        results.append(
            {
                "core_id": core_id,
                "ground_truth_label": ground_truth_label,
                "predicted_label": predicted_label,
                "match": _safe_bool_match(ground_truth_label, predicted_label),
                "reason": prediction.get("reason"),
                "parse_ok": prediction.get("parse_ok", False),
                "error": error_text,
                "included_in_metrics": included_in_metrics,
                "model_used": prediction.get("model_used"),
                "pre_image": str(pre_path),
                "post_image": str(post_path),
                "target_mask": str(target_mask),
                "raw_response": prediction.get("raw_text", ""),
                "predicted_label_valid": predicted_label_valid,
            }
        )

        print(
            f"[{index + 1}/{len(rows)}] {core_id} "
            f"gt={ground_truth_label} pred={predicted_label} "
            f"status={'scored' if included_in_metrics else 'skipped'}"
        )

        if error_text and fail_fast:
            raise RuntimeError(f"Fail-fast triggered on {core_id}: {error_text}")

        if sleep_seconds > 0 and index < len(rows) - 1:
            time.sleep(sleep_seconds)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "core_id",
        "ground_truth_label",
        "predicted_label",
        "match",
        "reason",
        "parse_ok",
        "error",
        "included_in_metrics",
        "model_used",
        "pre_image",
        "post_image",
        "target_mask",
        "raw_response",
        "predicted_label_valid",
    ]
    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    metrics = _build_summary(results, manifest_path, model_used)
    with metrics_path.open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2)

    print_summary(metrics)
    print(f"\nSaved results CSV: {output_csv}")
    print(f"Saved metrics JSON: {metrics_path}")
    return results, metrics
