"""
LLM Service Interface
======================
Contract between backend (chat endpoint) and ML (Gemini text generation).

Backend owns:  RAG retrieval, session management, /api/chat endpoint
ML person owns: implementing generate_response() with Gemini
"""

from abc import ABC, abstractmethod


class BaseLLMService(ABC):
    """Abstract interface — ML person implements this with Gemini."""

    @abstractmethod
    async def generate_response(
        self,
        message: str,
        context: str,
        history: list[dict[str, str]],
    ) -> str:
        """
        Generate a response to a user message using retrieved context.

        Args:
            message: The user's question
            context: Retrieved property/prediction data formatted as text
            history: List of {"role": "user"|"assistant", "content": "..."} dicts

        Returns:
            The assistant's response string
        """
        ...


class MockLLMService(BaseLLMService):
    """Mock for dev/testing. Returns canned responses."""

    async def generate_response(
        self,
        message: str,
        context: str,
        history: list[dict[str, str]],
    ) -> str:
        if not context:
            return (
                "I don't have any assessment data for that location. "
                "Could you try a different address or area?"
            )

        return (
            f"Based on the assessment data I found, here's what I can tell you: "
            f"I found relevant property records in the system. "
            f"[Mock response — Gemini integration pending]. "
            f"Your question was: '{message}'"
        )


# Swap for real Gemini implementation when ready
llm_service: BaseLLMService = MockLLMService()
