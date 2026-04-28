"""CLI entry point for per-building crop evaluation.

Usage examples:

  # Evaluate all buildings in all label JSONs:
  python ml/run_evaluation_building.py

  # Limit to first 50 buildings, hurricane-harvey only:
  python ml/run_evaluation_building.py --disaster hurricane-harvey --limit 50

  # Custom output path with sleep between calls:
  python ml/run_evaluation_building.py \\
    --output-csv ml/results/building_eval_results.csv \\
    --model gemini-2.5-flash \\
    --sleep-seconds 1.0
"""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from .evaluation_building import IMAGES_DIR, LABELS_DIR, evaluate_building_crops
    from .inference import DEFAULT_MODEL_NAME
except ImportError:
    from evaluation_building import IMAGES_DIR, LABELS_DIR, evaluate_building_crops
    from inference import DEFAULT_MODEL_NAME


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate Gemini per-building damage predictions on xBD image crops.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--labels-dir",
        type=Path,
        default=LABELS_DIR,
        help="Directory containing xBD label JSON files.",
    )
    parser.add_argument(
        "--images-dir",
        type=Path,
        default=IMAGES_DIR,
        help="Directory containing pre/post disaster PNG images.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=None,
        help="Path to write results CSV (metrics JSON saved alongside). "
             "Defaults to ml/results/building_eval_results.csv.",
    )
    parser.add_argument(
        "--model",
        dest="preferred_model",
        default=DEFAULT_MODEL_NAME,
        help="Gemini model name.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Stop after this many buildings (default: all).",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.5,
        help="Seconds to sleep between Gemini API calls.",
    )
    parser.add_argument(
        "--disaster",
        dest="disaster_filter",
        default=None,
        help="Only process label JSONs whose filename starts with this string "
             "(e.g. 'hurricane-harvey', 'guatemala-volcano').",
    )
    parser.add_argument(
        "--padding",
        dest="crop_padding",
        type=int,
        default=16,
        help="Pixel padding added around each building bounding box crop.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        default=False,
        help="Stop on first error.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    evaluate_building_crops(
        labels_dir=args.labels_dir,
        images_dir=args.images_dir,
        output_csv=args.output_csv,
        preferred_model=args.preferred_model,
        limit=args.limit,
        sleep_seconds=args.sleep_seconds,
        disaster_filter=args.disaster_filter,
        crop_padding=args.crop_padding,
        fail_fast=args.fail_fast,
    )


if __name__ == "__main__":
    main()
