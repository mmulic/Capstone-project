#!/usr/bin/env python3
"""
Normalize Harvey dataset JSON files into:
  - public/harvey/harvey-data.json      (scene metadata, building markers)
  - public/harvey/scene-polygons/*.json (per-scene geographic building polygons)

Building polygons are derived directly from the lng_lat WKT features so that UIDs
match postMarkers and coordinates are already in WGS84 lat/lng (no pixel conversion).
"""
import json
import os
import re
import glob

# Paths relative to this script's location (scripts/ → frontend/)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_FRONTEND_DIR = os.path.dirname(_SCRIPT_DIR)

HARVEY_JSON_DIR = os.path.join(_FRONTEND_DIR, "public", "harvey", "harvey_json_data")
OUT_FILE = os.path.join(_FRONTEND_DIR, "public", "harvey", "harvey-data.json")
POLYGONS_DIR = os.path.join(_FRONTEND_DIR, "public", "harvey", "scene-polygons")

DAMAGE_MAP = {
    "no-damage": "none",
    "minor-damage": "minor",
    "major-damage": "major",
    "destroyed": "destroyed",
}


def parse_wkt_polygon_coords(wkt: str):
    """
    Extract all coordinate pairs from a WKT POLYGON string.
    Returns list of (val1, val2) tuples (first value, second value per pair).
    For geographic WKT: (lng, lat). For pixel WKT: (x, y).
    """
    coords_str = re.search(r"POLYGON\s*\(\((.+)\)\)", wkt)
    if not coords_str:
        return []
    pairs = coords_str.group(1).strip().split(",")
    result = []
    for pair in pairs:
        parts = pair.strip().split()
        if len(parts) >= 2:
            try:
                result.append((float(parts[0]), float(parts[1])))
            except ValueError:
                continue
    return result


def parse_wkt_polygon_centroid(wkt: str):
    """Extract centroid from WKT POLYGON string. Returns (lat, lng) or None."""
    coords = parse_wkt_polygon_coords(wkt)
    if not coords:
        return None
    lngs = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return sum(lats) / len(lats), sum(lngs) / len(lngs)


def _image_bounds_corners(A, B, C, D, width: int, height: int):
    """Return imageBounds dict from affine lng=A+B*px, lat=C+D*py corner projection."""
    corners_lng = [A, A + B * width, A, A + B * width]
    corners_lat = [C, C, C + D * height, C + D * height]
    lng_sw = min(corners_lng)
    lng_ne = max(corners_lng)
    lat_sw = min(corners_lat)
    lat_ne = max(corners_lat)
    return {
        "sw": [round(lat_sw, 7), round(lng_sw, 7)],
        "ne": [round(lat_ne, 7), round(lng_ne, 7)],
    }


def _compute_image_bounds_one_building(xy_wkt: str, ll_wkt: str, width: int, height: int):
    """
    When only one building is present, centroid regression is underdetermined.
    Assume north-up imagery and estimate A,B,C,D from the building polygon's
    axis-aligned bbox in pixel space vs geographic space, then project image corners.
    """
    xy_coords = parse_wkt_polygon_coords(xy_wkt)
    ll_coords = parse_wkt_polygon_coords(ll_wkt)
    if len(xy_coords) < 3 or len(ll_coords) < 3:
        return None
    xs = [c[0] for c in xy_coords]
    ys = [c[1] for c in xy_coords]
    lngs = [c[0] for c in ll_coords]
    lats = [c[1] for c in ll_coords]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    lng_w, lng_e = min(lngs), max(lngs)
    lat_s, lat_n = min(lats), max(lats)
    eps = 1e-6
    dx = max(x1 - x0, eps)
    dy = max(y1 - y0, eps)
    B = (lng_e - lng_w) / dx
    A = lng_w - B * x0
    # y increases downward; northern edge (larger lat) maps to smaller y.
    D = (lat_s - lat_n) / dy
    C = lat_n - D * y0
    return _image_bounds_corners(A, B, C, D, width, height)


def compute_image_bounds(xy_features, ll_features, width: int, height: int):
    """
    Compute the geographic bounding box of the image using paired pixel and
    geographic building polygon centroids.

    Fits a linear model:
      lng = A + B * px   (lng increases with pixel x, eastward)
      lat = C + D * py   (lat decreases with pixel y, image y grows downward)

    Returns { "sw": [lat_sw, lng_sw], "ne": [lat_ne, lng_ne] } or None.
    """
    px_list, py_list, lng_list, lat_list = [], [], [], []

    for xy_f, ll_f in zip(xy_features, ll_features):
        xy_c = parse_wkt_polygon_centroid(xy_f.get("wkt", ""))
        ll_c = parse_wkt_polygon_centroid(ll_f.get("wkt", ""))
        if xy_c is None or ll_c is None:
            continue
        # parse_wkt_polygon_centroid returns (second_val_avg, first_val_avg)
        # For xy WKT "POLYGON ((x y, ...))" → returns (y_avg, x_avg)
        # For ll WKT "POLYGON ((lng lat, ...))" → returns (lat_avg, lng_avg)
        y_pix, x_pix = xy_c
        lat, lng = ll_c
        px_list.append(x_pix)
        py_list.append(y_pix)
        lng_list.append(lng)
        lat_list.append(lat)

    n = len(px_list)
    if n < 1:
        return None
    if n == 1:
        pair = next(
            (
                (xy_f, ll_f)
                for xy_f, ll_f in zip(xy_features, ll_features)
                if parse_wkt_polygon_centroid(xy_f.get("wkt", ""))
                and parse_wkt_polygon_centroid(ll_f.get("wkt", ""))
            ),
            None,
        )
        if not pair:
            return None
        return _compute_image_bounds_one_building(
            pair[0].get("wkt", ""), pair[1].get("wkt", ""), width, height
        )

    def linear_fit(xs, ys):
        """Returns (slope, intercept) via least squares."""
        mx = sum(xs) / n
        my = sum(ys) / n
        cov = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
        var = sum((xs[i] - mx) ** 2 for i in range(n))
        if var == 0:
            return 0.0, my
        slope = cov / var
        intercept = my - slope * mx
        return slope, intercept

    B, A = linear_fit(px_list, lng_list)   # lng = A + B * px
    D, C = linear_fit(py_list, lat_list)   # lat = C + D * py

    return _image_bounds_corners(A, B, C, D, width, height)


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


def extract_geo_polygons(scene_data):
    """
    Extract per-building geographic polygon rings from the lng_lat WKT features.
    Returns { uid: [[lat, lng], ...] } — ready for Leaflet Polygon without any
    pixel-to-geo conversion. Closing vertex is dropped (Leaflet closes rings itself).
    """
    polygons = {}
    for feature in scene_data.get("features", {}).get("lng_lat", []):
        uid = feature.get("properties", {}).get("uid")
        wkt = feature.get("wkt", "")
        if not uid:
            continue
        coords = parse_wkt_polygon_coords(wkt)  # list of (lng, lat)
        if len(coords) < 3:
            continue
        # WKT closes the ring by repeating the first vertex — drop it
        ring = coords[:-1] if coords[0] == coords[-1] else coords
        # Convert (lng, lat) → [lat, lng] for Leaflet
        polygons[uid] = [[round(lat, 7), round(lng, 7)] for lng, lat in ring]
    return polygons


def main():
    json_files = glob.glob(os.path.join(HARVEY_JSON_DIR, "*.json"))
    if not json_files:
        print(f"ERROR: No JSON files found in {HARVEY_JSON_DIR}")
        return

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
    bounds_computed = 0
    bounds_failed = 0

    for scene_id, phases in sorted(scenes_by_id.items()):
        pre_path = phases.get("pre")
        post_path = phases.get("post")

        pre_data = load_scene(pre_path) if pre_path else None
        post_data = load_scene(post_path) if post_path else None

        meta_source = post_data or pre_data
        metadata = meta_source.get("metadata", {}) if meta_source else {}

        pre_buildings = extract_buildings(pre_data, "pre") if pre_data else []
        post_buildings = extract_buildings(post_data, "post") if post_data else []

        if len(pre_buildings) + len(post_buildings) == 0:
            continue

        # Compute scene centroid from all buildings
        all_lats = [b["lat"] for b in pre_buildings + post_buildings]
        all_lngs = [b["lng"] for b in pre_buildings + post_buildings]
        centroid = {
            "lat": round(sum(all_lats) / len(all_lats), 6),
            "lng": round(sum(all_lngs) / len(all_lngs), 6),
        } if all_lats else None

        # Compute geographic image bounds from pixel ↔ geographic building coords.
        # Prefer post data (more complete annotation); fall back to pre.
        bounds_source = post_data or pre_data
        image_bounds = None
        if bounds_source:
            xy_features = bounds_source.get("features", {}).get("xy", [])
            ll_features = bounds_source.get("features", {}).get("lng_lat", [])
            img_w = metadata.get("width", 1024)
            img_h = metadata.get("height", 1024)
            image_bounds = compute_image_bounds(xy_features, ll_features, img_w, img_h)
        if image_bounds:
            bounds_computed += 1
        else:
            bounds_failed += 1

        scene = {
            "sceneId": scene_id,
            "disaster": metadata.get("disaster", "hurricane-harvey"),
            "disasterType": metadata.get("disaster_type", "flooding"),
            "captureDate": {
                "pre": (pre_data or {}).get("metadata", {}).get("capture_date"),
                "post": (post_data or {}).get("metadata", {}).get("capture_date"),
            },
            "imagePath": {
                "pre": f"/harvey/harvey_images/hurricane-harvey_{scene_id}_pre_disaster.png" if pre_path else None,
                "post": f"/harvey/harvey_images/hurricane-harvey_{scene_id}_post_disaster.png" if post_path else None,
            },
            "imageBounds": image_bounds,
            "imgWidth":  metadata.get("width",  1024),
            "imgHeight": metadata.get("height", 1024),
            "centroid": centroid,
            "buildingCount": {
                "pre": len(pre_buildings),
                "post": len(post_buildings),
            },
        }
        scenes.append(scene)

        for b in pre_buildings:
            pre_markers.append({**b, "sceneId": scene_id, "phase": "pre"})
        for b in post_buildings:
            post_markers.append({**b, "sceneId": scene_id, "phase": "post"})

        # Write per-scene geographic polygon file from lng_lat WKT (post preferred, fall back to pre).
        # This replaces any pre-existing file so UIDs always match postMarkers.
        poly_source = post_data or pre_data
        geo_polygons = extract_geo_polygons(poly_source) if poly_source else {}
        poly_out = os.path.join(POLYGONS_DIR, f"{scene_id}.json")
        with open(poly_out, "w") as f:
            json.dump(geo_polygons, f, separators=(",", ":"))

    keep_ids = {s["sceneId"] for s in scenes}
    if os.path.isdir(POLYGONS_DIR):
        for fn in os.listdir(POLYGONS_DIR):
            if not fn.endswith(".json"):
                continue
            sid = fn[:-5]
            if sid not in keep_ids:
                os.remove(os.path.join(POLYGONS_DIR, fn))

    print(f"Processed {len(scenes)} scenes "
          f"({sum(1 for s in scenes if s['buildingCount']['pre'] > 0)} with pre, "
          f"{sum(1 for s in scenes if s['buildingCount']['post'] > 0)} with post)")
    print(f"Image bounds: {bounds_computed} computed, {bounds_failed} failed")
    print(f"Scene polygon files written to {POLYGONS_DIR}/")

    output = {
        "scenes": scenes,
        "preMarkers": pre_markers,
        "postMarkers": post_markers,
    }

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, "w") as f:
        json.dump(output, f, separators=(",", ":"))

    size_kb = os.path.getsize(OUT_FILE) / 1024
    print(f"Written {OUT_FILE} ({size_kb:.1f} KB)")
    print(f"Pre markers: {len(pre_markers)}, Post markers: {len(post_markers)}")


if __name__ == "__main__":
    main()
