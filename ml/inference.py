from __future__ import annotations

import os
import re

import google.generativeai as genai

DEFAULT_MODEL_NAME = "gemini-2.0-flash"

# Models tried in order if the preferred model is unavailable
_FALLBACK_MODELS = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]


def create_client() -> None:
    """Configure the Gemini client with the API key from the environment."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    genai.configure(api_key=api_key)


def resolve_model_name(preferred: str) -> str:
    """Return the preferred model name, falling back to defaults if needed."""
    if preferred:
        return preferred
    return DEFAULT_MODEL_NAME


def normalize_response_text(text: str) -> str:
    """Strip markdown code fences so the result can be parsed as plain JSON."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _extract_retry_delay_seconds(error_message: str) -> float | None:
    """Parse the retry delay in seconds from a rate-limit error message."""
    match = re.search(r"retry[_ ]after[_ ]?(\d+)", error_message, re.IGNORECASE)
    if match:
        return float(match.group(1))
    # Also handles "retryDelay: '30s'" style
    match = re.search(r"retryDelay['\"]?\s*:\s*['\"]?(\d+)s?", error_message, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return None
