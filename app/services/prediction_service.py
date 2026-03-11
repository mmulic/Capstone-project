"""
Prediction Service Interface
=============================
This is the contract between backend and ML.

Backend owns:  orchestration, storage, retries, API endpoints
ML person owns: implementing predict() with Gemini Vision API

To implement:
    1. Subclass BasePredictionService
    2. Implement predict() — send images to Gemini, parse response
    3. Register your implementation in app/services/__init__.py
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from app.schemas.schemas import PredictionResult, DamageClassEnum
import random


class BasePredictionService(ABC):
    """Abstract interface — ML person implements this."""

    @abstractmethod
    async def predict(
        self, pre_image: bytes, post_image: bytes, property_id: str = ""
    ) -> PredictionResult:
        """
        Analyze a pre/post disaster image pair and return damage assessment.

        Args:
            pre_image: Raw bytes of the pre-disaster image
            post_image: Raw bytes of the post-disaster image
            property_id: Optional property identifier for logging

        Returns:
            PredictionResult with damage_class, confidence, rationale
        """
        ...

    async def predict_batch(
        self, pairs: list[tuple[bytes, bytes, str]]
    ) -> list[PredictionResult]:
        """
        Process multiple image pairs. Default implementation calls predict() sequentially.
        Override for optimized batch processing.
        """
        results = []
        for pre_img, post_img, prop_id in pairs:
            result = await self.predict(pre_img, post_img, prop_id)
            results.append(result)
        return results


class MockPredictionService(BasePredictionService):
    """
    Mock implementation for development and testing.
    Returns randomized but realistic-looking predictions.
    """

    async def predict(
        self, pre_image: bytes, post_image: bytes, property_id: str = ""
    ) -> PredictionResult:
        damage_classes = [
            (DamageClassEnum.NO_DAMAGE, 0.85, "No visible structural changes detected."),
            (DamageClassEnum.MINOR, 0.72, "Minor roof damage and debris observed."),
            (DamageClassEnum.MAJOR, 0.81, "Significant structural damage to walls and roof."),
            (DamageClassEnum.DESTROYED, 0.93, "Structure is collapsed or completely destroyed."),
        ]

        choice = random.choice(damage_classes)
        confidence = round(choice[1] + random.uniform(-0.1, 0.1), 3)
        confidence = max(0.0, min(1.0, confidence))

        return PredictionResult(
            damage_class=choice[0],
            confidence=confidence,
            rationale=choice[2],
            detected_features=["roof_damage", "debris", "structural_collapse"][:random.randint(1, 3)],
            processing_time_ms=random.randint(800, 3000),
        )


# ──────────────────────────────────────────────────────────
# Active service — swap MockPredictionService for the real
# Gemini implementation when the ML person's code is ready
# ──────────────────────────────────────────────────────────
prediction_service: BasePredictionService = MockPredictionService()
