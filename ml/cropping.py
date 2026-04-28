from __future__ import annotations

import re
from pathlib import Path

from PIL import Image


def parse_wkt_polygon(wkt: str) -> list[tuple[float, float]]:
    """Parse a WKT POLYGON string and return a list of (x, y) pixel coordinate pairs."""
    match = re.search(r"POLYGON\s*\(\((.+?)\)\)", wkt.strip(), re.IGNORECASE)
    if not match:
        raise ValueError(f"Cannot parse WKT polygon: {wkt!r}")
    coords = []
    for pair in match.group(1).split(","):
        parts = pair.strip().split()
        if len(parts) >= 2:
            coords.append((float(parts[0]), float(parts[1])))
    return coords


def polygon_bbox(
    coords: list[tuple[float, float]],
    padding: int = 16,
    img_w: int = 1024,
    img_h: int = 1024,
) -> tuple[int, int, int, int]:
    """Return (left, top, right, bottom) bounding box with padding, clamped to image bounds."""
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    left = max(0, int(min(xs)) - padding)
    top = max(0, int(min(ys)) - padding)
    right = min(img_w, int(max(xs)) + padding)
    bottom = min(img_h, int(max(ys)) + padding)
    return left, top, right, bottom


def crop_building(image_path: Path, wkt: str, padding: int = 16) -> Image.Image:
    """Crop a building region from an image using pixel-coordinate WKT polygon."""
    image = Image.open(image_path).convert("RGB")
    coords = parse_wkt_polygon(wkt)
    bbox = polygon_bbox(coords, padding=padding, img_w=image.width, img_h=image.height)
    return image.crop(bbox)
