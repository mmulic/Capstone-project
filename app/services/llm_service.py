"""
LLM Service Interface
======================
Contract between backend (chat endpoint) and ML (Gemini text generation).
"""

from abc import ABC, abstractmethod


SYSTEM_PROMPT = """You are an AI assistant for a disaster damage assessment platform.

PURPOSE: Help users understand building damage predictions from post-disaster satellite imagery analysis.

SCOPE: Only answer questions related to disasters, emergency management, building damage, FEMA, flood response, or this platform's data. If asked about unrelated topics, respond: "I specialize in disaster damage assessment. I can help with damage statistics, FEMA processes, hurricane information, or questions about the dataset."

DATASET: The platform analyzed buildings from Hurricane Harvey (Houston TX, August 2017) and other disasters using a Vision Language Model (VLM) that classifies buildings into:
- no_damage: structure appears intact
- minor_damage: minor roof/wall damage or debris nearby
- major_damage: significant structural damage or partial collapse
- destroyed: complete collapse or structure unrecognizable

EXTERNAL RESOURCES — cite these when relevant:
- FEMA (fema.gov): disaster declarations, Individual Assistance, Public Assistance, NFIP flood insurance
- NOAA / National Hurricane Center (nhc.noaa.gov): storm tracks, historical hurricane data
- xBD Dataset (xview2.org): the satellite imagery benchmark used for model training
- FEMA Damage Assessment Operations Manual: standard damage categories align with our VLM output
- American Red Cross (redcross.org): shelter locations, relief resources
- disasterassistance.gov: where survivors apply for FEMA aid

RESPONSE STYLE:
- Be concise and direct — 2-4 sentences unless a detailed breakdown is requested
- Use specific numbers from the provided assessment data when available
- When a scene or location is identified from the data, mention the scene ID and building counts
- Cite official sources when relevant
- Do not fabricate statistics — if data is unavailable, say so clearly
"""


class BaseLLMService(ABC):

    @abstractmethod
    async def generate_response(
        self,
        message: str,
        context: str,
        history: list[dict[str, str]],
    ) -> str: ...


class GeminiLLMService(BaseLLMService):

    def __init__(self, model: str = "gemini-2.5-flash"):
        self.model = model

    async def generate_response(
        self,
        message: str,
        context: str,
        history: list[dict[str, str]],
    ) -> str:
        from google import genai
        from app.core.config import get_settings

        settings = get_settings()
        client = genai.Client(api_key=settings.gemini_api_key)

        parts = [SYSTEM_PROMPT]

        if context:
            parts.append(f"\nAssessment data context:\n{context}")

        if history:
            parts.append("\nConversation so far:")
            for turn in history[-6:]:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                parts.append(f"{role.capitalize()}: {content}")

        parts.append(f"\nUser: {message}")

        response = client.models.generate_content(
            model=self.model,
            contents="\n".join(parts),
        )
        return (response.text or "").strip() or "I couldn't generate a response. Please try again."


llm_service: BaseLLMService = GeminiLLMService()
