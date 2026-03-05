from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.evaluation import _compute_metrics
from ml.inference import parse_prediction_response
from ml.labeling import overall_label_from_target_mask
from ml.paths import resolve_manifest_path


def test_parse_prediction_response_handles_fenced_json():
    raw = """```json
{"label":"major_damage","reason":"Visible roof collapse."}
```"""
    result = parse_prediction_response(raw)
    assert result["parse_ok"] is True
    assert result["label"] == "major_damage"


def test_compute_metrics_handles_empty_dataframe():
    metrics = _compute_metrics([])
    assert metrics["accuracy"] is None
    assert metrics["confusion_matrix"] == [[0, 0, 0, 0] for _ in range(4)]


def test_overall_label_from_target_mask_uses_max_severity(tmp_path: Path):
    import numpy as np
    from PIL import Image

    mask_path = tmp_path / "mask.png"
    mask = np.array([[0, 1], [2, 4]], dtype="uint8")
    Image.fromarray(mask).save(mask_path)

    assert overall_label_from_target_mask(mask_path) == "destroyed"


def test_resolve_manifest_path_accepts_relative_and_absolute_paths(tmp_path: Path):
    relative_path = "ml/data/subset_harvey/images/example.png"
    assert resolve_manifest_path(relative_path).is_absolute()

    absolute_path = tmp_path / "example.png"
    assert resolve_manifest_path(str(absolute_path)) == absolute_path
