from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import get_db
from app.schemas.schemas import HealthResponse

router = APIRouter(tags=["Health"])
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check — verifies app is running and DB is connected."""
    db_status = "disconnected"
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "error"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        version="0.1.0",
        environment=settings.app_env,
        database=db_status,
    )
