"""
Service-level unit tests.
"""

import io
import pytest
from PIL import Image

from app.services.image_preprocessor import image_preprocessor
from app.services.auth_service import auth_service
from app.services.prediction_service import MockPredictionService
from app.services.llm_service import MockLLMService


# ─── Image Preprocessor ──────────────────────────────────

def _make_test_image(width=200, height=200, fmt="JPEG") -> bytes:
    """Generate a test image as bytes."""
    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def test_validate_file_accepts_jpeg():
    img_bytes = _make_test_image()
    errors = image_preprocessor.validate_file(img_bytes, "image/jpeg", "test.jpg")
    assert errors == []


def test_validate_file_rejects_unsupported_mime():
    img_bytes = _make_test_image()
    errors = image_preprocessor.validate_file(img_bytes, "application/pdf", "test.pdf")
    assert any("Unsupported MIME type" in e for e in errors)


def test_validate_file_rejects_oversized():
    big_data = b"x" * (60 * 1024 * 1024)  # 60MB
    errors = image_preprocessor.validate_file(big_data, "image/jpeg", "big.jpg")
    assert any("exceeds" in e for e in errors)


def test_extract_metadata():
    img_bytes = _make_test_image(width=500, height=400)
    meta = image_preprocessor.extract_metadata(img_bytes)
    assert meta.width == 500
    assert meta.height == 400
    assert meta.file_format == "JPEG"


def test_normalize_image():
    img_bytes = _make_test_image(width=2000, height=1500)
    normalized = image_preprocessor.normalize_image(img_bytes)
    img = Image.open(io.BytesIO(normalized))
    # Should fit within 1024x1024
    assert img.width <= 1024
    assert img.height <= 1024


def test_haversine_distance():
    # Houston to Dallas ~360 km
    dist = image_preprocessor.haversine_km(29.76, -95.36, 32.78, -96.80)
    assert 350 < dist < 400


def test_pair_matching_by_id():
    pre = [{"property_id": "A", "latitude": 30.0, "longitude": -95.0}]
    post = [{"property_id": "A", "latitude": 30.0, "longitude": -95.0}]
    matches = image_preprocessor.match_pairs(pre, post)
    assert len(matches) == 1


def test_pair_matching_by_gps():
    pre = [{"latitude": 30.000, "longitude": -95.000}]
    post = [{"latitude": 30.001, "longitude": -95.001}]  # ~140m away
    matches = image_preprocessor.match_pairs(pre, post)
    assert len(matches) == 1


def test_pair_matching_too_far():
    pre = [{"latitude": 30.0, "longitude": -95.0}]
    post = [{"latitude": 31.0, "longitude": -96.0}]  # ~140km away
    matches = image_preprocessor.match_pairs(pre, post)
    assert len(matches) == 0


# ─── Auth Service ────────────────────────────────────────

def test_password_hash_and_verify():
    pw = "test_password_123"
    hashed = auth_service.hash_password(pw)
    assert hashed != pw
    assert auth_service.verify_password(pw, hashed)
    assert not auth_service.verify_password("wrong", hashed)


def test_jwt_create_and_decode():
    token = auth_service.create_access_token("user-123", "test@example.com")
    payload = auth_service.decode_token(token)
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["email"] == "test@example.com"
    assert payload["type"] == "access"


def test_jwt_invalid_token():
    payload = auth_service.decode_token("not-a-real-token")
    assert payload is None


# ─── Prediction Service Mock ─────────────────────────────

@pytest.mark.asyncio
async def test_mock_prediction_service():
    svc = MockPredictionService()
    img_data = _make_test_image()
    result = await svc.predict(img_data, img_data, "test-prop")
    assert result.damage_class is not None
    assert 0.0 <= result.confidence <= 1.0


@pytest.mark.asyncio
async def test_mock_prediction_batch():
    svc = MockPredictionService()
    img_data = _make_test_image()
    results = await svc.predict_batch([(img_data, img_data, "p1"), (img_data, img_data, "p2")])
    assert len(results) == 2


# ─── LLM Service Mock ────────────────────────────────────

@pytest.mark.asyncio
async def test_mock_llm_with_context():
    svc = MockLLMService()
    response = await svc.generate_response(
        message="What is the damage at 123 Main St?",
        context="Property at 123 Main St — Damage: major (90%)",
        history=[],
    )
    assert isinstance(response, str)
    assert len(response) > 0


@pytest.mark.asyncio
async def test_mock_llm_no_context():
    svc = MockLLMService()
    response = await svc.generate_response(
        message="Random query",
        context="",
        history=[],
    )
    assert "don't have" in response.lower() or "no" in response.lower()
