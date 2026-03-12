import csv
from pathlib import Path

# Creates csv file with:
# core_id, pre_image, post_image, target_mask, label_json
# for each hurricane sample.
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
BASE = HERE / "subset_harvey"
OUT_PATH = HERE / "harvey_manifest.csv"
LABELS_DIR = HERE / "test" / "labels"

print("Base directory:", BASE)

post_targets = sorted((BASE / "targets").glob("*_post_disaster_target.png"))
print("Found", len(post_targets), "post-disaster target masks")

rows = []

for target_path in post_targets:
    core = target_path.name.replace("_post_disaster_target.png", "")
    pre_img = BASE / "images" / f"{core}_pre_disaster.png"
    post_img = BASE / "images" / f"{core}_post_disaster.png"
    label_json = LABELS_DIR / f"{core}_post_disaster.json"

    if not (pre_img.exists() and post_img.exists()):
        print("Missing pre/post image for", core)
        continue

    if not label_json.exists():
        print("Missing label json for", core)
        continue

    rows.append(
        {
            "core_id": core,
            "pre_image": str(pre_img.relative_to(REPO_ROOT)),
            "post_image": str(post_img.relative_to(REPO_ROOT)),
            "target_mask": str(target_path.relative_to(REPO_ROOT)),
            "label_json": str(label_json.relative_to(REPO_ROOT)),
        }
    )

with OUT_PATH.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=["core_id", "pre_image", "post_image", "target_mask", "label_json"],
    )
    writer.writeheader()
    writer.writerows(rows)

print("Saved", OUT_PATH, "with", len(rows), "samples")
