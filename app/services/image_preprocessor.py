"""
Image Preprocessing Service (BE-007)
=====================================
Handles image validation, EXIF/GPS extraction, dimension normalization,
and pre/post pair matching by property ID and GPS proximity.
"""

import io
import json
import math
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

from PIL import Image, ImageOps
from PIL.ExifTags import TAGS, GPSTAGS


# ─── Data Classes ────────────────────────────────────────

@dataclass
class ImageMetadata:
    width: int
    height: int
    file_format: str
    file_size_bytes: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    capture_date: Optional[datetime] = None
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    raw_exif: Optional[dict] = None


@dataclass
class PreprocessedImage:
    data: bytes
    metadata: ImageMetadata
    content_type: str


# ─── Constants ───────────────────────────────────────────

ALLOWED_FORMATS = {"JPEG", "PNG", "TIFF", "MPO"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/tiff"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
TARGET_WIDTH = 1024
TARGET_HEIGHT = 1024
GPS_PROXIMITY_THRESHOLD_KM = 0.5  # 500 meters


class ImagePreprocessor:
    """Validates, extracts metadata, and normalizes aerial images."""

    # ── Validation ───────────────────────────────────────

    def validate_file(self, file_data: bytes, content_type: str, filename: str) -> list[str]:
        """Validate image file. Returns list of errors (empty = valid)."""
        errors = []

        if len(file_data) > MAX_FILE_SIZE:
            errors.append(f"File exceeds {MAX_FILE_SIZE // (1024*1024)}MB limit ({len(file_data) // (1024*1024)}MB)")

        if content_type not in ALLOWED_MIME_TYPES:
            errors.append(f"Unsupported MIME type '{content_type}'. Allowed: {', '.join(ALLOWED_MIME_TYPES)}")

        try:
            img = Image.open(io.BytesIO(file_data))
            if img.format not in ALLOWED_FORMATS:
                errors.append(f"Unsupported image format '{img.format}'. Allowed: JPEG, PNG, TIFF")
            if img.width < 64 or img.height < 64:
                errors.append(f"Image too small ({img.width}x{img.height}). Minimum 64x64 pixels")
        except Exception as e:
            errors.append(f"Cannot open image: {str(e)}")

        return errors

    # ── EXIF / GPS Extraction ────────────────────────────

    def extract_metadata(self, file_data: bytes) -> ImageMetadata:
        """Extract dimensions, GPS coordinates, capture date, and camera info from image."""
        img = Image.open(io.BytesIO(file_data))

        metadata = ImageMetadata(
            width=img.width,
            height=img.height,
            file_format=img.format or "unknown",
            file_size_bytes=len(file_data),
        )

        exif_data = self._get_exif(img)
        if exif_data:
            metadata.raw_exif = {k: str(v) for k, v in exif_data.items() if isinstance(k, str)}
            metadata.latitude, metadata.longitude = self._extract_gps(exif_data)
            metadata.capture_date = self._extract_date(exif_data)
            metadata.camera_make = exif_data.get("Make")
            metadata.camera_model = exif_data.get("Model")

        return metadata

    def _get_exif(self, img: Image.Image) -> Optional[dict]:
        """Extract EXIF data as a readable dictionary."""
        try:
            raw_exif = img._getexif()
            if not raw_exif:
                return None
            return {TAGS.get(tag, tag): value for tag, value in raw_exif.items()}
        except (AttributeError, Exception):
            return None

    def _extract_gps(self, exif_data: dict) -> tuple[Optional[float], Optional[float]]:
        """Extract latitude and longitude from EXIF GPS data."""
        gps_info = exif_data.get("GPSInfo")
        if not gps_info:
            return None, None

        try:
            gps_decoded = {GPSTAGS.get(k, k): v for k, v in gps_info.items()}

            lat = self._dms_to_decimal(
                gps_decoded.get("GPSLatitude"),
                gps_decoded.get("GPSLatitudeRef", "N"),
            )
            lng = self._dms_to_decimal(
                gps_decoded.get("GPSLongitude"),
                gps_decoded.get("GPSLongitudeRef", "E"),
            )
            return lat, lng
        except (TypeError, ValueError, KeyError):
            return None, None

    def _dms_to_decimal(self, dms, ref: str) -> Optional[float]:
        """Convert GPS degrees/minutes/seconds to decimal."""
        if not dms:
            return None
        degrees = float(dms[0])
        minutes = float(dms[1])
        seconds = float(dms[2])
        decimal = degrees + minutes / 60.0 + seconds / 3600.0
        if ref in ("S", "W"):
            decimal = -decimal
        return round(decimal, 7)

    def _extract_date(self, exif_data: dict) -> Optional[datetime]:
        """Extract capture date from EXIF."""
        for field in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
            val = exif_data.get(field)
            if val:
                try:
                    return datetime.strptime(str(val), "%Y:%m:%d %H:%M:%S")
                except ValueError:
                    continue
        return None

    # ── Normalization ────────────────────────────────────

    def normalize_image(
        self,
        file_data: bytes,
        target_width: int = TARGET_WIDTH,
        target_height: int = TARGET_HEIGHT,
        output_format: str = "JPEG",
    ) -> bytes:
        """
        Normalize image dimensions while preserving aspect ratio.
        Applies histogram equalization for consistent brightness/contrast.
        """
        img = Image.open(io.BytesIO(file_data))

        # Convert to RGB if necessary (handles RGBA, palette, etc.)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        # Resize to fit within target while preserving aspect ratio
        img.thumbnail((target_width, target_height), Image.LANCZOS)

        # Apply auto-contrast (histogram equalization)
        img = ImageOps.autocontrast(img, cutoff=0.5)

        # Save normalized image
        buffer = io.BytesIO()
        save_format = output_format if output_format != "TIFF" else "JPEG"
        img.save(buffer, format=save_format, quality=90, optimize=True)
        return buffer.getvalue()

    # ── Full Preprocessing Pipeline ──────────────────────

    async def preprocess(
        self, file_data: bytes, content_type: str, filename: str
    ) -> PreprocessedImage:
        """
        Full preprocessing pipeline:
        1. Validate
        2. Extract metadata (EXIF, GPS)
        3. Normalize dimensions + contrast
        """
        errors = self.validate_file(file_data, content_type, filename)
        if errors:
            raise ValueError(f"Image validation failed: {'; '.join(errors)}")

        metadata = self.extract_metadata(file_data)
        normalized = self.normalize_image(file_data)

        # Update metadata with normalized dimensions
        norm_img = Image.open(io.BytesIO(normalized))
        metadata.width = norm_img.width
        metadata.height = norm_img.height
        metadata.file_size_bytes = len(normalized)

        return PreprocessedImage(
            data=normalized,
            metadata=metadata,
            content_type="image/jpeg",
        )

    # ── Pair Matching ────────────────────────────────────

    @staticmethod
    def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance in km between two GPS coordinates."""
        R = 6371.0
        lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def match_pairs(
        self,
        pre_images: list[dict],
        post_images: list[dict],
        threshold_km: float = GPS_PROXIMITY_THRESHOLD_KM,
    ) -> list[tuple[dict, dict]]:
        """
        Match pre/post image pairs by property ID (exact match) or GPS proximity.

        Each dict should have: 'property_id' (optional), 'latitude', 'longitude'
        Returns list of (pre, post) matched pairs.
        """
        matched = []
        used_post = set()

        # Pass 1: Match by exact property_id
        post_by_id = {}
        for i, post in enumerate(post_images):
            pid = post.get("property_id")
            if pid:
                post_by_id[pid] = (i, post)

        for pre in pre_images:
            pid = pre.get("property_id")
            if pid and pid in post_by_id:
                idx, post = post_by_id[pid]
                matched.append((pre, post))
                used_post.add(idx)

        # Pass 2: Match remaining by GPS proximity
        unmatched_pre = [p for p in pre_images if p.get("property_id") not in post_by_id]
        unmatched_post = [(i, p) for i, p in enumerate(post_images) if i not in used_post]

        for pre in unmatched_pre:
            pre_lat, pre_lng = pre.get("latitude"), pre.get("longitude")
            if pre_lat is None or pre_lng is None:
                continue

            best_match = None
            best_dist = threshold_km

            for idx, post in unmatched_post:
                if idx in used_post:
                    continue
                post_lat, post_lng = post.get("latitude"), post.get("longitude")
                if post_lat is None or post_lng is None:
                    continue

                dist = self.haversine_km(pre_lat, pre_lng, post_lat, post_lng)
                if dist < best_dist:
                    best_dist = dist
                    best_match = (idx, post)

            if best_match:
                matched.append((pre, best_match[1]))
                used_post.add(best_match[0])

        return matched


# Singleton
image_preprocessor = ImagePreprocessor()
