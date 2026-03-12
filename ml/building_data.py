import csv
import json
from pathlib import Path

from PIL import Image
from shapely import wkt

try:
    from .paths import repo_root, resolve_manifest_path
except ImportError:
    from paths import repo_root, resolve_manifest_path

XVIEW_SUBTYPE_TO_LABEL = {
    "no-damage": "no_damage",
    "minor-damage": "minor_damage",
    "major-damage": "major_damage",
    "destroyed": "destroyed",
}

DEFAULT_LABELS_DIR = repo_root() / "ml" / "data" / "test" / "labels"


def normalize_xview_subtype(subtype: str | None) -> str | None:
    return XVIEW_SUBTYPE_TO_LABEL.get(subtype)


def label_json_path_for_core(core_id: str, labels_dir: Path = DEFAULT_LABELS_DIR) -> Path:
    return Path(labels_dir) / f"{core_id}_post_disaster.json"


def load_building_annotations(label_json_path: Path) -> list[dict]:
    label_json_path = Path(label_json_path)
    payload = json.loads(label_json_path.read_text(encoding="utf-8"))
    annotations = []

    for feature in payload.get("features", {}).get("xy", []):
        properties = feature.get("properties", {})
        if properties.get("feature_type") != "building":
            continue
        ground_truth_label = normalize_xview_subtype(properties.get("subtype"))
        if ground_truth_label is None:
            continue
        annotations.append(
            {
                "building_uid": properties.get("uid"),
                "polygon_wkt": feature.get("wkt"),
                "ground_truth_label": ground_truth_label,
                "raw_subtype": properties.get("subtype"),
            }
        )

    return annotations


def load_manifest_rows(manifest_path: Path) -> list[dict]:
    manifest_path = Path(manifest_path)
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_building_records(manifest_path: Path, labels_dir: Path = DEFAULT_LABELS_DIR) -> list[dict]:
    records = []
    for row in load_manifest_rows(manifest_path):
        core_id = row["core_id"]
        label_path = (
            resolve_manifest_path(row["label_json"])
            if row.get("label_json")
            else label_json_path_for_core(core_id, labels_dir=labels_dir)
        )
        if not label_path.exists():
            records.append(
                {
                    "core_id": core_id,
                    "pre_path": resolve_manifest_path(row["pre_image"]),
                    "post_path": resolve_manifest_path(row["post_image"]),
                    "label_json_path": label_path,
                    "building_uid": None,
                    "polygon_wkt": None,
                    "ground_truth_label": None,
                    "error": f"missing_label_json: {label_path}",
                }
            )
            continue

        for annotation in load_building_annotations(label_path):
            records.append(
                {
                    "core_id": core_id,
                    "pre_path": resolve_manifest_path(row["pre_image"]),
                    "post_path": resolve_manifest_path(row["post_image"]),
                    "label_json_path": label_path,
                    **annotation,
                    "error": None,
                }
            )
    return records


def crop_building_pair(
    pre_path: Path,
    post_path: Path,
    polygon_wkt: str,
    padding: int = 16,
) -> tuple[Image.Image, Image.Image, tuple[int, int, int, int]]:
    polygon = wkt.loads(polygon_wkt)
    min_x, min_y, max_x, max_y = polygon.bounds

    pre_image = Image.open(pre_path).convert("RGB")
    post_image = Image.open(post_path).convert("RGB")
    width, height = pre_image.size

    left = max(0, int(min_x) - padding)
    top = max(0, int(min_y) - padding)
    right = min(width, int(max_x) + padding)
    bottom = min(height, int(max_y) + padding)

    if right <= left or bottom <= top:
        raise ValueError("invalid_crop_bounds")

    bbox = (left, top, right, bottom)
    return pre_image.crop(bbox), post_image.crop(bbox), bbox
