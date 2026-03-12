import csv
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

try:
    from .building_data import DEFAULT_LABELS_DIR, crop_building_pair, load_building_records
    from .building_evaluation import (
        BUILDING_RESULT_FIELDNAMES,
        DEFAULT_BUILDING_MODEL_NAME,
        _build_summary,
        _completed_keys,
        _load_existing_results,
        build_building_result_row,
        print_summary,
    )
    from .inference import BUILDING_SYSTEM_PROMPT, create_client, get_api_key, parse_prediction_response, pil_image_to_png_bytes
except ImportError:
    from building_data import DEFAULT_LABELS_DIR, crop_building_pair, load_building_records
    from building_evaluation import (
        BUILDING_RESULT_FIELDNAMES,
        DEFAULT_BUILDING_MODEL_NAME,
        _build_summary,
        _completed_keys,
        _load_existing_results,
        build_building_result_row,
        print_summary,
    )
    from inference import BUILDING_SYSTEM_PROMPT, create_client, get_api_key, parse_prediction_response, pil_image_to_png_bytes


DEFAULT_BATCH_POLL_SECONDS = 30.0
DEFAULT_FILE_POLL_SECONDS = 2.0
DEFAULT_BATCH_STAGE_DIR = Path(__file__).resolve().parent / "results" / "batch"
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


def _safe_batch_name(batch_name: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", batch_name.strip()).strip("-")
    return normalized or "harvey-building-batch"


def _request_id_for_record(record: dict) -> str:
    return f"{record['core_id']}__{record.get('building_uid')}"


def _select_records(
    manifest_path: Path,
    labels_dir: Path,
    limit_images: int | None,
    limit_buildings: int | None,
) -> list[dict]:
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
    return image_records


def _placeholder_uri(request_id: str, suffix: str) -> str:
    return f"pending://{request_id}/{suffix}"


def _state_name(value: Any) -> str:
    if value is None:
        return ""
    return str(getattr(value, "value", value))


def _save_metadata(metadata_path: Path, metadata: dict) -> None:
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def _load_metadata(metadata_path: Path) -> dict:
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def _request_payload_from_uris(pre_uri: str, post_uri: str) -> dict:
    return {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": BUILDING_SYSTEM_PROMPT},
                    {"fileData": {"mimeType": "image/png", "fileUri": pre_uri}},
                    {"fileData": {"mimeType": "image/png", "fileUri": post_uri}},
                ],
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
        },
    }


def stage_batch_requests(
    records: list[dict],
    stage_dir: Path,
    padding: int,
    model_name: str,
    batch_name: str,
) -> tuple[Path, Path]:
    stage_dir.mkdir(parents=True, exist_ok=True)
    crop_dir = stage_dir / "crops"
    crop_dir.mkdir(parents=True, exist_ok=True)
    requests_path = stage_dir / f"{batch_name}_requests.jsonl"
    metadata_path = stage_dir / f"{batch_name}_metadata.json"

    metadata = {
        "model_name": model_name,
        "batch_name": batch_name,
        "ordered_request_ids": [],
        "records": {},
        "input_file": None,
    }

    with requests_path.open("w", encoding="utf-8") as requests_handle:
        for record in records:
            request_id = _request_id_for_record(record)
            metadata["ordered_request_ids"].append(request_id)
            error_text = record.get("error")
            bbox = None
            pre_crop_path = None
            post_crop_path = None

            if error_text is None:
                try:
                    pre_crop, post_crop, bbox = crop_building_pair(
                        pre_path=record["pre_path"],
                        post_path=record["post_path"],
                        polygon_wkt=record["polygon_wkt"],
                        padding=padding,
                    )
                    pre_crop_path = crop_dir / f"{request_id}_pre.png"
                    post_crop_path = crop_dir / f"{request_id}_post.png"
                    pre_crop_path.write_bytes(pil_image_to_png_bytes(pre_crop))
                    post_crop_path.write_bytes(pil_image_to_png_bytes(post_crop))
                except Exception as exc:
                    error_text = str(exc)

            request_line = {
                "key": request_id,
                "request": _request_payload_from_uris(
                    _placeholder_uri(request_id, "pre"),
                    _placeholder_uri(request_id, "post"),
                ),
            }
            requests_handle.write(json.dumps(request_line) + "\n")

            metadata["records"][request_id] = {
                "record": {
                    "core_id": record["core_id"],
                    "building_uid": record.get("building_uid"),
                    "ground_truth_label": record.get("ground_truth_label"),
                    "label_json_path": str(record.get("label_json_path")),
                    "pre_path": str(record["pre_path"]),
                    "post_path": str(record["post_path"]),
                    "polygon_wkt": record.get("polygon_wkt"),
                },
                "crop_bbox": bbox,
                "staging_error": error_text,
                "pre_crop_path": None if pre_crop_path is None else str(pre_crop_path),
                "post_crop_path": None if post_crop_path is None else str(post_crop_path),
                "uploaded_files": {},
            }

    _save_metadata(metadata_path, metadata)
    return requests_path, metadata_path


def _file_is_active(file_obj) -> bool:
    return _state_name(getattr(file_obj, "state", None)).endswith("ACTIVE")


def _wait_for_file_active(client, file_name: str, timeout_seconds: float = 300.0) -> Any:
    deadline = time.time() + timeout_seconds
    while True:
        file_obj = client.files.get(name=file_name)
        state_name = _state_name(getattr(file_obj, "state", None))
        if state_name.endswith("ACTIVE") or state_name == "":
            return file_obj
        if state_name.endswith("FAILED"):
            raise RuntimeError(f"Uploaded file failed processing: {file_name}")
        if time.time() >= deadline:
            raise RuntimeError(f"Timed out waiting for uploaded file to become active: {file_name}")
        time.sleep(DEFAULT_FILE_POLL_SECONDS)


def _reuse_or_upload_crop_file(client, path_str: str | None, file_info: dict | None, reuse_uploaded_files: bool):
    if not path_str:
        return None

    if reuse_uploaded_files and file_info and file_info.get("name"):
        try:
            existing = _wait_for_file_active(client, file_info["name"])
            return {
                "name": existing.name,
                "uri": existing.uri,
                "mime_type": existing.mime_type or file_info.get("mime_type") or "image/png",
            }
        except Exception:
            pass

    uploaded = client.files.upload(
        file=Path(path_str),
        config={
            "mime_type": "image/png",
            "display_name": Path(path_str).name,
        },
    )
    uploaded = _wait_for_file_active(client, uploaded.name)
    return {
        "name": uploaded.name,
        "uri": uploaded.uri,
        "mime_type": uploaded.mime_type or "image/png",
    }


def prepare_uploaded_batch_input(
    client,
    requests_path: Path,
    metadata_path: Path,
    reuse_uploaded_files: bool = False,
) -> dict:
    metadata = _load_metadata(metadata_path)

    request_lines = []
    for request_id in metadata["ordered_request_ids"]:
        entry = metadata["records"][request_id]
        if entry.get("staging_error"):
            continue

        uploaded_files = entry.setdefault("uploaded_files", {})
        pre_info = _reuse_or_upload_crop_file(
            client,
            entry.get("pre_crop_path"),
            uploaded_files.get("pre"),
            reuse_uploaded_files,
        )
        post_info = _reuse_or_upload_crop_file(
            client,
            entry.get("post_crop_path"),
            uploaded_files.get("post"),
            reuse_uploaded_files,
        )
        uploaded_files["pre"] = pre_info
        uploaded_files["post"] = post_info

        request_lines.append(
            {
                "key": request_id,
                "request": _request_payload_from_uris(pre_info["uri"], post_info["uri"]),
            }
        )

    with requests_path.open("w", encoding="utf-8") as requests_handle:
        for request_line in request_lines:
            requests_handle.write(json.dumps(request_line) + "\n")

    input_file = metadata.get("input_file")
    if reuse_uploaded_files and input_file and input_file.get("name"):
        try:
            active = _wait_for_file_active(client, input_file["name"])
            metadata["input_file"] = {
                "name": active.name,
                "uri": active.uri,
                "mime_type": active.mime_type or input_file.get("mime_type") or "application/json",
            }
            _save_metadata(metadata_path, metadata)
            return metadata
        except Exception:
            pass

    uploaded_input = client.files.upload(
        file=requests_path,
        config={
            "mime_type": "application/json",
            "display_name": requests_path.name,
        },
    )
    uploaded_input = _wait_for_file_active(client, uploaded_input.name)
    metadata["input_file"] = {
        "name": uploaded_input.name,
        "uri": uploaded_input.uri,
        "mime_type": uploaded_input.mime_type or "application/json",
    }
    _save_metadata(metadata_path, metadata)
    return metadata


def _gemini_request(method: str, path: str, api_key: str, payload: dict | None = None) -> dict:
    url = f"{GEMINI_API_BASE}/{path.lstrip('/')}"
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        data=body,
        method=method,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
    )
    try:
        with urllib.request.urlopen(request) as response:
            data = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini batch request failed ({exc.code}): {error_text}") from exc
    return json.loads(data) if data else {}


def _normalize_batch_resource(payload: dict) -> dict:
    for key in ("batch", "response", "metadata"):
        value = payload.get(key)
        if isinstance(value, dict) and any(field in value for field in ("state", "output", "name", "done")):
            return value
    return payload


def _batch_name_from_payload(payload: dict) -> str:
    resource = _normalize_batch_resource(payload)
    return resource.get("name") or payload.get("name") or ""


def _batch_state_from_payload(payload: dict) -> str:
    resource = _normalize_batch_resource(payload)
    return resource.get("state") or payload.get("state") or ""


def _responses_file_name(payload: dict) -> str | None:
    resource = _normalize_batch_resource(payload)
    output = resource.get("output") or {}
    return output.get("responsesFile") or output.get("responses_file")


def submit_batch_job(model_name: str, input_file_name: str, batch_name: str, api_key: str) -> dict:
    return _gemini_request(
        "POST",
        f"models/{model_name}:batchGenerateContent",
        api_key,
        payload={
            "batch": {
                "displayName": batch_name,
                "inputConfig": {
                    "fileName": input_file_name,
                },
            }
        },
    )


def wait_for_batch_job(batch_name: str, api_key: str, poll_seconds: float = DEFAULT_BATCH_POLL_SECONDS) -> dict:
    while True:
        payload = _gemini_request("GET", batch_name, api_key)
        state = _batch_state_from_payload(payload)
        print(f"Batch job {batch_name} state={state}")
        if state in {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}:
            return payload
        time.sleep(poll_seconds)


def download_batch_outputs(client, responses_file_name: str, stage_dir: Path) -> list[Path]:
    local_output_dir = stage_dir / "downloaded_outputs"
    local_output_dir.mkdir(parents=True, exist_ok=True)
    local_path = local_output_dir / f"{responses_file_name.replace('/', '_')}.jsonl"
    local_path.write_bytes(client.files.download(file=responses_file_name))
    return [local_path]


def _extract_text_from_candidate(candidate: dict) -> str:
    parts = ((candidate or {}).get("content") or {}).get("parts") or []
    text_chunks = [part.get("text", "") for part in parts if isinstance(part, dict)]
    return "\n".join(chunk for chunk in text_chunks if chunk).strip()


def _extract_prediction_from_output_line(line: dict) -> tuple[dict, str | None, str | None]:
    response_payload = line.get("response") if isinstance(line.get("response"), dict) else line
    batch_status = line.get("status") or ("succeeded" if response_payload else None)

    error_text = None
    if isinstance(line.get("error"), dict):
        error_text = line["error"].get("message") or json.dumps(line["error"])
    elif line.get("error"):
        error_text = str(line["error"])

    if error_text:
        return {
            "label": None,
            "reason": None,
            "raw_text": "",
            "model_used": None,
            "parse_ok": False,
            "error": error_text,
        }, batch_status or "error", error_text

    candidates = response_payload.get("candidates") or []
    raw_text = _extract_text_from_candidate(candidates[0]) if candidates else ""
    prediction = parse_prediction_response(raw_text)
    prediction["model_used"] = response_payload.get("modelVersion") or response_payload.get("model") or prediction.get("model_used")
    return prediction, batch_status, prediction.get("error")


def hydrate_batch_results(
    metadata_path: Path,
    output_paths: list[Path],
    output_csv: Path,
    manifest_path: Path,
    batch_job_name: str,
    existing_rows: list[dict] | None = None,
) -> tuple[list[dict], dict]:
    metadata = _load_metadata(metadata_path)
    remaining_request_ids = list(metadata.get("ordered_request_ids", []))
    result_rows = list(existing_rows or [])

    for output_path in output_paths:
        with output_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                line = json.loads(raw_line)
                if not remaining_request_ids:
                    continue
                request_id = remaining_request_ids.pop(0)
                metadata_row = metadata["records"][request_id]
                record = {
                    **metadata_row["record"],
                    "label_json_path": Path(metadata_row["record"]["label_json_path"]),
                    "pre_path": Path(metadata_row["record"]["pre_path"]),
                    "post_path": Path(metadata_row["record"]["post_path"]),
                }
                prediction, batch_status, error_text = _extract_prediction_from_output_line(line)
                row = build_building_result_row(
                    record=record,
                    prediction=prediction,
                    bbox=tuple(metadata_row["crop_bbox"]) if metadata_row["crop_bbox"] else None,
                    error_text=error_text,
                    batch_job_name=batch_job_name,
                    request_id=request_id,
                    batch_status=batch_status,
                )
                result_rows.append(row)

    for request_id in remaining_request_ids:
        metadata_row = metadata["records"][request_id]
        record = {
            **metadata_row["record"],
            "label_json_path": Path(metadata_row["record"]["label_json_path"]),
            "pre_path": Path(metadata_row["record"]["pre_path"]),
            "post_path": Path(metadata_row["record"]["post_path"]),
        }
        error_text = metadata_row.get("staging_error") or "missing_batch_output_for_request"
        row = build_building_result_row(
            record=record,
            prediction={
                "label": None,
                "reason": None,
                "raw_text": "",
                "model_used": metadata.get("model_name"),
                "parse_ok": False,
                "error": error_text,
            },
            bbox=tuple(metadata_row["crop_bbox"]) if metadata_row["crop_bbox"] else None,
            error_text=error_text,
            batch_job_name=batch_job_name,
            request_id=request_id,
            batch_status="missing",
        )
        result_rows.append(row)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=BUILDING_RESULT_FIELDNAMES)
        writer.writeheader()
        writer.writerows(result_rows)

    metrics = _build_summary(result_rows, manifest_path, metadata.get("model_name"))
    metrics_path = output_csv.with_name(f"{output_csv.stem}_metrics.json")
    with metrics_path.open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2)

    print_summary(metrics)
    print(f"\nSaved results CSV: {output_csv}")
    print(f"Saved metrics JSON: {metrics_path}")
    return result_rows, metrics


def evaluate_buildings_batch(
    manifest_path: Path,
    output_csv: Path,
    preferred_model: str = DEFAULT_BUILDING_MODEL_NAME,
    labels_dir: Path = DEFAULT_LABELS_DIR,
    limit_images: int | None = None,
    limit_buildings: int | None = None,
    padding: int = 16,
    batch_name: str = "harvey-building-batch",
    poll_seconds: float = DEFAULT_BATCH_POLL_SECONDS,
    resume: bool = True,
    reuse_staged_requests: bool = False,
    reuse_uploaded_files: bool = False,
) -> tuple[list[dict], dict]:
    manifest_path = Path(manifest_path)
    output_csv = Path(output_csv)
    batch_name = _safe_batch_name(batch_name)

    existing_rows = _load_existing_results(output_csv) if resume else []
    completed_keys = _completed_keys(existing_rows)
    all_records = _select_records(manifest_path, labels_dir, limit_images, limit_buildings)
    pending_records = [
        record
        for record in all_records
        if (record["core_id"], str(record.get("building_uid"))) not in completed_keys
    ]

    if existing_rows and not pending_records:
        metrics = _build_summary(existing_rows, manifest_path, preferred_model)
        print_summary(metrics)
        return existing_rows, metrics

    stage_dir = DEFAULT_BATCH_STAGE_DIR / batch_name
    requests_path = stage_dir / f"{batch_name}_requests.jsonl"
    metadata_path = stage_dir / f"{batch_name}_metadata.json"
    batch_job_state_path = stage_dir / f"{batch_name}_job.json"

    if not (reuse_staged_requests and requests_path.exists() and metadata_path.exists()):
        requests_path, metadata_path = stage_batch_requests(
            records=pending_records,
            stage_dir=stage_dir,
            padding=padding,
            model_name=preferred_model,
            batch_name=batch_name,
        )
    else:
        print(f"Reusing staged batch requests from {requests_path}")

    downloaded_outputs = sorted((stage_dir / "downloaded_outputs").rglob("*.jsonl"))
    if reuse_staged_requests and downloaded_outputs and metadata_path.exists():
        saved_job = json.loads(batch_job_state_path.read_text(encoding="utf-8")) if batch_job_state_path.exists() else {}
        return hydrate_batch_results(
            metadata_path=metadata_path,
            output_paths=downloaded_outputs,
            output_csv=output_csv,
            manifest_path=manifest_path,
            batch_job_name=saved_job.get("name", batch_name),
            existing_rows=existing_rows,
        )

    client = create_client()
    metadata = prepare_uploaded_batch_input(
        client=client,
        requests_path=requests_path,
        metadata_path=metadata_path,
        reuse_uploaded_files=reuse_uploaded_files,
    )
    api_key = get_api_key()

    if reuse_staged_requests and batch_job_state_path.exists():
        saved_job = json.loads(batch_job_state_path.read_text(encoding="utf-8"))
        batch_resource = wait_for_batch_job(
            batch_name=saved_job["name"],
            api_key=api_key,
            poll_seconds=poll_seconds,
        )
    else:
        batch_resource = submit_batch_job(
            model_name=preferred_model,
            input_file_name=metadata["input_file"]["name"],
            batch_name=batch_name,
            api_key=api_key,
        )
        batch_name_value = _batch_name_from_payload(batch_resource)
        batch_job_state_path.parent.mkdir(parents=True, exist_ok=True)
        batch_job_state_path.write_text(json.dumps(batch_resource, indent=2), encoding="utf-8")
        batch_resource = wait_for_batch_job(
            batch_name=batch_name_value,
            api_key=api_key,
            poll_seconds=poll_seconds,
        )

    batch_job_state_path.write_text(json.dumps(batch_resource, indent=2), encoding="utf-8")
    responses_file_name = _responses_file_name(batch_resource)
    if not responses_file_name:
        raise RuntimeError(f"Batch completed without output.responsesFile: {json.dumps(batch_resource, indent=2)}")

    downloaded_outputs = download_batch_outputs(client, responses_file_name, stage_dir)
    return hydrate_batch_results(
        metadata_path=metadata_path,
        output_paths=downloaded_outputs,
        output_csv=output_csv,
        manifest_path=manifest_path,
        batch_job_name=_batch_name_from_payload(batch_resource),
        existing_rows=existing_rows,
    )
