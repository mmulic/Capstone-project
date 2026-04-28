from __future__ import annotations

import io
import json
import time
from pathlib import Path

from PIL import Image

import google.generativeai as genai

try:
    from .inference import (
        DEFAULT_MODEL_NAME,
        create_client,
        resolve_model_name,
        normalize_response_text,
        _extract_retry_delay_seconds,
    )
    from .labeling import LABEL_ORDER, is_valid_damage_label
except ImportError:
    from inference import (
        DEFAULT_MODEL_NAME,
        create_client,
        resolve_model_name,
        normalize_response_text,
        _extract_retry_delay_seconds,
    )
    from labeling import LABEL_ORDER, is_valid_damage_label


SYSTEM_PROMPT_BUILDING = """
You are an expert disaster damage assessor working with overhead satellite imagery.

You are given two small RGB image crops showing the SAME SINGLE BUILDING:
- First image: BEFORE the disaster
- Second image: AFTER the disaster

Assess the damage to this specific building and assign ONE damage level:
- no_damage: structure intact, no visible changes between before and after
- minor_damage: minor roof/wall damage or debris nearby, but the structure is still standing
- major_damage: significant structural damage, partial collapse, or severe flooding
- destroyed: complete collapse or the structure is no longer visible

Respond ONLY with JSON:
{
  "label": "<one of: no_damage, minor_damage, major_damage, destroyed>",
  "reason": "<one short sentence explaining the assessment>"
}
""".strip()


def _pil_to_part(img: Image.Image) -> dict:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return {"mime_type": "image/png", "data": buf.getvalue()}


def parse_building_response(raw_text: str) -> dict:
    normalized = normalize_response_text(raw_text)
    result = {
        "label": None,
        "reason": None,
        "raw_text": raw_text,
        "normalized_text": normalized,
        "parse_ok": False,
        "error": None,
    }
    try:
        parsed = json.loads(normalized)
    except Exception as exc:
        result["error"] = f"json_parse_error: {exc}"
        return result

    label = parsed.get("label")
    reason = parsed.get("reason")

    if not is_valid_damage_label(label):
        valid_labels = ", ".join(LABEL_ORDER)
        result["error"] = f"invalid_label: {label!r}; expected one of [{valid_labels}]"
        result["reason"] = reason
        return result

    result["label"] = label
    result["reason"] = reason
    result["parse_ok"] = True
    return result


def predict_building_damage(
    pre_crop: Image.Image,
    post_crop: Image.Image,
    preferred_model: str = DEFAULT_MODEL_NAME,
    max_retries: int = 2,
) -> dict:
    """Send pre/post building crops to Gemini and return per-building damage prediction."""
    resolved_model = resolve_model_name(preferred_model)
    model = genai.GenerativeModel(resolved_model)

    pre_part = _pil_to_part(pre_crop)
    post_part = _pil_to_part(post_crop)

    for attempt in range(max_retries + 1):
        try:
            response = model.generate_content(
                [
                    SYSTEM_PROMPT_BUILDING,
                    pre_part,
                    post_part,
                ]
            )
            break
        except Exception as exc:
            message = str(exc)
            if "404" in message:
                return {
                    "label": None,
                    "reason": None,
                    "raw_text": "",
                    "normalized_text": "",
                    "model_used": resolved_model,
                    "parse_ok": False,
                    "error": f"model_unavailable: {resolved_model}",
                }

            is_rate_limited = "429" in message or "RESOURCE_EXHAUSTED" in message
            retry_delay = _extract_retry_delay_seconds(message)
            if is_rate_limited and attempt < max_retries:
                time.sleep((retry_delay or 30.0) + 1.0)
                continue

            return {
                "label": None,
                "reason": None,
                "raw_text": "",
                "normalized_text": "",
                "model_used": resolved_model,
                "parse_ok": False,
                "error": message,
            }

    raw_text = (getattr(response, "text", "") or "").strip()
    parsed = parse_building_response(raw_text)
    parsed["model_used"] = resolved_model
    return parsed
