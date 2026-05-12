"""
ML Bridge Router
=================
Exposes the ML teammate's Supabase predictions through clean API endpoints.
Frontend calls these — backend handles the cross-database join under the hood.

Endpoints:
  GET  /api/ml/health              — Check Supabase connectivity + diagnostics
  GET  /api/ml/predictions         — List predictions (with filters)
  GET  /api/ml/geojson             — GeoJSON FeatureCollection for map (only valid GPS)
  GET  /api/ml/stats               — Damage distribution by disaster
  GET  /api/ml/evaluation          — Latest accuracy/F1/confusion matrix
  GET  /api/ml/jobs                — Recent inference jobs

DEFENSIVE BEHAVIOR:
- Returns 503 if SUPABASE_DB_DSN is not set instead of crashing
- GeoJSON endpoint filters out features without valid GPS coordinates
- Predictions endpoint includes _warnings array when data is degraded
- Image URLs returned as null if they're unreachable Colab paths
"""

from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from app.services.supabase_bridge import supabase_bridge

router = APIRouter(prefix="/api/ml", tags=["ML Bridge (Supabase)"])


def _require_configured():
    """Raise 503 if the bridge isn't configured."""
    if not supabase_bridge.is_configured:
        raise HTTPException(
            status_code=503,
            detail=(
                "ML bridge is not configured. "
                "Set SUPABASE_DB_DSN environment variable to enable."
            ),
        )


# ─── Health ───────────────────────────────────────────────

@router.get("/health")
async def ml_health():
    """
    Check connectivity to the ML teammate's Supabase database.
    Includes a coordinate audit so the team can see if data quality is good.
    """
    return supabase_bridge.get_schema_summary()


# ─── Predictions ──────────────────────────────────────────

@router.get("/predictions")
async def list_predictions(
    limit: int = Query(100, ge=1, le=1000),
    damage: Optional[str] = Query(None, description="Filter: no-damage, minor-damage, major-damage, destroyed"),
    disaster: Optional[str] = Query(None, description="Filter by disaster name"),
    only_with_gps: bool = Query(False, description="Only return rows with valid GPS coordinates"),
):
    """
    List predictions from the ML pipeline.

    Each prediction includes:
    - property_id, external building UID
    - latitude/longitude (or null if invalid)
    - damage_class, confidence, rationale
    - ground truth label (if available)
    - disaster name + type
    - _warnings array if data quality is degraded
    """
    _require_configured()

    results = supabase_bridge.fetch_predictions(
        limit=limit,
        damage_filter=damage,
        disaster_name=disaster,
        require_valid_gps=only_with_gps,
    )

    # Count warnings across the dataset for visibility
    total_warnings = sum(1 for r in results if r.get("_warnings"))
    valid_gps_count = sum(1 for r in results if r.get("location_valid"))

    return {
        "count": len(results),
        "valid_gps_count": valid_gps_count,
        "warnings_count": total_warnings,
        "predictions": results,
    }


# ─── GeoJSON for Map ──────────────────────────────────────

DAMAGE_COLORS = {
    "no_damage": "#27AE60",
    "minor_damage": "#F39C12",
    "major_damage": "#E67E22",
    "destroyed": "#E74C3C",
}


@router.get("/geojson")
async def ml_geojson(
    limit: int = Query(1000, ge=1, le=5000),
    disaster: Optional[str] = Query(None, description="Filter by disaster name"),
):
    """
    Return ML predictions as a GeoJSON FeatureCollection.
    AUTOMATICALLY FILTERS OUT records without valid GPS coordinates so the map
    only shows pins that actually make geographic sense.

    Frontend can plug straight into Leaflet:
    ```js
    const res = await fetch('/api/ml/geojson');
    const geojson = await res.json();
    L.geoJSON(geojson, { style: f => ({ color: f.properties.color }) }).addTo(map);
    ```
    """
    _require_configured()

    # Use require_valid_gps=True so the SQL itself filters bad coords out
    predictions = supabase_bridge.fetch_predictions(
        limit=limit,
        disaster_name=disaster,
        require_valid_gps=True,
    )

    features = []
    for p in predictions:
        if p.get("error"):
            continue
        # Even with the SQL filter, double-check at the Python layer
        if p.get("latitude") is None or p.get("longitude") is None:
            continue
        if not p.get("location_valid"):
            continue

        damage = p.get("damage_class")
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [p["longitude"], p["latitude"]],
            },
            "properties": {
                "id": p["property_id"],
                "external_id": p.get("external_id"),
                "damage_class": damage,
                "confidence": p.get("confidence"),
                "rationale": p.get("rationale"),
                "color": DAMAGE_COLORS.get(damage, "#808080"),
                "disaster_name": p.get("disaster_name"),
                "disaster_type": p.get("disaster_type"),
                "ground_truth_label": p.get("ground_truth_label"),
                "pre_image_url": p.get("pre_image_url"),
                "post_image_url": p.get("post_image_url"),
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "total_features": len(features),
            "filtered_by_disaster": disaster,
            "note": "Records without valid GPS coordinates are excluded.",
        },
    }


# ─── Stats ────────────────────────────────────────────────

@router.get("/stats")
async def ml_stats():
    """
    Damage distribution grouped by disaster.
    Used by frontend dashboard for summary cards and charts.
    """
    _require_configured()

    rows = supabase_bridge.fetch_disaster_summary()

    if rows and rows[0].get("error"):
        raise HTTPException(status_code=500, detail=rows[0]["error"])

    # Reorganize: { disaster_name: { label: count } }
    summary: dict[str, dict[str, int]] = {}
    for row in rows:
        disaster = row["disaster_name"] or "unknown"
        label = row["final_label"]
        count = row["count"]
        if disaster not in summary:
            summary[disaster] = {}
        summary[disaster][label] = count

    # Compute totals across all disasters
    overall: dict[str, int] = {}
    for disaster_counts in summary.values():
        for label, cnt in disaster_counts.items():
            overall[label] = overall.get(label, 0) + cnt

    return {
        "by_disaster": summary,
        "overall_distribution": overall,
        "total_predictions": sum(overall.values()),
        "disasters_count": len(summary),
    }


# ─── Evaluation Metrics ───────────────────────────────────

@router.get("/evaluation")
async def ml_evaluation(job_id: Optional[int] = None):
    """
    Latest evaluation metrics from the ML team's evaluation_runs table.
    Includes accuracy, macro precision/recall/F1, and confusion matrix.

    Pass `?job_id=N` to fetch metrics for a specific inference job.
    """
    _require_configured()

    result = supabase_bridge.fetch_evaluation(job_id=job_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="No evaluation runs found. Has the ML notebook completed an evaluation pass?"
        )
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


# ─── Jobs ────────────────────────────────────────────────

@router.get("/jobs")
async def ml_jobs(limit: int = Query(20, ge=1, le=100)):
    """List recent inference jobs from the ML pipeline."""
    _require_configured()

    jobs = supabase_bridge.fetch_jobs(limit=limit)
    return {
        "count": len(jobs),
        "jobs": jobs,
    }
