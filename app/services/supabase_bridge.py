"""
Supabase Bridge Service (Hardened)
====================================
Connects to the ML teammate's Supabase database and exposes their predictions
through the existing API. Maps their xBD building-level schema to our property-level schema.

DEFENSIVE FEATURES:
- Detects pixel-vs-GPS coordinates and skips/flags invalid ones
- Sanitizes Colab-local image URIs (won't leak useless local paths to the frontend)
- No hardcoded credentials in source — must come from environment

THEIR SCHEMA (Supabase):
  - scenes(id, scene_id, disaster_name, disaster_type, pre_image_uri, post_image_uri, ...)
  - buildings(id, scene_id, building_uid, geom POINT, pixel_wkt, bbox_px, centroid POINT, ground_truth_label)
  - inference_jobs(id, job_name, model_name, model_version, status, started_at, finished_at)
  - building_predictions(id, building_id, job_id, final_label, final_confidence, source_model, needs_review, reason, raw_output_json)
  - evaluation_runs(id, job_id, accuracy, macro_precision, macro_recall, macro_f1, confusion_matrix_json)

OUR SCHEMA (FastAPI):
  - properties(id, address, latitude, longitude, location)
  - predictions(id, property_id, damage_class, confidence, rationale, model_name)
  - ground_truth(id, property_id, damage_class, source)
"""

import os
import logging
from typing import Optional, Any

import psycopg
from psycopg.rows import dict_row

from app.models.models import DamageClass

logger = logging.getLogger(__name__)


# ─── Configuration ────────────────────────────────────────

# NEVER hardcode credentials. Read from environment only.
SUPABASE_DSN = os.environ.get("SUPABASE_DB_DSN", "").strip()


# ─── Coordinate Validation ────────────────────────────────

# Valid GPS bounds: lat in [-90, 90], lng in [-180, 180]
# xBD pixel coordinates are typically thousands of pixels, never negative,
# so we use these heuristics to detect the difference.

def is_valid_gps(lat: Optional[float], lng: Optional[float]) -> bool:
    """
    Check if a coordinate pair looks like a real GPS lat/lng (not pixel coords).
    xBD pixel coordinates would be 0–1024 range, integers, and *very* unlikely
    to fall in valid GPS bounds — but we still want to be safe.
    """
    if lat is None or lng is None:
        return False
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except (TypeError, ValueError):
        return False
    # Must be within valid GPS bounds
    if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lng_f <= 180.0):
        return False
    # Reject (0, 0) — almost always means "missing data"
    if lat_f == 0 and lng_f == 0:
        return False
    return True


# ─── URI Sanitization ─────────────────────────────────────

# These prefixes indicate paths that aren't reachable from outside Colab/local runtime
COLAB_LOCAL_PREFIXES = (
    "/content/",
    "/tmp/",
    "/home/",
    "C:\\",
    "file://",
)


def sanitize_image_uri(uri: Optional[str]) -> Optional[str]:
    """
    Return None if the URI is a Colab/local path the frontend can't fetch.
    Return the URI unchanged if it looks like a real HTTP(S) URL.
    """
    if not uri:
        return None
    uri = uri.strip()
    if uri.startswith(("http://", "https://", "s3://")):
        return uri
    # Anything else (Colab paths, local files) is unusable to the frontend
    if uri.startswith(COLAB_LOCAL_PREFIXES) or uri.startswith("/"):
        return None
    return None


# ─── Label Mapping ────────────────────────────────────────

# ML team uses hyphens, we use underscores
ML_LABEL_TO_OURS: dict[str, DamageClass] = {
    "no-damage": DamageClass.NO_DAMAGE,
    "minor-damage": DamageClass.MINOR,
    "major-damage": DamageClass.MAJOR,
    "destroyed": DamageClass.DESTROYED,
    # Tolerate other casings/formats
    "no_damage": DamageClass.NO_DAMAGE,
    "minor_damage": DamageClass.MINOR,
    "major_damage": DamageClass.MAJOR,
    "no damage": DamageClass.NO_DAMAGE,
    "minor damage": DamageClass.MINOR,
    "major damage": DamageClass.MAJOR,
}


def map_label(ml_label: Optional[str]) -> Optional[DamageClass]:
    """Convert ML team's label format to our DamageClass enum."""
    if not ml_label:
        return None
    return ML_LABEL_TO_OURS.get(ml_label.lower().strip())


# ─── Supabase Bridge ──────────────────────────────────────

class SupabaseBridge:
    """
    Read-only adapter to the ML teammate's Supabase database.
    Pulls their predictions and exposes them in our API's data shape.
    """

    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn or SUPABASE_DSN

    @property
    def is_configured(self) -> bool:
        """True if a Supabase DSN has been provided via env var."""
        return bool(self.dsn)

    def _connect(self) -> psycopg.Connection:
        """Open a synchronous connection (psycopg, not async)."""
        if not self.is_configured:
            raise RuntimeError(
                "SUPABASE_DB_DSN is not set. "
                "Add it to your .env file to enable the ML bridge."
            )
        return psycopg.connect(self.dsn, row_factory=dict_row)

    # ── Health Check ─────────────────────────────────────

    def is_reachable(self) -> bool:
        """Test if we can connect to Supabase."""
        if not self.is_configured:
            return False
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute("SELECT 1")
                return cur.fetchone() is not None
        except Exception:
            return False

    def get_schema_summary(self) -> dict:
        """Return counts + a coordinate-validity audit for diagnostics."""
        if not self.is_configured:
            return {
                "connected": False,
                "configured": False,
                "message": "SUPABASE_DB_DSN environment variable is not set."
            }

        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS c FROM scenes")
                scenes = cur.fetchone()["c"]
                cur.execute("SELECT COUNT(*) AS c FROM buildings")
                buildings = cur.fetchone()["c"]
                cur.execute("SELECT COUNT(*) AS c FROM building_predictions")
                predictions = cur.fetchone()["c"]
                cur.execute("SELECT COUNT(*) AS c FROM inference_jobs")
                jobs = cur.fetchone()["c"]

                # Audit: how many buildings have valid GPS coordinates?
                cur.execute("""
                    SELECT
                        COUNT(*) FILTER (WHERE
                            ST_X(centroid) BETWEEN -180 AND 180
                            AND ST_Y(centroid) BETWEEN -90 AND 90
                            AND NOT (ST_X(centroid) = 0 AND ST_Y(centroid) = 0)
                        ) AS valid_gps,
                        COUNT(*) AS total
                    FROM buildings
                    WHERE centroid IS NOT NULL
                """)
                coord_audit = cur.fetchone()

                return {
                    "connected": True,
                    "configured": True,
                    "scenes": scenes,
                    "buildings": buildings,
                    "predictions": predictions,
                    "inference_jobs": jobs,
                    "coordinate_audit": {
                        "buildings_with_centroids": coord_audit["total"],
                        "buildings_with_valid_gps": coord_audit["valid_gps"],
                        "warning": (
                            "Most centroids appear to be PIXEL coordinates, not GPS. "
                            "Map markers will be filtered out until the ML team fixes coordinates."
                            if coord_audit["total"] > 0 and coord_audit["valid_gps"] / coord_audit["total"] < 0.5
                            else None
                        ),
                    },
                }
        except Exception as e:
            logger.error(f"Supabase schema summary failed: {e}")
            return {"connected": False, "configured": True, "error": str(e)}

    # ── Pull Predictions ─────────────────────────────────

    def fetch_predictions(
        self,
        limit: int = 1000,
        damage_filter: Optional[str] = None,
        disaster_name: Optional[str] = None,
        require_valid_gps: bool = False,
    ) -> list[dict]:
        """
        Pull the latest predictions joined with their building + scene info.
        Returns records mapped to our schema.

        Args:
            limit: max records to return
            damage_filter: filter by ML label (e.g. 'destroyed')
            disaster_name: filter by disaster
            require_valid_gps: if True, only return records with valid lat/lng GPS coords
        """
        if not self.is_configured:
            return [{"error": "Supabase not configured. Set SUPABASE_DB_DSN."}]

        query = """
            SELECT
                p.id              AS ml_prediction_id,
                p.final_label     AS damage_class,
                p.final_confidence AS confidence,
                p.reason          AS rationale,
                p.source_model    AS model_name,
                p.needs_review    AS needs_review,
                b.id              AS ml_building_id,
                b.building_uid    AS building_uid,
                b.ground_truth_label AS ground_truth,
                ST_X(b.centroid)  AS longitude,
                ST_Y(b.centroid)  AS latitude,
                s.id              AS ml_scene_id,
                s.scene_id        AS scene_key,
                s.disaster_name   AS disaster_name,
                s.disaster_type   AS disaster_type,
                s.pre_image_uri   AS pre_image_uri,
                s.post_image_uri  AS post_image_uri,
                s.captured_post_at AS assessed_at
            FROM building_predictions p
            JOIN buildings b ON b.id = p.building_id
            JOIN scenes s    ON s.id = b.scene_id
            WHERE 1=1
        """
        params: list[Any] = []

        if damage_filter:
            query += " AND p.final_label = %s"
            params.append(damage_filter)

        if disaster_name:
            query += " AND s.disaster_name = %s"
            params.append(disaster_name)

        # Push GPS validity check into SQL when requested for efficiency
        if require_valid_gps:
            query += """
                AND ST_X(b.centroid) BETWEEN -180 AND 180
                AND ST_Y(b.centroid) BETWEEN -90 AND 90
                AND NOT (ST_X(b.centroid) = 0 AND ST_Y(b.centroid) = 0)
            """

        query += " ORDER BY p.id DESC LIMIT %s"
        params.append(limit)

        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                return [self._map_row(r) for r in rows]
        except Exception as e:
            logger.error(f"Supabase fetch_predictions failed: {e}")
            return [{"error": str(e)}]

    def fetch_disaster_summary(self) -> list[dict]:
        """Get counts grouped by disaster name and damage class."""
        if not self.is_configured:
            return [{"error": "Supabase not configured. Set SUPABASE_DB_DSN."}]

        query = """
            SELECT
                s.disaster_name,
                p.final_label,
                COUNT(*) AS count
            FROM building_predictions p
            JOIN buildings b ON b.id = p.building_id
            JOIN scenes s    ON s.id = b.scene_id
            GROUP BY s.disaster_name, p.final_label
            ORDER BY s.disaster_name, p.final_label
        """
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute(query)
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"Supabase fetch_disaster_summary failed: {e}")
            return [{"error": str(e)}]

    def fetch_evaluation(self, job_id: Optional[int] = None) -> Optional[dict]:
        """Pull the latest evaluation_runs entry, optionally for a specific job."""
        if not self.is_configured:
            return {"error": "Supabase not configured. Set SUPABASE_DB_DSN."}

        if job_id is not None:
            query = "SELECT * FROM evaluation_runs WHERE job_id = %s ORDER BY id DESC LIMIT 1"
            params = (job_id,)
        else:
            query = "SELECT * FROM evaluation_runs ORDER BY id DESC LIMIT 1"
            params = ()

        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute(query, params)
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "id": row["id"],
                    "job_id": row["job_id"],
                    "label_set": row.get("label_set"),
                    "accuracy": float(row["accuracy"]) if row["accuracy"] else None,
                    "macro_precision": float(row["macro_precision"]) if row["macro_precision"] else None,
                    "macro_recall": float(row["macro_recall"]) if row["macro_recall"] else None,
                    "macro_f1": float(row["macro_f1"]) if row["macro_f1"] else None,
                    "confusion_matrix": row.get("confusion_matrix_json"),
                }
        except Exception as e:
            logger.error(f"Supabase fetch_evaluation failed: {e}")
            return {"error": str(e)}

    def fetch_jobs(self, limit: int = 20) -> list[dict]:
        """List recent inference jobs."""
        if not self.is_configured:
            return [{"error": "Supabase not configured. Set SUPABASE_DB_DSN."}]

        query = """
            SELECT id, job_name, model_name, model_version, status, started_at, finished_at
            FROM inference_jobs
            ORDER BY id DESC
            LIMIT %s
        """
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute(query, (limit,))
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"Supabase fetch_jobs failed: {e}")
            return [{"error": str(e)}]

    # ── Mapping ──────────────────────────────────────────

    def _map_row(self, row: dict) -> dict:
        """Map a Supabase row into our API's response format with sanitization."""
        damage = map_label(row.get("damage_class"))
        ground_truth = map_label(row.get("ground_truth"))

        # Validate GPS coordinates — keep raw values but flag invalid ones
        raw_lat = row.get("latitude")
        raw_lng = row.get("longitude")
        valid_gps = is_valid_gps(raw_lat, raw_lng)

        # Sanitize image URIs — never expose useless Colab paths
        pre_uri = sanitize_image_uri(row.get("pre_image_uri"))
        post_uri = sanitize_image_uri(row.get("post_image_uri"))

        result = {
            # Identifiers
            "property_id": str(row.get("ml_building_id")),
            "external_id": row.get("building_uid"),
            "scene_id": row.get("scene_key"),

            # Location — only include if valid GPS, else null + flag
            "latitude": float(raw_lat) if valid_gps else None,
            "longitude": float(raw_lng) if valid_gps else None,
            "location_valid": valid_gps,

            # Prediction
            "damage_class": damage.value if damage else None,
            "confidence": float(row["confidence"]) if row.get("confidence") else None,
            "rationale": row.get("rationale"),
            "model_name": row.get("model_name"),
            "needs_review": row.get("needs_review", False),

            # Ground truth (FEMA-style)
            "ground_truth_label": ground_truth.value if ground_truth else None,

            # Disaster context
            "disaster_name": row.get("disaster_name"),
            "disaster_type": row.get("disaster_type"),
            "assessed_at": row.get("assessed_at").isoformat() if row.get("assessed_at") else None,

            # Image URLs — sanitized, will be null if Colab-local
            "pre_image_url": pre_uri,
            "post_image_url": post_uri,
        }

        # Add a warning hint if data is degraded
        if not valid_gps and (raw_lat is not None or raw_lng is not None):
            result["_warnings"] = result.get("_warnings", [])
            result["_warnings"].append(
                f"Coordinates ({raw_lat}, {raw_lng}) are not valid GPS — likely pixel coordinates from xBD"
            )
        if (row.get("pre_image_uri") or row.get("post_image_uri")) and not (pre_uri or post_uri):
            result["_warnings"] = result.get("_warnings", [])
            result["_warnings"].append(
                "Image URIs are local Colab paths — frontend cannot fetch them. Need S3 upload."
            )

        return result


# Singleton
supabase_bridge = SupabaseBridge()
