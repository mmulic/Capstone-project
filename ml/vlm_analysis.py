from pathlib import Path
import csv

try:
    from .inference import DEFAULT_MODEL_NAME, create_client, predict_damage
    from .labeling import overall_label_from_target_mask
    from .paths import resolve_manifest_path
except ImportError:
    from inference import DEFAULT_MODEL_NAME, create_client, predict_damage
    from labeling import overall_label_from_target_mask
    from paths import resolve_manifest_path

HERE = Path(__file__).resolve().parent
MANIFEST_PATH = HERE / "data" / "harvey_manifest.csv"
ROW_INDEX = 0
MODEL_NAME = DEFAULT_MODEL_NAME


def main() -> None:
    print("Reading manifest from:", MANIFEST_PATH)
    with MANIFEST_PATH.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) == 0:
        raise RuntimeError("harvey_manifest.csv is empty.")

    row = rows[ROW_INDEX]
    pre_path = resolve_manifest_path(row["pre_image"])
    post_path = resolve_manifest_path(row["post_image"])
    target_mask_path = resolve_manifest_path(row["target_mask"])
    ground_truth_label = overall_label_from_target_mask(target_mask_path)

    print("Using pair:")
    print("  pre :", pre_path)
    print("  post:", post_path)
    print("  target_mask:", target_mask_path)
    print("  ground_truth_label:", ground_truth_label)

    client = create_client()
    result = predict_damage(
        pre_path=pre_path,
        post_path=post_path,
        preferred_model=MODEL_NAME,
        client=client,
    )

    print("\nRaw Gemini response:")
    print(result.get("raw_text", ""))

    if result.get("parse_ok"):
        print("\nParsed result:")
        print("  label :", result.get("label"))
        print("  reason:", result.get("reason"))
        print("\nComparison:")
        print("  prediction  :", result.get("label"))
        print("  ground_truth:", ground_truth_label)
    else:
        print("\nCould not parse a valid prediction:")
        print(result.get("error"))


if __name__ == "__main__":
    main()
