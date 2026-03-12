from pathlib import Path
import sys
import csv
import json

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.building_batch_evaluation import hydrate_batch_results, stage_batch_requests
from ml.building_data import crop_building_pair, load_building_annotations, normalize_xview_subtype
from ml.building_evaluation import (
    _completed_keys,
    _load_existing_results,
    _minimum_interval_seconds,
    _row_is_terminal,
)


def test_normalize_xview_subtype():
    assert normalize_xview_subtype("major-damage") == "major_damage"
    assert normalize_xview_subtype("no-damage") == "no_damage"
    assert normalize_xview_subtype("unknown") is None


def test_load_building_annotations_reads_harvey_json():
    path = Path("/Users/shaheemjaleel/Desktop/Capstone-project/ml/data/test/labels/hurricane-harvey_00000003_post_disaster.json")
    annotations = load_building_annotations(path)
    assert annotations
    assert annotations[0]["building_uid"]
    assert annotations[0]["ground_truth_label"] in {"no_damage", "minor_damage", "major_damage", "destroyed"}


def test_crop_building_pair_returns_aligned_crops():
    pre_path = Path("/Users/shaheemjaleel/Desktop/Capstone-project/ml/data/subset_harvey/images/hurricane-harvey_00000003_pre_disaster.png")
    post_path = Path("/Users/shaheemjaleel/Desktop/Capstone-project/ml/data/subset_harvey/images/hurricane-harvey_00000003_post_disaster.png")
    label_path = Path("/Users/shaheemjaleel/Desktop/Capstone-project/ml/data/test/labels/hurricane-harvey_00000003_post_disaster.json")
    annotation = load_building_annotations(label_path)[0]

    pre_crop, post_crop, bbox = crop_building_pair(pre_path, post_path, annotation["polygon_wkt"], padding=16)
    assert pre_crop.size == post_crop.size
    assert pre_crop.size[0] > 0
    assert pre_crop.size[1] > 0
    assert len(bbox) == 4


def test_minimum_interval_seconds_uses_model_specific_rpm():
    assert round(_minimum_interval_seconds("gemini-2.0-flash-lite"), 2) == 2.5
    assert round(_minimum_interval_seconds("gemini-2.5-flash"), 2) == 7.5
    assert _minimum_interval_seconds("unknown-model") == 0.0


def test_completed_keys_loads_resume_rows(tmp_path: Path):
    output_csv = tmp_path / "results.csv"
    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["core_id", "building_uid", "predicted_label", "error", "parse_ok", "predicted_label_valid"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "core_id": "core-a",
                "building_uid": "building-1",
                "predicted_label": "destroyed",
                "error": "",
                "parse_ok": "True",
                "predicted_label_valid": "True",
            }
        )
    rows = _load_existing_results(output_csv)
    assert _completed_keys(rows) == {("core-a", "building-1")}


def test_row_is_terminal_respects_retryable_errors():
    assert _row_is_terminal(
        {
            "predicted_label": "destroyed",
            "error": "",
            "parse_ok": True,
            "predicted_label_valid": True,
        }
    )
    assert not _row_is_terminal(
        {
            "predicted_label": "",
            "error": "429 RESOURCE_EXHAUSTED retryDelay 58s",
            "parse_ok": False,
            "predicted_label_valid": False,
        }
    )
    assert not _row_is_terminal(
        {
            "predicted_label": "",
            "error": "network timeout while talking to API",
            "parse_ok": False,
            "predicted_label_valid": False,
        }
    )
    assert _row_is_terminal(
        {
            "predicted_label": "",
            "error": "missing_label_json: /tmp/missing.json",
            "parse_ok": False,
            "predicted_label_valid": False,
        }
    )


def test_stage_batch_requests_writes_jsonl_and_metadata(tmp_path: Path):
    pre_path = Path("/Users/shaheemjaleel/Desktop/Capstone-project/ml/data/subset_harvey/images/hurricane-harvey_00000003_pre_disaster.png")
    post_path = Path("/Users/shaheemjaleel/Desktop/Capstone-project/ml/data/subset_harvey/images/hurricane-harvey_00000003_post_disaster.png")
    label_path = Path("/Users/shaheemjaleel/Desktop/Capstone-project/ml/data/test/labels/hurricane-harvey_00000003_post_disaster.json")
    annotation = load_building_annotations(label_path)[0]
    record = {
        "core_id": "hurricane-harvey_00000003",
        "building_uid": annotation["building_uid"],
        "ground_truth_label": annotation["ground_truth_label"],
        "label_json_path": label_path,
        "pre_path": pre_path,
        "post_path": post_path,
        "polygon_wkt": annotation["polygon_wkt"],
        "error": None,
    }
    requests_path, metadata_path = stage_batch_requests(
        records=[record],
        stage_dir=tmp_path,
        padding=16,
        model_name="gemini-2.0-flash-lite",
        batch_name="test-batch",
    )
    request_lines = requests_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(request_lines) == 1
    request_payload = json.loads(request_lines[0])
    assert request_payload["key"].startswith("hurricane-harvey_00000003__")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert request_payload["key"] in metadata["records"]
    assert metadata["ordered_request_ids"] == [request_payload["key"]]


def test_hydrate_batch_results_reconstructs_prediction_rows(tmp_path: Path):
    metadata_path = tmp_path / "meta.json"
    request_id = "core-a__building-1"
    metadata_path.write_text(
        json.dumps(
            {
                "model_name": "gemini-2.0-flash-lite",
                "ordered_request_ids": [request_id],
                "records": {
                    request_id: {
                        "record": {
                            "core_id": "core-a",
                            "building_uid": "building-1",
                            "ground_truth_label": "destroyed",
                            "label_json_path": "/tmp/label.json",
                            "pre_path": "/tmp/pre.png",
                            "post_path": "/tmp/post.png",
                            "polygon_wkt": "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))",
                        },
                        "crop_bbox": [0, 0, 10, 10],
                        "staging_error": None,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    output_jsonl = tmp_path / "predictions.jsonl"
    output_jsonl.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": '{"label": "destroyed", "reason": "roof collapse visible"}'
                                }
                            ]
                        }
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output_csv = tmp_path / "results.csv"
    rows, metrics = hydrate_batch_results(
        metadata_path=metadata_path,
        output_paths=[output_jsonl],
        output_csv=output_csv,
        manifest_path=Path("/tmp/manifest.csv"),
        batch_job_name="batch-1",
    )
    assert len(rows) == 1
    assert rows[0]["predicted_label"] == "destroyed"
    assert rows[0]["request_id"] == request_id
    assert rows[0]["batch_status"] == "succeeded"
    assert metrics["num_buildings_scored"] == 1
