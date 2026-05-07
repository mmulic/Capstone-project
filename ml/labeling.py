from __future__ import annotations

LABEL_ORDER = ["no_damage", "minor_damage", "major_damage", "destroyed"]

# xBD dataset subtype strings → unified damage label
SUBTYPE_TO_LABEL: dict[str, str | None] = {
    "no-damage":    "no_damage",
    "minor-damage": "minor_damage",
    "major-damage": "major_damage",
    "destroyed":    "destroyed",
    "un-classified": None,  # excluded from metrics
}


def is_valid_damage_label(label: str | None) -> bool:
    return label in LABEL_ORDER
