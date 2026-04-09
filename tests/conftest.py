"""
Test fixtures and configuration.
"""

import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.core.database import Base, get_db


# Use SQLite in-memory for tests (no PostgreSQL required)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_db():
    """Create a fresh in-memory database for each test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Skip PostGIS-specific creation for SQLite tests
    # In real tests against PostgreSQL, use full Base.metadata.create_all
    # For unit tests we just verify the API contract works

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def client():
    """HTTP client for the FastAPI app."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
