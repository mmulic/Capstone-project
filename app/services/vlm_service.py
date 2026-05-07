"""Scene-level VLM damage assessment using Gemini.

Accepts raw pre/post image bytes for a full scene, sends both to Gemini,
and returns a per-building damage breakdown with an overall scene summary.
No building polygon labels are required — Gemini detects structures visually.
"""

from __future__ import annotations

import io
import json
import re
import time

from PIL import Image
from google import genai
from google.genai import types

from app.core.config import get_settings

_SCENE_PROMPT = """
You are a strict disaster damage assessor analyzing a post-disaster aerial image.

Count every building or structure visible. Carefully inspect each one for ANY signs of damage:
  destroyed    — complete collapse, missing roof, structure no longer recognisable
  major_damage — large holes in roof, partial collapse, severe flooding inside structure, walls missing
  minor_damage — debris on roof, small holes, broken windows, minor flooding nearby, displaced materials
  no_damage    — ONLY assign this if the structure shows absolutely zero visible damage

Be conservative: if there is ANY doubt, assign the worse category. Do NOT default to no_damage.
Flooding nearby a building, debris around it, or discoloration counts as at least minor_damage.

Respond ONLY with valid JSON:
{
  "buildings_visible": <total integer count>,
  "damage_counts": {
    "no_damage": <int>,
    "minor_damage": <int>,
    "major_damage": <int>,
    "destroyed": <int>
  },
  "scene_summary": "<one sentence>"
}
""".strip()

_VALID_LABELS = {"no_damage", "minor_damage", "major_damage", "destroyed"}
_DEFAULT_MODEL = "gemini-2.5-flash"


def _pil_to_part(img: Image.Image) -> types.Part:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return types.Part.from_bytes(data=buf.getvalue(), mime_type="image/png")


def _bytes_to_pil(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGB")


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_response(raw: str) -> dict:
    try:
        parsed = json.loads(_strip_fences(raw))
    except Exception as exc:
        return {"error": f"json_parse_error: {exc}", "buildings_visible": 0, "damage_counts": {}, "scene_summary": ""}

    return {
        "buildings_visible": parsed.get("buildings_visible", 0),
        "damage_counts": parsed.get("damage_counts", {}),
        "scene_summary": parsed.get("scene_summary", ""),
        "error": None,
    }


def analyze_scene(
    post_image_bytes: bytes,
    model_name: str = _DEFAULT_MODEL,
    max_retries: int = 2,
) -> dict:
    """Send a pre/post scene image pair to Gemini and return per-building damage results.

    Returns:
        {
            "buildings": [{"building_index", "label", "reason", "label_valid"}, ...],
            "scene_summary": str,
            "model_used": str,
            "error": str | None,
        }
    """
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)

    post_part = _pil_to_part(_bytes_to_pil(post_image_bytes))

    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[_SCENE_PROMPT, post_part],
            )
            break
        except Exception as exc:
            msg = str(exc)
            if "404" in msg:
                return {
                    "buildings": [],
                    "scene_summary": "",
                    "model_used": model_name,
                    "error": f"model_unavailable: {model_name}",
                }
            is_rate_limited = "429" in msg or "RESOURCE_EXHAUSTED" in msg
            if is_rate_limited:
                # Don't retry quota errors — fail fast so the frontend shows an error
                return {
                    "buildings_visible": 0,
                    "damage_counts": {},
                    "scene_summary": "",
                    "model_used": model_name,
                    "error": "API quota exceeded. Please try again later or check your Gemini API billing.",
                }
            return {
                "buildings": [],
                "scene_summary": "",
                "model_used": model_name,
                "error": msg,
            }

    raw = (response.text or "").strip()
    result = _parse_response(raw)
    result["model_used"] = model_name
    return result
