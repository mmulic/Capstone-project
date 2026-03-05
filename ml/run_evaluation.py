import argparse
from pathlib import Path

try:
    from .evaluation import evaluate_manifest
    from .inference import DEFAULT_MODEL_NAME
except ImportError:
    from evaluation import evaluate_manifest
    from inference import DEFAULT_MODEL_NAME

HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST_PATH = HERE / "data" / "harvey_manifest.csv"
DEFAULT_OUTPUT_CSV = HERE / "results" / "harvey_eval_results.csv"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate Gemini predictions against FEMA labels.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--row-offset", type=int, default=0)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    evaluate_manifest(
        manifest_path=args.manifest,
        output_csv=args.output_csv,
        preferred_model=args.model,
        limit=args.limit,
        row_offset=args.row_offset,
        fail_fast=args.fail_fast,
        sleep_seconds=args.sleep_seconds,
    )


if __name__ == "__main__":
    main()
