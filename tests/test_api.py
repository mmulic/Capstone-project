"""
API endpoint smoke tests.
Verifies routes are registered and respond correctly.
"""

import pytest


@pytest.mark.asyncio
async def test_root_endpoint(client):
    """Root should return app info."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "app" in data
    assert "docs" in data


@pytest.mark.asyncio
async def test_openapi_schema(client):
    """OpenAPI schema should be available."""
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "paths" in schema


@pytest.mark.asyncio
async def test_swagger_docs(client):
    """Swagger UI should be available."""
    response = await client.get("/docs")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_all_sprint_endpoints_registered(client):
    """Verify all expected endpoints are in the OpenAPI schema."""
    response = await client.get("/openapi.json")
    paths = response.json()["paths"]

    expected = [
        "/health",
        "/api/ingest",
        "/api/ingest/batch",
        "/api/geojson",
        "/api/predict",
        "/api/results",
        "/api/properties/{property_id}",
        "/api/chat",
        "/api/stats",
        "/api/evaluate",
        "/api/auth/register",
        "/api/auth/login",
    ]
    for endpoint in expected:
        assert endpoint in paths, f"Missing endpoint: {endpoint}"
