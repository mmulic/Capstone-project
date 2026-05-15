"""
VLM Analysis Router
====================
POST /api/vlm/analyze — Upload a post-disaster image, send to Gemini Vision,
                        return per-building damage breakdown.

The frontend's DatasetsPage sends a single post-disaster image.
Gemini analyzes the scene and returns a damage assessment.

Response shape (matches what DatasetsPage expects):
{
    "buildings_visible": 5,
    "damage_counts": {"no_damage": 1, "minor_damage": 2, "major_damage": 1, "destroyed": 1},
    "scene_summary": "Analysis shows significant damage...",
    "model_used": "gemini-2.0-flash"
}
"""

import os
import json
import re
import logging

from fastapi import APIRouter, UploadFile, File, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vlm", tags=["VLM Analysis"])

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DEFAULT_MODEL = "gemini-2.0-flash"

# ─── Gemini Scene Analysis Prompt ──────────────────────────────────────────

SCENE_ANALYSIS_PROMPT = """
You are an expert disaster damage assessor analyzing overhead satellite imagery.

You are given a post-disaster satellite image showing a neighborhood or area.
Identify all visible buildings in the image and assess each one's damage level.

For each building you can identify, classify it as one of:
- no_damage: structure appears intact, roof and walls undamaged
- minor_damage: minor roof damage, debris nearby, but structure is standing
- major_damage: significant structural damage, partial collapse, severe flooding
- destroyed: complete collapse, structure no longer recognizable

Respond ONLY with JSON (no markdown, no explanation):
{
    "buildings_visible": <integer — total buildings you can identify>,
    "damage_counts": {
        "no_damage": <count>,
        "minor_damage": <count>,
        "major_damage": <count>,
        "destroyed": <count>
    },
    "scene_summary": "<2-3 sentence description of the overall damage in the scene>"
}
""".strip()


def _normalize_response(text: str) -> str:
    """Strip markdown code fences from Gemini response."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


@router.post("/analyze")
async def analyze_scene(
    post_image: UploadFile = File(..., description="Post-disaster satellite image"),
):
    """
    Upload a post-disaster image for VLM damage analysis.

    Sends the image to Google Gemini Vision which identifies buildings
    and classifies damage levels. Returns counts per damage class
    and a scene summary.
    """
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY is not configured. Add it to the .env file to enable VLM analysis."
        )

    # Read the uploaded image
    image_data = await post_image.read()
    if len(image_data) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image exceeds 50 MB limit")

    # Determine MIME type
    content_type = post_image.content_type or "image/jpeg"
    if content_type not in ("image/jpeg", "image/png", "image/tiff", "image/webp"):
        content_type = "image/jpeg"  # fallback

    try:
        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(DEFAULT_MODEL)

        # Build the image part for Gemini
        image_part = {
            "mime_type": content_type,
            "data": image_data,
        }

        # Call Gemini
        response = model.generate_content(
            [SCENE_ANALYSIS_PROMPT, image_part],
            generation_config={"temperature": 0.1},
        )

        raw_text = (getattr(response, "text", "") or "").strip()
        normalized = _normalize_response(raw_text)

        # Parse the JSON response
        try:
            result = json.loads(normalized)
        except json.JSONDecodeError:
            logger.error(f"Gemini returned non-JSON: {raw_text[:500]}")
            raise HTTPException(
                status_code=502,
                detail=f"Gemini returned an unparseable response. Raw: {raw_text[:300]}"
            )

        # Validate and normalize the response
        buildings_visible = result.get("buildings_visible", 0)
        damage_counts = result.get("damage_counts", {})
        scene_summary = result.get("scene_summary", "")

        # Ensure all damage keys exist
        for key in ["no_damage", "minor_damage", "major_damage", "destroyed"]:
            if key not in damage_counts:
                damage_counts[key] = 0

        # Ensure counts are integers
        damage_counts = {k: int(v) for k, v in damage_counts.items()}

        # If buildings_visible is 0 but damage_counts has values, fix it
        total_from_counts = sum(damage_counts.values())
        if buildings_visible == 0 and total_from_counts > 0:
            buildings_visible = total_from_counts

        return {
            "buildings_visible": buildings_visible,
            "damage_counts": damage_counts,
            "scene_summary": scene_summary,
            "model_used": DEFAULT_MODEL,
        }

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Gemini API error: {error_msg}")

        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            raise HTTPException(
                status_code=429,
                detail="Gemini API rate limit reached. Please wait a moment and try again."
            )
        if "403" in error_msg or "PERMISSION_DENIED" in error_msg:
            raise HTTPException(
                status_code=403,
                detail="Gemini API key is invalid or doesn't have access. Check GEMINI_API_KEY in .env."
            )

        raise HTTPException(
            status_code=502,
            detail=f"Gemini API error: {error_msg[:300]}"
        )
