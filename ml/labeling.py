from pathlib import Path

import numpy as np
from PIL import Image

LABEL_ORDER = ["no_damage", "minor_damage", "major_damage", "destroyed"]

MASK_VALUE_TO_LABEL = {
    1: "no_damage",
    2: "minor_damage",
    3: "major_damage",
    4: "destroyed",
}

VALID_DAMAGE_LABELS = set(LABEL_ORDER)


def is_valid_damage_label(label: str | None) -> bool:
    return label in VALID_DAMAGE_LABELS


def overall_label_from_target_mask(mask_path: Path) -> str:
    """Convert xBD target-mask IDs into one image-level damage label."""
    mask = np.array(Image.open(mask_path))
    unique_vals = np.unique(mask)
    damage_vals = sorted(v for v in unique_vals.tolist() if v in MASK_VALUE_TO_LABEL)
    if not damage_vals:
        return "unknown"
    return MASK_VALUE_TO_LABEL[damage_vals[-1]]
