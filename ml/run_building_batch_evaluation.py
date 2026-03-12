import argparse
from pathlib import Path

try:
    from .building_data import DEFAULT_LABELS_DIR
    from .building_batch_evaluation import DEFAULT_BATCH_POLL_SECONDS, evaluate_buildings_batch
    from .building_evaluation import DEFAULT_BUILDING_MODEL_NAME
except ImportError:
    from building_data import DEFAULT_LABELS_DIR
    from building_batch_evaluation import DEFAULT_BATCH_POLL_SECONDS, evaluate_buildings_batch
    from building_evaluation import DEFAULT_BUILDING_MODEL_NAME

HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST_PATH = HERE / "data" / "harvey_manifest.csv"
DEFAULT_OUTPUT_CSV = HERE / "results" / "harvey_building_batch_eval_results.csv"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run building-level evaluation through Gemini Batch API and Files API.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--labels-dir", type=Path, default=DEFAULT_LABELS_DIR)
    parser.add_argument("--limit-images", type=int, default=None)
    parser.add_argument("--limit-buildings", type=int, default=None)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--model", default=DEFAULT_BUILDING_MODEL_NAME)
    parser.add_argument("--padding", type=int, default=16)
    parser.add_argument("--batch-name", default="harvey-building-batch")
    parser.add_argument("--poll-seconds", type=float, default=DEFAULT_BATCH_POLL_SECONDS)
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--reuse-staged-requests", action="store_true")
    parser.add_argument("--reuse-uploaded-files", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    evaluate_buildings_batch(
        manifest_path=args.manifest,
        output_csv=args.output_csv,
        preferred_model=args.model,
        labels_dir=args.labels_dir,
        limit_images=args.limit_images,
        limit_buildings=args.limit_buildings,
        padding=args.padding,
        batch_name=args.batch_name,
        poll_seconds=args.poll_seconds,
        resume=not args.no_resume,
        reuse_staged_requests=args.reuse_staged_requests,
        reuse_uploaded_files=args.reuse_uploaded_files,
    )


if __name__ == "__main__":
    main()
