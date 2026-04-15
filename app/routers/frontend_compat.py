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
    We translate to our internal chat pipeline (RAG retrieval + LLM).
    """
    message = payload.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=422, detail="message field is required")

    # Frontend may send history as an array of {role, content} or just an object
    history_raw = payload.get("history", [])
    if isinstance(history_raw, list):
        history = [
            {"role": h.get("role", "user"), "content": h.get("content", "")}
            for h in history_raw if isinstance(h, dict)
        ]
    else:
        history = []

    # Get RAG context (works against local DB; ML data could be added later)
    context_data = await rag_service.retrieve_context(query=message, db=db)
    formatted_context = context_data.get("formatted_context", "")

    # Generate response via LLM service (currently mock; ML teammate's Gemini code drops in later)
    response_text = await llm_service.generate_response(
        message=message,
        context=formatted_context,
        history=history,
    )

    # Frontend likely expects {response, ...} but be flexible — return both common shapes
    return {
        "response": response_text,
        "answer": response_text,  # alias in case frontend reads .answer
        "context_used": {
            "strategy": context_data.get("strategy"),
            "num_results": len(context_data.get("results", [])),
            "summary": context_data.get("summary"),
        },
    }


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
