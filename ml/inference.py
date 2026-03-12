import json
import io
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

try:
    from .labeling import LABEL_ORDER, is_valid_damage_label
except ImportError:
    from labeling import LABEL_ORDER, is_valid_damage_label

load_dotenv()

DEFAULT_MODEL_NAME = "gemini-2.5-flash"

SYSTEM_PROMPT = """
You are an expert disaster damage assessor working with overhead satellite imagery.

You are given two RGB image chips of the SAME location:
- First image: BEFORE the hurricane
- Second image: AFTER the hurricane

Assign ONE overall damage level using this label set:
- no_damage
- minor_damage
- major_damage
- destroyed

Respond ONLY with JSON:
{
  "label": "<label>",
  "reason": "<one short sentence>"
}
""".strip()

BUILDING_SYSTEM_PROMPT = """
You are an expert disaster damage assessor working with overhead satellite imagery.

You are given two RGB image crops focused on one building:
- First image: BEFORE the disaster
- Second image: AFTER the disaster

Classify damage for the central building only using exactly one label:
- no_damage
- minor_damage
- major_damage
- destroyed

Ignore surrounding buildings unless they are inseparable from the central structure.

Respond ONLY with JSON:
{
  "label": "<label>",
  "reason": "<one short sentence>"
}
""".strip()


def get_api_key() -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY in your environment or .env first.")
    return api_key


def create_client(api_key: str | None = None) -> genai.Client:
    return genai.Client(api_key=api_key or get_api_key())


def create_vertex_client(project: str, location: str) -> genai.Client:
    return genai.Client(vertexai=True, project=project, location=location)


def _base_model_name(name: str) -> str:
    return name.removeprefix("models/")


def resolve_model_name(client: genai.Client, preferred: str = DEFAULT_MODEL_NAME) -> str:
    """Pick a valid Gemini model that supports generateContent."""
    preferred_base = _base_model_name(preferred)
    preferred_full = f"models/{preferred_base}"

    try:
        models = list(client.models.list())
    except Exception:
        return preferred_base

    supported = []
    for model in models:
        name = getattr(model, "name", None)
        actions = getattr(model, "supported_actions", None) or []
        if name and "generateContent" in actions:
            supported.append(name)

    if not supported:
        return preferred_base

    if preferred_full in supported:
        return preferred_base

    preferred_order = [
        "models/gemini-2.5-flash",
        "models/gemini-2.0-flash",
        "models/gemini-1.5-flash",
    ]
    for candidate in preferred_order:
        if candidate in supported:
            return _base_model_name(candidate)

    for candidate in supported:
        if "/gemini" in candidate:
            return _base_model_name(candidate)

    return _base_model_name(supported[0])


def normalize_response_text(raw_text: str) -> str:
    raw_text = (raw_text or "").strip()
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        if lines and lines[0].strip().lower() == "json":
            lines = lines[1:]
        raw_text = "\n".join(lines).strip()
    return raw_text


def parse_prediction_response(raw_text: str) -> dict:
    normalized_text = normalize_response_text(raw_text)
    result = {
        "label": None,
        "reason": None,
        "raw_text": raw_text,
        "normalized_text": normalized_text,
        "parse_ok": False,
        "error": None,
    }

    try:
        parsed = json.loads(normalized_text)
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


def pil_image_to_png_bytes(image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _extract_retry_delay_seconds(message: str) -> float | None:
    retry_match = re.search(r"retry in ([0-9]+(?:\.[0-9]+)?)s?", message, flags=re.IGNORECASE)
    if retry_match:
        return float(retry_match.group(1))

    retry_match = re.search(r"'retryDelay': '([0-9]+)s'", message)
    if retry_match:
        return float(retry_match.group(1))

    return None


def predict_damage(
    pre_path: Path,
    post_path: Path,
    preferred_model: str = DEFAULT_MODEL_NAME,
    client: genai.Client | None = None,
    max_retries: int = 2,
) -> dict:
    pre_path = Path(pre_path)
    post_path = Path(post_path)

    if not pre_path.exists():
        return {
            "label": None,
            "reason": None,
            "raw_text": "",
            "normalized_text": "",
            "model_used": None,
            "parse_ok": False,
            "error": f"missing_pre_image: {pre_path}",
        }

    if not post_path.exists():
        return {
            "label": None,
            "reason": None,
            "raw_text": "",
            "normalized_text": "",
            "model_used": None,
            "parse_ok": False,
            "error": f"missing_post_image: {post_path}",
        }

    client = client or create_client()
    resolved_model = resolve_model_name(client, preferred_model)

    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=resolved_model,
                contents=[
                    types.Part.from_text(text=SYSTEM_PROMPT),
                    types.Part.from_bytes(data=pre_path.read_bytes(), mime_type="image/png"),
                    types.Part.from_bytes(data=post_path.read_bytes(), mime_type="image/png"),
                ],
            )
            break
        except errors.ClientError as exc:
            message = str(exc)
            if "404" in message:
                message = (
                    f"model_unavailable: {resolved_model}; "
                    "try updating the preferred model or inspect ListModels output"
                )
                return {
                    "label": None,
                    "reason": None,
                    "raw_text": "",
                    "normalized_text": "",
                    "model_used": resolved_model,
                    "parse_ok": False,
                    "error": message,
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
        except Exception as exc:
            return {
                "label": None,
                "reason": None,
                "raw_text": "",
                "normalized_text": "",
                "model_used": resolved_model,
                "parse_ok": False,
                "error": str(exc),
            }

    raw_text = (getattr(response, "text", "") or "").strip()
    parsed = parse_prediction_response(raw_text)
    parsed["model_used"] = resolved_model
    return parsed


def predict_damage_bytes(
    pre_bytes: bytes,
    post_bytes: bytes,
    preferred_model: str = DEFAULT_MODEL_NAME,
    client: genai.Client | None = None,
    max_retries: int = 2,
    system_prompt: str = SYSTEM_PROMPT,
) -> dict:
    client = client or create_client()
    resolved_model = resolve_model_name(client, preferred_model)

    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=resolved_model,
                contents=[
                    types.Part.from_text(text=system_prompt),
                    types.Part.from_bytes(data=pre_bytes, mime_type="image/png"),
                    types.Part.from_bytes(data=post_bytes, mime_type="image/png"),
                ],
            )
            break
        except errors.ClientError as exc:
            message = str(exc)
            if "404" in message:
                message = (
                    f"model_unavailable: {resolved_model}; "
                    "try updating the preferred model or inspect ListModels output"
                )
                return {
                    "label": None,
                    "reason": None,
                    "raw_text": "",
                    "normalized_text": "",
                    "model_used": resolved_model,
                    "parse_ok": False,
                    "error": message,
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
        except Exception as exc:
            return {
                "label": None,
                "reason": None,
                "raw_text": "",
                "normalized_text": "",
                "model_used": resolved_model,
                "parse_ok": False,
                "error": str(exc),
            }

    raw_text = (getattr(response, "text", "") or "").strip()
    parsed = parse_prediction_response(raw_text)
    parsed["model_used"] = resolved_model
    return parsed
