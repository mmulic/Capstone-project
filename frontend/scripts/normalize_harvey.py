#!/usr/bin/env python3
"""
Normalize Harvey dataset JSON files into a single harvey-data.json.
Parses WKT polygons to extract centroid lat/lng, pairs pre/post scenes by ID,
and produces map-ready building records.
"""
import json
import os
import re
import glob

HARVEY_JSON_DIR = "/Users/aeinayet/Downloads/drive-download-20260402T181530Z-3-001/Harvey json"
OUT_FILE = "/Users/aeinayet/PersonalProjects/Dashboard/public/harvey/harvey-data.json"

DAMAGE_MAP = {
    "no-damage": "none",
    "minor-damage": "minor",
    "major-damage": "major",
    "destroyed": "destroyed",
}

def parse_wkt_polygon_centroid(wkt: str):
    """Extract centroid from WKT POLYGON string. Returns (lat, lng) or None."""
    coords_str = re.search(r"POLYGON\s*\(\((.+)\)\)", wkt)
    if not coords_str:
        return None
    pairs = coords_str.group(1).strip().split(",")
    lngs, lats = [], []
    for pair in pairs:
        parts = pair.strip().split()
        if len(parts) >= 2:
            try:
                lngs.append(float(parts[0]))
                lats.append(float(parts[1]))
            except ValueError:
                continue
    if not lats:
        return None
    return sum(lats) / len(lats), sum(lngs) / len(lngs)

def parse_scene_id(filename: str):
    """Extract zero-padded scene ID from filename like hurricane-harvey_00000037_post_disaster.json"""
    m = re.search(r"_(\d+)_(pre|post)_disaster", filename)
    if m:
        return m.group(1), m.group(2)
    return None, None

def load_scene(filepath: str):
    with open(filepath, "r") as f:
        return json.load(f)

def extract_buildings(scene_data, phase: str):
    """Return a list of normalized building records from a scene."""
    buildings = []
    for feature in scene_data.get("features", {}).get("lng_lat", []):
        props = feature.get("properties", {})
        wkt = feature.get("wkt", "")
        centroid = parse_wkt_polygon_centroid(wkt)
        if centroid is None:
            continue
        lat, lng = centroid
        raw_subtype = props.get("subtype", "no-damage")
        damage = DAMAGE_MAP.get(raw_subtype, "none")
        buildings.append({
            "uid": props.get("uid"),
            "lat": round(lat, 7),
            "lng": round(lng, 7),
            "damage": damage,
            "rawSubtype": raw_subtype,
            "featureType": props.get("feature_type", "building"),
        })
    return buildings

def main():
    json_files = glob.glob(os.path.join(HARVEY_JSON_DIR, "*.json"))

    # Group by scene ID
    scenes_by_id = {}
    for filepath in json_files:
        filename = os.path.basename(filepath)
        scene_id, phase = parse_scene_id(filename)
        if not scene_id or not phase:
            continue
        if scene_id not in scenes_by_id:
            scenes_by_id[scene_id] = {}
        scenes_by_id[scene_id][phase] = filepath

    scenes = []
    pre_markers = []
    post_markers = []

    for scene_id, phases in sorted(scenes_by_id.items()):
        pre_path = phases.get("pre")
        post_path = phases.get("post")

        pre_data = load_scene(pre_path) if pre_path else None
        post_data = load_scene(post_path) if post_path else None

        meta_source = post_data or pre_data
        metadata = meta_source.get("metadata", {}) if meta_source else {}

        pre_buildings = extract_buildings(pre_data, "pre") if pre_data else []
        post_buildings = extract_buildings(post_data, "post") if post_data else []

        # Compute scene centroid from all buildings
        all_lats = [b["lat"] for b in pre_buildings + post_buildings]
        all_lngs = [b["lng"] for b in pre_buildings + post_buildings]
        centroid = {
            "lat": round(sum(all_lats) / len(all_lats), 6),
            "lng": round(sum(all_lngs) / len(all_lngs), 6),
        } if all_lats else None

        scene = {
            "sceneId": scene_id,
            "disaster": metadata.get("disaster", "hurricane-harvey"),
            "disasterType": metadata.get("disaster_type", "flooding"),
            "captureDate": {
                "pre": (pre_data or {}).get("metadata", {}).get("capture_date"),
                "post": (post_data or {}).get("metadata", {}).get("capture_date"),
            },
            "imagePath": {
                "pre": f"/harvey/images/hurricane-harvey_{scene_id}_pre_disaster.png" if pre_path else None,
                "post": f"/harvey/images/hurricane-harvey_{scene_id}_post_disaster.png" if post_path else None,
            },
            "centroid": centroid,
            "buildingCount": {
                "pre": len(pre_buildings),
                "post": len(post_buildings),
            },
            # buildings sub-object omitted; per-building data lives in preMarkers/postMarkers flat arrays
        }
        scenes.append(scene)

        # Accumulate flat marker arrays (kept for future overlay use)
        for b in pre_buildings:
            pre_markers.append({**b, "sceneId": scene_id, "phase": "pre"})
        for b in post_buildings:
            post_markers.append({**b, "sceneId": scene_id, "phase": "post"})

    print(f"Processed {len(scenes)} scenes ({sum(1 for s in scenes if s['buildingCount']['pre'] > 0)} with pre, {sum(1 for s in scenes if s['buildingCount']['post'] > 0)} with post)")

    output = {
        "scenes": scenes,
        "preMarkers": pre_markers,
        "postMarkers": post_markers,
    }

    with open(OUT_FILE, "w") as f:
        json.dump(output, f, separators=(",", ":"))

    size_kb = os.path.getsize(OUT_FILE) / 1024
    print(f"Written {OUT_FILE} ({size_kb:.1f} KB)")
    print(f"Pre markers: {len(pre_markers)}, Post markers: {len(post_markers)}")

if __name__ == "__main__":
    main()
