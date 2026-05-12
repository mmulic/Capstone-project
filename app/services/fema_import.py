"""
FEMA Ground-Truth Import Service (BE-019)
==========================================
Imports FEMA damage assessment labels and matches them to existing properties.
Supports CSV and JSON input formats.

Matching strategy:
1. Exact match by external_id
2. GPS proximity match (within 100m)
"""

import csv
import json
import io
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Property, GroundTruth, DamageClass
from app.services.image_preprocessor import image_preprocessor

GPS_MATCH_RADIUS_M = 100


# Map common FEMA label terminology to our enum
FEMA_LABEL_MAP = {
    "no damage": DamageClass.NO_DAMAGE,
    "no-damage": DamageClass.NO_DAMAGE,
    "none": DamageClass.NO_DAMAGE,
    "affected": DamageClass.MINOR,
    "minor": DamageClass.MINOR,
    "minor-damage": DamageClass.MINOR,
    "minor damage": DamageClass.MINOR,
    "major": DamageClass.MAJOR,
    "major-damage": DamageClass.MAJOR,
    "major damage": DamageClass.MAJOR,
    "destroyed": DamageClass.DESTROYED,
    "completely-destroyed": DamageClass.DESTROYED,
}


class FEMAImportService:
    """Imports FEMA ground-truth labels into the database."""

    async def import_csv(
        self, csv_data: bytes, db: AsyncSession
    ) -> dict:
        """
        Import labels from CSV. Expected columns:
        - property_id (or external_id)
        - damage_class (or damage_level, label)
        - latitude (optional, for GPS matching)
        - longitude (optional)
        - assessment_date (optional)
        """
        text = csv_data.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))

        records = []
        for row in reader:
            # Normalize column names
            normalized = {k.lower().strip(): v.strip() if v else None for k, v in row.items()}
            records.append(normalized)

        return await self._process_records(records, db)

    async def import_json(
        self, json_data: bytes, db: AsyncSession
    ) -> dict:
        """Import labels from JSON list of records."""
        try:
            data = json.loads(json_data.decode("utf-8"))
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON: {e}", "imported": 0}

        if not isinstance(data, list):
            return {"error": "Expected JSON array of records", "imported": 0}

        return await self._process_records(data, db)

    async def _process_records(
        self, records: list[dict], db: AsyncSession
    ) -> dict:
        """Process a list of label records and insert into ground_truth table."""
        imported = 0
        skipped = 0
        unmatched = 0
        errors = []

        # Pre-fetch all properties for efficient matching
        result = await db.execute(select(Property))
        all_properties = result.scalars().all()
        prop_by_external = {p.external_id: p for p in all_properties if p.external_id}

        for i, rec in enumerate(records):
            try:
                # Extract damage class
                damage_str = (
                    rec.get("damage_class")
                    or rec.get("damage_level")
                    or rec.get("label")
                    or rec.get("damage")
                )
                if not damage_str:
                    skipped += 1
                    continue

                damage_class = FEMA_LABEL_MAP.get(damage_str.lower().strip())
                if not damage_class:
                    errors.append(f"Row {i}: unknown damage class '{damage_str}'")
                    skipped += 1
                    continue

                # Find matching property
                prop = None
                ext_id = rec.get("property_id") or rec.get("external_id")
                if ext_id and ext_id in prop_by_external:
                    prop = prop_by_external[ext_id]
                else:
                    # Try GPS proximity match
                    lat = self._safe_float(rec.get("latitude") or rec.get("lat"))
                    lng = self._safe_float(rec.get("longitude") or rec.get("lng") or rec.get("lon"))
                    if lat is not None and lng is not None:
                        prop = self._find_nearest_property(lat, lng, all_properties)

                if not prop:
                    unmatched += 1
                    continue

                # Check if ground truth already exists
                existing = await db.execute(
                    select(GroundTruth).where(GroundTruth.property_id == prop.id)
                )
                if existing.scalar_one_or_none():
                    skipped += 1
                    continue

                # Parse assessment date
                assessment_date = None
                date_str = rec.get("assessment_date") or rec.get("date")
                if date_str:
                    try:
                        assessment_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        pass

                # Create ground truth record
                gt = GroundTruth(
                    property_id=prop.id,
                    damage_class=damage_class,
                    source=rec.get("source", "FEMA"),
                    assessment_date=assessment_date,
                    notes=rec.get("notes"),
                )
                db.add(gt)
                imported += 1

            except Exception as e:
                errors.append(f"Row {i}: {str(e)}")

        await db.flush()

        return {
            "total_records": len(records),
            "imported": imported,
            "skipped": skipped,
            "unmatched": unmatched,
            "errors": errors[:20],  # cap errors
            "match_rate": round(imported / max(len(records), 1) * 100, 1),
        }

    def _safe_float(self, val) -> Optional[float]:
        """Safely convert value to float."""
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def _find_nearest_property(
        self, lat: float, lng: float, properties: list[Property]
    ) -> Optional[Property]:
        """Find the closest property within GPS_MATCH_RADIUS_M meters."""
        best = None
        best_dist = GPS_MATCH_RADIUS_M / 1000  # km

        for prop in properties:
            if prop.latitude is None or prop.longitude is None:
                continue
            dist = image_preprocessor.haversine_km(lat, lng, prop.latitude, prop.longitude)
            if dist < best_dist:
                best_dist = dist
                best = prop

        return best


# Singleton
fema_import_service = FEMAImportService()
