"""Tests for RAG retrieval service query analysis."""

from app.services.rag_service import rag_service
from app.models.models import DamageClass


def test_is_stats_query():
    assert rag_service._is_stats_query("how many properties were destroyed")
    assert rag_service._is_stats_query("give me a summary")
    assert rag_service._is_stats_query("what's the total count")
    assert not rag_service._is_stats_query("damage at 123 Main St")


def test_extract_address():
    assert rag_service._extract_address("what is the damage at 123 main street") == "123 main street"
    assert rag_service._extract_address("damage at oak avenue") == "oak avenue"
    assert rag_service._extract_address("hello world") is None


def test_extract_damage_level():
    assert rag_service._extract_damage_level("show me destroyed properties") == DamageClass.DESTROYED
    assert rag_service._extract_damage_level("any major damage") == DamageClass.MAJOR
    assert rag_service._extract_damage_level("minor issues") == DamageClass.MINOR
    assert rag_service._extract_damage_level("undamaged buildings") == DamageClass.NO_DAMAGE
    assert rag_service._extract_damage_level("hello") is None


def test_format_for_llm_empty():
    result = rag_service._format_for_llm([])
    assert "No assessment data" in result


def test_format_for_llm_with_records():
    records = [
        {
            "address": "123 Main St",
            "latitude": 29.76,
            "longitude": -95.36,
            "damage_class": "major_damage",
            "confidence": 0.85,
            "rationale": "Roof collapse visible",
        }
    ]
    formatted = rag_service._format_for_llm(records)
    assert "123 Main St" in formatted
    assert "major_damage" in formatted
    assert "85" in formatted
