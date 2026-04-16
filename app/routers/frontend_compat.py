"""
Frontend Compatibility Aliases
================================
Thin alias endpoints that match what the React frontend currently calls.
This lets the frontend keep its existing api.js without any changes.

Frontend expects:
  GET  /damage-data        →  forwards to /api/ml/geojson (or /api/geojson fallback)
  POST /query              →  forwards to /api/chat with field translation
  GET  /evaluate           →  forwards to /api/properties/{id}

These wrappers do field translation (e.g. message+history → message+session_id)
and route to the appropriate underlying endpoint based on data availability.
"""

from typing import Optional, Any
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.supabase_bridge import supabase_bridge
from app.services.geojson_service import geojson_service
from app.services.rag_service import rag_service
from app.services.llm_service import llm_service

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
    db: AsyncSession = Depends(get_db),
):
    """
    Frontend-compatible alias for GeoJSON damage data.

    Routes to ML bridge if Supabase is configured (live ML predictions),
    otherwise falls back to the local PostgreSQL GeoJSON service.
    """
    # Prefer live ML data if Supabase is wired up
    if supabase_bridge.is_configured and supabase_bridge.is_reachable():
        # Reuse the ML bridge router's logic by importing its handler
        from app.routers.ml_bridge import ml_geojson
        return await ml_geojson(limit=2000, disaster=disaster)

    # Fallback to local PostgreSQL data
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
async def query(
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Frontend-compatible alias for the chatbot.

    Frontend sends: { message: str, history: array | object }
    Pulls real prediction data from Supabase for context, then generates a response.
    """
    message = payload.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=422, detail="message field is required")

    # Build context from real Supabase data if available
    context_text = ""
    stats = None

    if supabase_bridge.is_configured and supabase_bridge.is_reachable():
        # Get overall stats
        summary_rows = supabase_bridge.fetch_disaster_summary()
        if summary_rows and not summary_rows[0].get("error"):
            overall = {}
            by_disaster = {}
            for row in summary_rows:
                disaster = row.get("disaster_name", "unknown")
                label = row.get("final_label", "unknown")
                count = row.get("count", 0)
                overall[label] = overall.get(label, 0) + count
                if disaster not in by_disaster:
                    by_disaster[disaster] = {}
                by_disaster[disaster][label] = count

            total = sum(overall.values())
            context_text = f"Disaster Assessment Database Summary:\n"
            context_text += f"Total predictions: {total}\n"
            context_text += f"Damage distribution: {', '.join(f'{k}: {v}' for k, v in overall.items())}\n"
            for disaster, counts in by_disaster.items():
                context_text += f"\n{disaster}: {', '.join(f'{k}: {v}' for k, v in counts.items())}"

            stats = {"total": total, "distribution": overall, "by_disaster": by_disaster}

        # If the question mentions a specific location or property, search predictions
        lower_msg = message.lower()
        if any(word in lower_msg for word in ["property", "building", "address", "scene", "location", "specific"]):
            preds = supabase_bridge.fetch_predictions(limit=5)
            if preds and not preds[0].get("error"):
                context_text += "\n\nSample predictions:\n"
                for p in preds[:5]:
                    context_text += (
                        f"- Building {p.get('external_id', 'N/A')} in {p.get('scene_id', 'N/A')}: "
                        f"{p.get('damage_class', 'unknown')} (confidence: {p.get('confidence', 'N/A')}). "
                        f"Rationale: {p.get('rationale', 'N/A')}\n"
                    )

    # Generate a smart response based on the context
    if context_text:
        # Build a response that actually uses the real data
        response_text = _generate_contextual_response(message, context_text, stats)
    else:
        response_text = (
            "The assessment database is not currently connected. "
            "Once the Supabase bridge is configured, I can answer questions about "
            "damage predictions, building assessments, and disaster statistics."
        )

    return {
        "response": response_text,
        "answer": response_text,
        "context_used": {
            "source": "supabase" if context_text else "none",
            "has_data": bool(context_text),
        },
    }


def _generate_contextual_response(message: str, context: str, stats: dict = None) -> str:
    """Generate a helpful response using real Supabase data as context."""
    lower = message.lower()

    if stats:
        total = stats.get("total", 0)
        dist = stats.get("distribution", {})
        by_disaster = stats.get("by_disaster", {})

        # Handle common question patterns
        if any(w in lower for w in ["how many", "total", "count", "number"]):
            if "destroyed" in lower or "destroy" in lower:
                destroyed = dist.get("destroyed", 0)
                return (
                    f"Based on our VLM analysis, {destroyed:,} buildings were classified as destroyed "
                    f"out of {total:,} total assessed buildings ({destroyed/total*100:.1f}%). "
                    f"This includes assessments across {len(by_disaster)} disaster events: "
                    f"{', '.join(by_disaster.keys())}."
                )
            if "major" in lower:
                major = dist.get("major-damage", 0)
                return (
                    f"Our model identified {major:,} buildings with major damage "
                    f"out of {total:,} total assessments ({major/total*100:.1f}%). "
                    f"Major damage indicates significant structural compromise visible in post-disaster imagery."
                )
            if "minor" in lower:
                minor = dist.get("minor-damage", 0)
                return (
                    f"The analysis found {minor:,} buildings with minor damage "
                    f"out of {total:,} total assessments ({minor/total*100:.1f}%). "
                    f"Minor damage typically includes superficial issues like broken windows or minor roof damage."
                )
            # Generic count question
            return (
                f"The system has analyzed {total:,} buildings across {len(by_disaster)} disaster events. "
                f"Damage breakdown: {', '.join(f'{k}: {v:,}' for k, v in dist.items())}."
            )

        if any(w in lower for w in ["summary", "overview", "status", "report"]):
            lines = [f"Assessment Overview — {total:,} buildings analyzed across {len(by_disaster)} disasters:\n"]
            for disaster, counts in by_disaster.items():
                disaster_total = sum(counts.values())
                lines.append(f"• {disaster.replace('-', ' ').title()}: {disaster_total:,} buildings assessed")
                for label, count in sorted(counts.items(), key=lambda x: -x[1]):
                    lines.append(f"  - {label}: {count:,} ({count/disaster_total*100:.1f}%)")
            return "\n".join(lines)

        if any(w in lower for w in ["worst", "most damage", "severe", "hardest hit"]):
            worst_disaster = max(by_disaster.items(), key=lambda x: x[1].get("destroyed", 0))
            return (
                f"The hardest-hit disaster was {worst_disaster[0].replace('-', ' ').title()} "
                f"with {worst_disaster[1].get('destroyed', 0):,} buildings destroyed. "
                f"Full breakdown: {', '.join(f'{k}: {v:,}' for k, v in worst_disaster[1].items())}."
            )

        if any(w in lower for w in ["model", "accuracy", "performance", "how well"]):
            return (
                f"The system uses the Qwen2.5-VL-3B-Instruct vision-language model with 4-bit quantization. "
                f"It has processed {total:,} building assessments across {len(by_disaster)} disaster events. "
                f"Each prediction includes a damage classification, confidence score, and natural language rationale "
                f"explaining the visual evidence observed in the pre/post disaster imagery."
            )

    # Default response using whatever context we have
    return (
        f"Based on the assessment database: {context.split(chr(10))[0]}. "
        f"You can ask me about damage statistics, specific disasters, or the prediction methodology."
    )


# ─── /evaluate ───────────────────────────────────────────
# Frontend calls this for single-property detail

@router.get("/evaluate")
async def evaluate_alias(
    propertyId: Optional[str] = Query(None, description="Property/building ID to evaluate"),
    db: AsyncSession = Depends(get_db),
):
    """
    Frontend-compatible alias for property evaluation.

    Frontend calls: GET /evaluate?propertyId=X
    We translate to either:
      - ML bridge prediction lookup (if Supabase configured + ID looks like an ML building ID)
      - Local property detail (fallback)
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
        from uuid import UUID
        return await get_property_detail(UUID(propertyId), db=db)
    except (ValueError, HTTPException) as e:
        raise HTTPException(
            status_code=404,
            detail=f"Property '{propertyId}' not found in either ML or local database"
        )
