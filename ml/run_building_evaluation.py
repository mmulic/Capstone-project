import argparse
from pathlib import Path

try:
    from .building_data import DEFAULT_LABELS_DIR
    from .building_evaluation import DEFAULT_BUILDING_MODEL_NAME, evaluate_buildings
except ImportError:
    from building_data import DEFAULT_LABELS_DIR
    from building_evaluation import DEFAULT_BUILDING_MODEL_NAME, evaluate_buildings

HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST_PATH = HERE / "data" / "harvey_manifest.csv"
DEFAULT_OUTPUT_CSV = HERE / "results" / "harvey_building_eval_results.csv"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate Gemini predictions against per-building xView2 labels.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--labels-dir", type=Path, default=DEFAULT_LABELS_DIR)
    parser.add_argument("--limit-images", type=int, default=None)
    parser.add_argument("--limit-buildings", type=int, default=None)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--model", default=DEFAULT_BUILDING_MODEL_NAME)
    parser.add_argument("--padding", type=int, default=16)
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--no-resume", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    evaluate_buildings(
        manifest_path=args.manifest,
        output_csv=args.output_csv,
        preferred_model=args.model,
        labels_dir=args.labels_dir,
        limit_images=args.limit_images,
        limit_buildings=args.limit_buildings,
        padding=args.padding,
        fail_fast=args.fail_fast,
        sleep_seconds=args.sleep_seconds,
        resume=not args.no_resume,
    )


if __name__ == "__main__":
    main()
