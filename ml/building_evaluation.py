import csv
import json
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

try:
    from .building_data import DEFAULT_LABELS_DIR, crop_building_pair, load_building_records
    from .inference import (
        BUILDING_SYSTEM_PROMPT,
        DEFAULT_MODEL_NAME,
        create_client,
        pil_image_to_png_bytes,
        predict_damage_bytes,
    )
    from .labeling import LABEL_ORDER, is_valid_damage_label
except ImportError:
    from building_data import DEFAULT_LABELS_DIR, crop_building_pair, load_building_records
    from inference import (
        BUILDING_SYSTEM_PROMPT,
        DEFAULT_MODEL_NAME,
        create_client,
        pil_image_to_png_bytes,
        predict_damage_bytes,
    )
    from labeling import LABEL_ORDER, is_valid_damage_label

DEFAULT_BUILDING_MODEL_NAME = "gemini-2.0-flash-lite"
MODEL_RPM_LIMITS = {
    "gemini-2.5-flash": 8,
    "gemini-2.0-flash": 12,
    "gemini-2.0-flash-lite": 24,
}

BUILDING_RESULT_FIELDNAMES = [
    "core_id",
    "building_uid",
    "ground_truth_label",
    "predicted_label",
    "match",
    "reason",
    "parse_ok",
    "error",
    "included_in_metrics",
    "model_used",
    "label_json_path",
    "pre_image",
    "post_image",
    "polygon_wkt",
    "crop_bbox",
    "raw_response",
    "predicted_label_valid",
    "batch_job_name",
    "request_id",
    "batch_status",
]


def _safe_bool_match(ground_truth_label: str | None, predicted_label: str | None) -> bool | None:
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
        "num_buildings_total": int(len(results)),
        "num_buildings_scored": int(len(scored_rows)),
        "num_buildings_prediction_error": int(sum(bool(row["error"]) for row in results)),
        "num_buildings_invalid_prediction": int(sum(row["predicted_label_valid"] is False for row in results)),
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
    print("\nBuilding evaluation summary")
    print(f"  manifest_path               : {metrics['manifest_path']}")
    print(f"  model_used                  : {metrics['model_used']}")
    print(f"  num_buildings_total         : {metrics['num_buildings_total']}")
    print(f"  num_buildings_scored        : {metrics['num_buildings_scored']}")
    print(f"  num_buildings_invalid_prediction : {metrics['num_buildings_invalid_prediction']}")
    print(f"  num_buildings_prediction_error   : {metrics['num_buildings_prediction_error']}")
    print(f"  accuracy                    : {_format_metric(metrics['accuracy'])}")
    print(f"  macro_precision             : {_format_metric(metrics['macro_precision'])}")
    print(f"  macro_recall                : {_format_metric(metrics['macro_recall'])}")
    print(f"  macro_f1                    : {_format_metric(metrics['macro_f1'])}")

    print("\nConfusion matrix")
    print("  labels:", ", ".join(metrics["label_order"]))
    for label, row in zip(metrics["label_order"], metrics["confusion_matrix"]):
        print(f"  {label:12s} {row}")


def _load_existing_results(output_csv: Path) -> list[dict]:
    if not output_csv.exists():
        return []
    with output_csv.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes"}


def _is_retryable_error(error_text: str | None) -> bool:
    error_text = (error_text or "").lower()
    if not error_text:
        return False
    retryable_markers = (
        "429",
        "resource_exhausted",
        "quota",
        "retrydelay",
        "temporarily unavailable",
        "connection reset",
        "timeout",
        "timed out",
        "network",
        "service unavailable",
        "internal server error",
        "bad gateway",
    )
    return any(marker in error_text for marker in retryable_markers)


def _is_deterministic_local_error(error_text: str | None) -> bool:
    error_text = (error_text or "").lower()
    if not error_text:
        return False
    deterministic_markers = (
        "missing_label_json:",
        "missing_pre_image:",
        "missing_post_image:",
        "invalid_crop_bounds",
        "missing_manifest",
    )
    return any(marker in error_text for marker in deterministic_markers)


def _row_is_terminal(row: dict) -> bool:
    predicted_label = row.get("predicted_label")
    if is_valid_damage_label(predicted_label):
        return True

    error_text = row.get("error")
    if _is_retryable_error(error_text):
        return False

    if _is_deterministic_local_error(error_text):
        return True

    parse_ok = _parse_bool(row.get("parse_ok"))
    predicted_label_valid = _parse_bool(row.get("predicted_label_valid"))
    if parse_ok and not predicted_label_valid:
        return True

    return False


def _completed_keys(existing_rows: list[dict]) -> set[tuple[str, str]]:
    completed = set()
    for row in existing_rows:
        core_id = row.get("core_id")
        building_uid = row.get("building_uid")
        if core_id and building_uid and _row_is_terminal(row):
            completed.add((core_id, building_uid))
    return completed


def _minimum_interval_seconds(preferred_model: str) -> float:
    rpm = MODEL_RPM_LIMITS.get(preferred_model)
    if not rpm:
        return 0.0
    return 60.0 / rpm


def _maybe_wait_for_rate_limit(last_request_started_at: float | None, preferred_model: str) -> float:
    minimum_interval = _minimum_interval_seconds(preferred_model)
    if minimum_interval <= 0 or last_request_started_at is None:
        return time.monotonic()

    elapsed = time.monotonic() - last_request_started_at
    remaining = minimum_interval - elapsed
    if remaining > 0:
        time.sleep(remaining)
    return time.monotonic()


def build_building_result_row(
    record: dict,
    prediction: dict,
    bbox: tuple[int, int, int, int] | None,
    error_text: str | None,
    batch_job_name: str | None = None,
    request_id: str | None = None,
    batch_status: str | None = None,
) -> dict:
    predicted_label = prediction.get("label")
    ground_truth_label = record.get("ground_truth_label")
    included_in_metrics = is_valid_damage_label(ground_truth_label) and is_valid_damage_label(predicted_label)
    return {
        "core_id": record["core_id"],
        "building_uid": record.get("building_uid"),
        "ground_truth_label": ground_truth_label,
        "predicted_label": predicted_label,
        "match": _safe_bool_match(ground_truth_label, predicted_label),
        "reason": prediction.get("reason"),
        "parse_ok": prediction.get("parse_ok", False),
        "error": error_text,
        "included_in_metrics": included_in_metrics,
        "model_used": prediction.get("model_used"),
        "label_json_path": str(record.get("label_json_path")),
        "pre_image": str(record["pre_path"]),
        "post_image": str(record["post_path"]),
        "polygon_wkt": record.get("polygon_wkt"),
        "crop_bbox": "" if bbox is None else ",".join(str(value) for value in bbox),
        "raw_response": prediction.get("raw_text", ""),
        "predicted_label_valid": is_valid_damage_label(predicted_label),
        "batch_job_name": batch_job_name,
        "request_id": request_id,
        "batch_status": batch_status,
    }


def evaluate_buildings(
    manifest_path: Path,
    output_csv: Path,
    preferred_model: str = DEFAULT_BUILDING_MODEL_NAME,
    labels_dir: Path = DEFAULT_LABELS_DIR,
    limit_images: int | None = None,
    limit_buildings: int | None = None,
    padding: int = 16,
    fail_fast: bool = False,
    sleep_seconds: float = 0.0,
    resume: bool = True,
) -> tuple[list[dict], dict]:
    manifest_path = Path(manifest_path)
    output_csv = Path(output_csv)
    metrics_path = output_csv.with_name(f"{output_csv.stem}_metrics.json")
    image_records = load_building_records(manifest_path, labels_dir=labels_dir)
    if limit_images is not None:
        allowed_core_ids = []
        seen = set()
        for record in image_records:
            core_id = record["core_id"]
            if core_id not in seen:
                seen.add(core_id)
                allowed_core_ids.append(core_id)
            if len(allowed_core_ids) >= limit_images:
                break
        allowed_core_ids = set(allowed_core_ids)
        image_records = [record for record in image_records if record["core_id"] in allowed_core_ids]
    if limit_buildings is not None:
        image_records = image_records[:limit_buildings]

    existing_rows = _load_existing_results(output_csv) if resume else []
    completed_keys = _completed_keys(existing_rows)
    pending_records = [
        record
        for record in image_records
        if (record["core_id"], str(record.get("building_uid"))) not in completed_keys
    ]

    client = create_client()
    model_used = None
    results = list(existing_rows)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    last_request_started_at = None
    processed_this_run = 0
    scored_this_run = 0
    errored_this_run = 0
    skipped_from_resume = len(image_records) - len(pending_records)

    if skipped_from_resume:
        print(f"Resuming run: skipping {skipped_from_resume} previously completed buildings")

    write_mode = "a" if resume and output_csv.exists() and existing_rows else "w"
    with output_csv.open(write_mode, encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=BUILDING_RESULT_FIELDNAMES)
        if write_mode == "w":
            writer.writeheader()

        for index, record in enumerate(pending_records):
            prediction = {
                "label": None,
                "reason": None,
                "raw_text": "",
                "model_used": None,
                "parse_ok": False,
                "error": None,
            }
            bbox = None
            error_text = record.get("error")

            if error_text is None:
                try:
                    last_request_started_at = _maybe_wait_for_rate_limit(
                        last_request_started_at,
                        preferred_model,
                    )
                    pre_crop, post_crop, bbox = crop_building_pair(
                        pre_path=record["pre_path"],
                        post_path=record["post_path"],
                        polygon_wkt=record["polygon_wkt"],
                        padding=padding,
                    )
                    prediction = predict_damage_bytes(
                        pre_bytes=pil_image_to_png_bytes(pre_crop),
                        post_bytes=pil_image_to_png_bytes(post_crop),
                        preferred_model=preferred_model,
                        client=client,
                        system_prompt=BUILDING_SYSTEM_PROMPT,
                    )
                    model_used = prediction.get("model_used") or model_used
                except Exception as exc:
                    error_text = str(exc)

            error_text = error_text or prediction.get("error")
            result_row = build_building_result_row(record, prediction, bbox, error_text)
            results.append(result_row)
            writer.writerow(result_row)
            handle.flush()
            processed_this_run += 1
            if result_row["included_in_metrics"]:
                scored_this_run += 1
            if error_text:
                errored_this_run += 1

            print(
                f"[{index + 1}/{len(pending_records)}] {record['core_id']}:{record.get('building_uid')} "
                f"gt={result_row['ground_truth_label']} pred={result_row['predicted_label']} "
                f"status={'scored' if result_row['included_in_metrics'] else 'skipped'}"
            )

            if processed_this_run % 10 == 0:
                print(
                    "Progress:"
                    f" processed_this_run={processed_this_run}"
                    f" scored_this_run={scored_this_run}"
                    f" errored_this_run={errored_this_run}"
                    f" skipped_from_resume={skipped_from_resume}"
                )

            if error_text and fail_fast:
                raise RuntimeError(
                    f"Fail-fast triggered on {record['core_id']}:{record.get('building_uid')}: {error_text}"
                )

            if sleep_seconds > 0 and index < len(pending_records) - 1:
                time.sleep(sleep_seconds)

    metrics = _build_summary(results, manifest_path, model_used)
    with metrics_path.open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2)

    print_summary(metrics)
    print(f"\nSaved results CSV: {output_csv}")
    print(f"Saved metrics JSON: {metrics_path}")
    return results, metrics
