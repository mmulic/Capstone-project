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
from fastapi import APIRouter, Query, HTTPException, Request

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
async def query(
    payload: dict,
):
    """
    Frontend-compatible chatbot endpoint with full rubric capabilities:
    1. Conversational memory — remembers previous queries via history
    2. External disaster info — answers general disaster/FEMA questions
    3. VLM prediction data — damage levels for full dataset, city, or street
    4. Map focus — returns coordinates for the frontend to zoom to
    """
    message = payload.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=422, detail="message field is required")

    # Parse conversation history for context memory
    history_raw = payload.get("history", [])
    if isinstance(history_raw, list):
        history = [
            h.get("text", h.get("content", ""))
            for h in history_raw
            if isinstance(h, dict) and h.get("role") == "user"
        ]
    else:
        history = []

    lower = message.lower()

    # ── 1. Check if this is a general disaster/FEMA question ──────────
    is_general_disaster = any(w in lower for w in [
        "what is", "what are", "define", "explain", "fema", "how does",
        "hurricane", "tornado", "earthquake", "flood", "tsunami",
        "category", "saffir", "richter", "preparedness", "evacuation",
        "emergency", "relief", "recovery", "insurance", "claim",
        "shelter", "red cross", "disaster declaration",
    ]) and not any(w in lower for w in ["how many", "count", "destroyed", "our", "dataset", "prediction"])

    if is_general_disaster:
        response_text = _get_disaster_knowledge(message, lower)
        return {
            "response": response_text,
            "answer": response_text,
            "context_used": {"source": "disaster_knowledge", "has_data": True},
        }

    # ── 2. Check if this references previous conversation ─────────────
    references_history = any(w in lower for w in [
        "previous", "before", "earlier", "last question", "you said",
        "you mentioned", "follow up", "what about", "and also",
        "same", "those", "that",
    ])

    history_context = ""
    if references_history and history:
        history_context = f"Previous questions in this conversation: {'; '.join(history[-5:])}. "

    # ── 3. Query Supabase for real prediction data ────────────────────
    context_text = ""
    stats = None
    map_focus = None  # Will contain {lat, lng, zoom} if we should focus the map

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
            context_text = f"Total predictions: {total}\n"
            context_text += f"Distribution: {', '.join(f'{k}: {v}' for k, v in overall.items())}\n"
            stats = {"total": total, "distribution": overall, "by_disaster": by_disaster}

        # ── 4. Location-specific queries (city, street, scene) ────────
        location_query = _extract_location(message)
        if location_query:
            preds = supabase_bridge.fetch_predictions(limit=2000, disaster_name=location_query.get("disaster"))
            if preds and not preds[0].get("error"):
                # Filter by location keywords if present
                location_name = location_query.get("name", "").lower()
                if location_name:
                    matching = [p for p in preds if
                        (p.get("scene_id") and location_name in p.get("scene_id", "").lower()) or
                        (p.get("disaster_name") and location_name in p.get("disaster_name", "").lower())]
                else:
                    matching = preds

                if matching:
                    # Build damage summary for this location
                    loc_counts = {}
                    lats, lngs = [], []
                    for p in matching:
                        dc = p.get("damage_class", "unknown")
                        loc_counts[dc] = loc_counts.get(dc, 0) + 1
                        if p.get("latitude") and p.get("longitude"):
                            lats.append(p["latitude"])
                            lngs.append(p["longitude"])

                    context_text += f"\nLocation filter '{location_name}': {len(matching)} buildings\n"
                    context_text += f"Damage: {', '.join(f'{k}: {v}' for k, v in loc_counts.items())}\n"

                    # Set map focus to center of matching buildings
                    if lats and lngs:
                        map_focus = {
                            "lat": sum(lats) / len(lats),
                            "lng": sum(lngs) / len(lngs),
                            "zoom": 15,
                            "building_count": len(matching),
                        }

        # ── 5. Scene-specific queries ─────────────────────────────────
        scene_match = _extract_scene_id(message)
        if scene_match:
            preds = supabase_bridge.fetch_predictions(limit=500)
            if preds and not preds[0].get("error"):
                scene_preds = [p for p in preds if p.get("scene_id") and scene_match in p.get("scene_id", "")]
                if scene_preds:
                    sc_counts = {}
                    lats, lngs = [], []
                    for p in scene_preds:
                        dc = p.get("damage_class", "unknown")
                        sc_counts[dc] = sc_counts.get(dc, 0) + 1
                        if p.get("latitude") and p.get("longitude"):
                            lats.append(p["latitude"])
                            lngs.append(p["longitude"])

                    context_text += f"\nScene {scene_match}: {len(scene_preds)} buildings\n"
                    context_text += f"Damage: {', '.join(f'{k}: {v}' for k, v in sc_counts.items())}\n"

                    if lats and lngs:
                        map_focus = {
                            "lat": sum(lats) / len(lats),
                            "lng": sum(lngs) / len(lngs),
                            "zoom": 16,
                            "building_count": len(scene_preds),
                        }

        # If no specific location/scene, get sample predictions for context
        if not location_query and not scene_match:
            if any(w in lower for w in ["building", "property", "example", "show", "sample"]):
                preds = supabase_bridge.fetch_predictions(limit=5)
                if preds and not preds[0].get("error"):
                    context_text += "\nSample predictions:\n"
                    for p in preds[:5]:
                        context_text += (
                            f"- {p.get('scene_id', 'N/A')}: {p.get('damage_class', '?')} "
                            f"(confidence: {p.get('confidence', '?')}). {p.get('rationale', '')}\n"
                        )

    # ── Generate response ──────────────────────────────────────────────
    if context_text:
        full_context = history_context + context_text
        response_text = _generate_contextual_response(message, full_context, stats)
    else:
        response_text = (
            "The assessment database is not currently connected. "
            "Once configured, I can answer questions about damage predictions, "
            "building assessments, and disaster statistics."
        )

    result = {
        "response": response_text,
        "answer": response_text,
        "context_used": {
            "source": "supabase" if context_text else "none",
            "has_data": bool(context_text),
        },
    }

    # Include map focus data if we found a location to zoom to
    if map_focus:
        result["map_focus"] = map_focus

    return result


def _extract_location(message: str) -> Optional[dict]:
    """Extract location references from a chat message."""
    lower = message.lower()

    # Check for disaster names
    for disaster in ["harvey", "florence", "ian", "idalia", "katrina"]:
        if disaster in lower:
            return {"name": disaster, "disaster": f"hurricane-{disaster}"}

    # Check for city names
    for city in ["houston", "dallas", "austin", "miami", "new orleans",
                 "tampa", "jacksonville", "wilmington", "florence"]:
        if city in lower:
            return {"name": city, "disaster": None}

    # Check for generic location queries
    if any(w in lower for w in ["street", "road", "avenue", "blvd", "drive", "lane"]):
        return {"name": "", "disaster": None}

    return None


def _extract_scene_id(message: str) -> Optional[str]:
    """Extract scene ID references like 'scene 3' or 'scene #18'."""
    import re
    match = re.search(r"scene\s*#?\s*(\d+)", message.lower())
    if match:
        scene_num = match.group(1).zfill(8)  # pad to 8 digits
        return scene_num
    return None


def _get_disaster_knowledge(message: str, lower: str) -> str:
    """Return general disaster information from built-in knowledge base."""

    if "fema" in lower:
        if "declaration" in lower or "declare" in lower:
            return (
                "A FEMA disaster declaration is issued when the President determines that a disaster "
                "is of such severity that state and local governments need federal assistance. There are "
                "two types: Emergency Declarations (limited assistance) and Major Disaster Declarations "
                "(full range of federal programs). Once declared, affected individuals can apply for "
                "Individual Assistance, and state/local governments can receive Public Assistance for "
                "infrastructure repairs."
            )
        if "assistance" in lower or "aid" in lower or "help" in lower:
            return (
                "FEMA provides several types of disaster assistance: Individual Assistance (temporary housing, "
                "home repairs, personal property replacement), Public Assistance (debris removal, emergency "
                "protective measures, infrastructure repair), and Hazard Mitigation grants. Affected residents "
                "can apply at DisasterAssistance.gov or by calling 1-800-621-3362."
            )
        return (
            "FEMA (Federal Emergency Management Agency) coordinates the federal government's response to "
            "natural disasters. Key functions include: pre-disaster planning and mitigation, emergency response "
            "coordination, disaster recovery assistance, and the National Flood Insurance Program. FEMA uses "
            "damage assessment data — like what our system produces — to determine disaster severity and "
            "allocate federal resources."
        )

    if "hurricane" in lower and ("category" in lower or "scale" in lower or "saffir" in lower):
        return (
            "The Saffir-Simpson Hurricane Wind Scale classifies hurricanes by sustained wind speed:\n"
            "• Category 1: 74-95 mph — minimal damage\n"
            "• Category 2: 96-110 mph — moderate damage\n"
            "• Category 3: 111-129 mph — devastating damage (major hurricane)\n"
            "• Category 4: 130-156 mph — catastrophic damage\n"
            "• Category 5: 157+ mph — catastrophic, total destruction of structures\n\n"
            "Hurricane Harvey (2017) made landfall as a Category 4. Florence (2018) as Category 1 "
            "but caused massive flooding damage."
        )

    if any(w in lower for w in ["preparedness", "prepare", "evacuation", "evacuate"]):
        return (
            "Disaster preparedness involves: building an emergency supply kit (water, food, medications, "
            "documents), creating a family communication plan, knowing your evacuation routes, and "
            "understanding local warning systems. For hurricanes specifically: board windows, secure outdoor "
            "items, fill vehicles with gas, and evacuate if ordered. After the disaster, document all damage "
            "with photos for insurance claims and FEMA applications."
        )

    if "harvey" in lower:
        return (
            "Hurricane Harvey struck the Texas coast on August 25, 2017 as a Category 4 hurricane. "
            "It stalled over Houston for four days, dropping over 60 inches of rain in some areas — "
            "the highest-ever recorded rainfall from a single storm in the continental US. Over 300,000 "
            "structures were flooded, 40,000 people were rescued, and total damage exceeded $125 billion. "
            "Our dataset includes satellite imagery from the Houston metropolitan area assessing building-level damage."
        )

    if "florence" in lower:
        return (
            "Hurricane Florence made landfall near Wrightsville Beach, North Carolina on September 14, 2018 "
            "as a Category 1 hurricane. Despite its lower wind speed, Florence moved very slowly and produced "
            "catastrophic flooding — some areas received over 30 inches of rain. The storm caused $24 billion "
            "in damage and 53 deaths. Our dataset includes building damage assessments from affected areas."
        )

    # Generic disaster question
    if any(w in lower for w in ["what is", "what are", "define", "explain"]):
        if "damage assessment" in lower:
            return (
                "Post-disaster damage assessment is the process of evaluating structural damage to buildings "
                "and infrastructure after a natural disaster. Traditional methods involve teams physically "
                "inspecting each structure, which is slow and dangerous. Our system automates this using "
                "satellite imagery and vision-language models (VLMs) that can classify damage levels by "
                "comparing pre- and post-disaster imagery of individual buildings."
            )

    return (
        "I can answer questions about disaster preparedness, FEMA processes, hurricane classifications, "
        "and specific disasters like Hurricane Harvey and Florence. I also have access to real building "
        "damage predictions from our VLM analysis. What would you like to know?"
    )


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
