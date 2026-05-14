"""
Frontend Compatibility Aliases
================================
Thin alias endpoints that match what the React frontend currently calls.
"""

import re
import logging
from typing import Optional, Any

import httpx
from fastapi import APIRouter, Query, HTTPException

from app.services.supabase_bridge import supabase_bridge
from app.services.geojson_service import geojson_service
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

# No prefix — frontend expects these at the root
router = APIRouter(tags=["Frontend Compat (Aliases)"])


# ─── /damage-data ────────────────────────────────────────
# Frontend calls this for the GeoJSON map data

@router.get("/damage-data")
async def damage_data(
    sw_lat: Optional[float] = Query(None),
    sw_lng: Optional[float] = Query(None),
    ne_lat: Optional[float] = Query(None),
    ne_lng: Optional[float] = Query(None),
    damage_level: Optional[str] = Query(None),
    confidence_min: Optional[float] = Query(None, ge=0.0, le=1.0),
    disaster: Optional[str] = Query(None),
    sceneId: Optional[str] = Query(None, description="Filter predictions to a single scene"),
):
    """
    Frontend-compatible alias for GeoJSON damage data.

    Routes to ML bridge if Supabase is configured (live ML predictions),
    otherwise falls back to the local PostgreSQL GeoJSON service.

    The frontend passes `?sceneId=00000003` when the user selects a scene;
    this is forwarded to the ML bridge as `scene_id` so only that scene's
    buildings are returned.

    Note: the local-DB session is created lazily (only in the fallback path)
    so a missing local PostgreSQL does not prevent the Supabase path from working.
    """
    # Prefer live ML data if Supabase is wired up
    if supabase_bridge.is_configured and supabase_bridge.is_reachable():
        from app.routers.ml_bridge import ml_geojson
        return await ml_geojson(limit=2000, disaster=disaster, scene_id=sceneId)

    # Fallback to local PostgreSQL data — open the session only when needed
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        return await geojson_service.get_feature_collection(
            db=db,
            sw_lat=sw_lat,
            sw_lng=sw_lng,
            ne_lat=ne_lat,
            ne_lng=ne_lng,
            damage_level=damage_level,
            confidence_min=confidence_min,
        )


# ─── /query ──────────────────────────────────────────────
# Frontend calls this for the chatbot

@router.post("/query")
async def query(payload: dict):
    """
    Chatbot endpoint. Builds context from Supabase predictions, geocodes location
    references, and calls Gemini. Returns response + optional map_action.
    """
    message = payload.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=422, detail="message field is required")

    # Parse conversation history
    history: list[dict[str, str]] = []
    for h in payload.get("history", []):
        if not isinstance(h, dict):
            continue
        role = h.get("role", "user")
        content = h.get("text") or h.get("content") or ""
        if content:
            history.append({"role": role, "content": content})

    context_parts: list[str] = []
    map_action: Optional[dict] = None

    if supabase_bridge.is_configured and supabase_bridge.is_reachable():
        # ── Overall damage stats ──────────────────────────────────────
        summary_rows = supabase_bridge.fetch_disaster_summary()
        if summary_rows and not summary_rows[0].get("error"):
            overall: dict[str, int] = {}
            by_disaster: dict[str, dict[str, int]] = {}
            for row in summary_rows:
                dis = row.get("disaster_name", "unknown")
                label = row.get("final_label", "unknown")
                count = int(row.get("count", 0))
                overall[label] = overall.get(label, 0) + count
                by_disaster.setdefault(dis, {})[label] = count

            total = sum(overall.values())
            context_parts.append(f"Total buildings assessed: {total}")
            context_parts.append("Damage distribution: " + ", ".join(f"{k}: {v}" for k, v in overall.items()))
            context_parts.append("Disasters covered: " + ", ".join(by_disaster.keys()))
            for dis, counts in by_disaster.items():
                context_parts.append(f"  {dis}: " + ", ".join(f"{k}: {v}" for k, v in counts.items()))

        # ── Scene reference ("scene 3", "scene #18") ─────────────────
        scene_match = _extract_scene_id(message)
        if scene_match:
            preds = supabase_bridge.fetch_predictions(limit=1000, scene_id=scene_match)
            valid = [p for p in preds if p.get("latitude") and p.get("longitude") and not p.get("error")]
            if valid:
                sc_counts: dict[str, int] = {}
                lats, lngs = [], []
                for p in valid:
                    label = p.get("damage_class") or "unknown"
                    sc_counts[label] = sc_counts.get(label, 0) + 1
                    lats.append(p["latitude"])
                    lngs.append(p["longitude"])
                center_lat = sum(lats) / len(lats)
                center_lng = sum(lngs) / len(lngs)
                # Reverse geocode so Gemini can name the neighbourhood
                location_label = await _reverse_geocode(center_lat, center_lng)
                location_str = f" ({location_label})" if location_label else ""
                context_parts.append(
                    f"\nScene {scene_match}{location_str} — {len(valid)} buildings: "
                    + ", ".join(f"{k}: {v}" for k, v in sc_counts.items())
                )
                map_action = {
                    "scene_id": scene_match,
                    "lat": center_lat,
                    "lng": center_lng,
                    "zoom": 16,
                    "show_overlay": True,
                }

        # ── Location reference (city / street / neighbourhood) ────────
        elif loc_name := _extract_location_name(message):
            geocoded = await _geocode_location(loc_name)
            if geocoded:
                radius = 0.08  # ~9 km
                preds = supabase_bridge.fetch_predictions_in_bbox(
                    min_lat=geocoded["lat"] - radius,
                    max_lat=geocoded["lat"] + radius,
                    min_lng=geocoded["lng"] - radius,
                    max_lng=geocoded["lng"] + radius,
                )
                if preds:
                    # Group by scene key
                    by_scene: dict[str, list] = {}
                    for p in preds:
                        sk = p.get("scene_key") or "unknown"
                        by_scene.setdefault(sk, []).append(p)

                    total_loc = sum(len(v) for v in by_scene.values())
                    context_parts.append(
                        f"\nLocation '{loc_name}': {total_loc} buildings across {len(by_scene)} scenes"
                    )

                    # Best scene = most buildings
                    best_key, best_preds = max(by_scene.items(), key=lambda x: len(x[1]))

                    # Reverse geocode the best scene's centre for a neighbourhood label
                    best_lats = [p["latitude"] for p in best_preds if p.get("latitude")]
                    best_lngs = [p["longitude"] for p in best_preds if p.get("longitude")]
                    if best_lats and best_lngs:
                        bc_lat = sum(best_lats) / len(best_lats)
                        bc_lng = sum(best_lngs) / len(best_lngs)
                        scene_label = await _reverse_geocode(bc_lat, bc_lng)
                    else:
                        bc_lat, bc_lng = geocoded["lat"], geocoded["lng"]
                        scene_label = None

                    sc_counts2: dict[str, int] = {}
                    for p in best_preds:
                        label = p.get("damage_class") or "unknown"
                        sc_counts2[label] = sc_counts2.get(label, 0) + 1
                    label_str = f" in {scene_label}" if scene_label else ""
                    context_parts.append(
                        f"Best scene ({best_key}){label_str}: {len(best_preds)} buildings — "
                        + ", ".join(f"{k}: {v}" for k, v in sc_counts2.items())
                    )

                    numeric = re.search(r"(\d{5,8})", best_key)
                    scene_id_short = numeric.group(1).zfill(8) if numeric else None
                    if scene_id_short:
                        map_action = {
                            "scene_id": scene_id_short,
                            "lat": bc_lat,
                            "lng": bc_lng,
                            "zoom": 14,
                            "show_overlay": True,
                        }
                else:
                    context_parts.append(
                        f"\nNo building predictions found near '{loc_name}' in our dataset. "
                        f"Coverage is primarily in the Houston, TX metro area."
                    )

        # ── Fall back to scene from payload (selected scene in UI) ────
        elif (payload_scene := payload.get("scene_id")) and not map_action:
            scene_id_norm = str(payload_scene).zfill(8)
            preds = supabase_bridge.fetch_predictions(limit=500, scene_id=scene_id_norm)
            valid = [p for p in preds if p.get("latitude") and p.get("longitude") and not p.get("error")]
            if valid:
                sc_counts3: dict[str, int] = {}
                lats3, lngs3 = [], []
                for p in valid:
                    label = p.get("damage_class") or "unknown"
                    sc_counts3[label] = sc_counts3.get(label, 0) + 1
                    lats3.append(p["latitude"])
                    lngs3.append(p["longitude"])
                center3_lat = sum(lats3) / len(lats3)
                center3_lng = sum(lngs3) / len(lngs3)
                loc3 = await _reverse_geocode(center3_lat, center3_lng)
                loc3_str = f" ({loc3})" if loc3 else ""
                context_parts.append(
                    f"\nCurrently selected scene {scene_id_norm}{loc3_str} — {len(valid)} buildings: "
                    + ", ".join(f"{k}: {v}" for k, v in sc_counts3.items())
                )

    # ── Call Gemini ───────────────────────────────────────────────────
    context_text = "\n".join(context_parts)
    response_text = await llm_service.generate_response(message, context_text, history)

    result: dict = {
        "response": response_text,
        "answer": response_text,
        "context_used": {
            "source": "supabase" if context_parts else "none",
            "has_data": bool(context_parts),
        },
    }
    if map_action:
        result["map_action"] = map_action
    return result


# ─── Helpers ─────────────────────────────────────────────

def _extract_scene_id(message: str) -> Optional[str]:
    """Extract scene ID from 'scene 3' or 'scene #18' style references."""
    match = re.search(r"scene\s*#?\s*(\d+)", message.lower())
    if match:
        return match.group(1).zfill(8)
    return None


# Houston-area locations covered by the Harvey dataset
_HOUSTON_LOCATIONS = [
    "houston", "galveston", "sugar land", "katy", "pearland",
    "league city", "friendswood", "baytown", "pasadena", "la porte",
    "deer park", "port arthur", "beaumont", "humble", "spring",
    "cypress", "the woodlands", "conroe", "south houston", "north houston",
    "west houston", "east houston", "memorial", "montrose", "heights",
    "midtown", "downtown houston", "clear lake",
]

_STREET_PATTERN = re.compile(
    r"\b([\w\s]{2,30}?"
    r"(?:street|st\.?|avenue|ave\.?|boulevard|blvd\.?|road|rd\.?|"
    r"drive|dr\.?|lane|ln\.?|highway|hwy\.?|freeway|pkwy))\b",
    re.IGNORECASE,
)


def _extract_location_name(message: str) -> Optional[str]:
    """Return a geocodable place name from the message, or None."""
    lower = message.lower()
    for loc in _HOUSTON_LOCATIONS:
        if loc in lower:
            return loc
    m = _STREET_PATTERN.search(message)
    if m:
        return m.group(1).strip()
    zip_m = re.search(r"\b(7[0-9]{4})\b", message)
    if zip_m:
        return zip_m.group(1)
    return None


async def _geocode_location(location: str) -> Optional[dict]:
    """Geocode a place name to lat/lng via Nominatim (OpenStreetMap). No API key needed."""
    query = location if "houston" in location.lower() else f"{location}, Houston TX"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "format": "json", "limit": 1, "countrycodes": "us"},
                headers={"User-Agent": "DisasterAssessmentPlatform/1.0 (capstone)"},
            )
            if resp.status_code == 200:
                results = resp.json()
                if results:
                    return {
                        "lat": float(results[0]["lat"]),
                        "lng": float(results[0]["lon"]),
                        "display_name": results[0].get("display_name", location),
                    }
    except Exception as e:
        logger.warning(f"Geocoding '{location}' failed: {e}")
    return None


async def _reverse_geocode(lat: float, lng: float) -> Optional[str]:
    """
    Convert lat/lng to a human-readable neighbourhood / suburb label.
    Returns a short string like "Westside, Houston, TX" or None on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "lat": lat,
                    "lon": lng,
                    "format": "json",
                    "zoom": 14,       # neighbourhood level
                    "addressdetails": 1,
                },
                headers={"User-Agent": "DisasterAssessmentPlatform/1.0 (capstone)"},
            )
            if resp.status_code == 200:
                data = resp.json()
                addr = data.get("address", {})
                # Build a compact label: neighbourhood/suburb + city + state
                parts = [
                    addr.get("neighbourhood") or addr.get("suburb") or addr.get("quarter"),
                    addr.get("city") or addr.get("town") or addr.get("county"),
                    addr.get("state"),
                ]
                label = ", ".join(p for p in parts if p)
                return label or data.get("display_name", "").split(",")[0]
    except Exception as e:
        logger.warning(f"Reverse geocode ({lat}, {lng}) failed: {e}")
    return None


# ─── /evaluate ───────────────────────────────────────────
# Frontend calls this for single-property detail

@router.get("/evaluate")
async def evaluate_alias(
    propertyId: Optional[str] = Query(None, description="Property/building ID to evaluate"),
):
    """
    Frontend-compatible alias for property evaluation.

    Frontend calls: GET /evaluate?propertyId=X
    We translate to either:
      - ML bridge prediction lookup (if Supabase configured + ID looks like an ML building ID)
      - Local property detail (fallback)

    Note: local-DB sessions are opened lazily so a missing local PostgreSQL does not
    block the Supabase path from working.
    """
    if not propertyId:
        # If no property ID given, return overall evaluation metrics
        # Try ML bridge first, fallback to local
        if supabase_bridge.is_configured and supabase_bridge.is_reachable():
            from app.routers.ml_bridge import ml_evaluation
            try:
                return await ml_evaluation(job_id=None)
            except HTTPException:
                pass

        # Fallback to local evaluation
        from app.services.evaluation_service import evaluation_service
        from app.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            return await evaluation_service.evaluate(db)

    # Property-specific lookup
    # Try ML bridge first (since frontend likely shows ML predictions)
    if supabase_bridge.is_configured and supabase_bridge.is_reachable():
        predictions = supabase_bridge.fetch_predictions(limit=1000)
        match = next(
            (p for p in predictions if str(p.get("property_id")) == str(propertyId)
             or p.get("external_id") == propertyId),
            None,
        )
        if match:
            return match

    # Fallback to local property detail
    try:
        from app.routers.results import get_property_detail
        from app.core.database import AsyncSessionLocal
        from uuid import UUID
        async with AsyncSessionLocal() as db:
            return await get_property_detail(UUID(propertyId), db=db)
    except (ValueError, HTTPException) as e:
        raise HTTPException(
            status_code=404,
            detail=f"Property '{propertyId}' not found in either ML or local database"
        )
