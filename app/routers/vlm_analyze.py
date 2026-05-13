"""
VLM Analysis Router
====================
POST /api/vlm/analyze — Upload a pre+post disaster image pair, send to Gemini Vision,
                        return per-building damage breakdown via comparison analysis.

When only post_image is provided, Gemini assesses absolute damage from the post scene.
When both pre_image and post_image are provided, Gemini compares the two to identify
changes and classify damage more accurately.

Response shape:
{
    "buildings_visible": 5,
    "damage_counts": {"no_damage": 1, "minor_damage": 2, "major_damage": 1, "destroyed": 1},
    "scene_summary": "Analysis shows significant damage...",
    "model_used": "gemini-2.0-flash",
    "comparison_mode": true
}
"""

import os
import json
import re
import logging
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vlm", tags=["VLM Analysis"])

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DEFAULT_MODEL = "gemini-2.0-flash"

# ─── Prompts ───────────────────────────────────────────────────────────────

POST_ONLY_PROMPT = """
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

COMPARISON_PROMPT = """
You are an expert disaster damage assessor performing a before-and-after satellite imagery analysis.

You are given TWO overhead satellite images of the same area:
  IMAGE 1: Pre-disaster (before the event)
  IMAGE 2: Post-disaster (after the event)

Compare the two images carefully. For each building visible in the pre-disaster image,
determine what happened to it in the post-disaster image and classify it as:
- no_damage: structure looks the same as before — no visible change
- minor_damage: slight changes — minor roof damage, debris nearby, but structure intact
- major_damage: significant changes — partial collapse, flooding, severe structural compromise
- destroyed: structure is gone or completely unrecognizable compared to before

Respond ONLY with JSON (no markdown, no explanation):
{
    "buildings_visible": <integer — buildings identifiable in pre-disaster image>,
    "damage_counts": {
        "no_damage": <count>,
        "minor_damage": <count>,
        "major_damage": <count>,
        "destroyed": <count>
    },
    "scene_summary": "<2-3 sentence description comparing before vs after, highlighting key changes>"
}
""".strip()


def _normalize_response(text: str) -> str:
    """Strip markdown code fences from Gemini response."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _safe_mime(content_type: Optional[str]) -> str:
    allowed = ("image/jpeg", "image/png", "image/tiff", "image/webp")
    return content_type if content_type in allowed else "image/jpeg"


@router.post("/analyze")
async def analyze_scene(
    post_image: UploadFile = File(..., description="Post-disaster satellite image"),
    pre_image: Optional[UploadFile] = File(None, description="Pre-disaster satellite image (optional, enables comparison mode)"),
):
    """
    Upload a pre/post disaster image pair for VLM damage analysis.

    - **post_image** (required): the post-disaster satellite image
    - **pre_image** (optional): the pre-disaster satellite image

    When both images are provided, Gemini performs a side-by-side comparison to detect
    changes and classify damage more accurately (comparison mode).
    When only post_image is provided, Gemini assesses damage from the post scene alone.

    Returns counts per damage class and a scene summary.
    """
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY is not configured. Add it to the .env file to enable VLM analysis."
        )

    # Read post-disaster image
    post_data = await post_image.read()
    if len(post_data) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Post-disaster image exceeds 50 MB limit")

    post_mime = _safe_mime(post_image.content_type)

    # Read pre-disaster image if provided
    pre_data = None
    pre_mime = None
    if pre_image and pre_image.filename:
        pre_data = await pre_image.read()
        if len(pre_data) > 50 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Pre-disaster image exceeds 50 MB limit")
        pre_mime = _safe_mime(pre_image.content_type)

    comparison_mode = pre_data is not None

    try:
        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(DEFAULT_MODEL)

        if comparison_mode:
            # Send pre + post to Gemini with comparison prompt
            prompt = COMPARISON_PROMPT
            content = [
                prompt,
                "IMAGE 1 — Pre-disaster:",
                {"mime_type": pre_mime, "data": pre_data},
                "IMAGE 2 — Post-disaster:",
                {"mime_type": post_mime, "data": post_data},
            ]
        else:
            prompt = POST_ONLY_PROMPT
            content = [
                prompt,
                {"mime_type": post_mime, "data": post_data},
            ]

        response = model.generate_content(content, generation_config={"temperature": 0.1})

        raw_text = (getattr(response, "text", "") or "").strip()
        normalized = _normalize_response(raw_text)

        try:
            result = json.loads(normalized)
        except json.JSONDecodeError:
            logger.error(f"Gemini returned non-JSON: {raw_text[:500]}")
            raise HTTPException(
                status_code=502,
                detail=f"Gemini returned an unparseable response. Raw: {raw_text[:300]}"
            )

        buildings_visible = result.get("buildings_visible", 0)
        damage_counts = result.get("damage_counts", {})
        scene_summary = result.get("scene_summary", "")

        for key in ["no_damage", "minor_damage", "major_damage", "destroyed"]:
            if key not in damage_counts:
                damage_counts[key] = 0

        damage_counts = {k: int(v) for k, v in damage_counts.items()}

        total_from_counts = sum(damage_counts.values())
        if buildings_visible == 0 and total_from_counts > 0:
            buildings_visible = total_from_counts

        return {
            "buildings_visible": buildings_visible,
            "damage_counts": damage_counts,
            "scene_summary": scene_summary,
            "model_used": DEFAULT_MODEL,
            "comparison_mode": comparison_mode,
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
