from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import health, ingest
from app.routers.geojson import router as geojson_router
from app.routers.batch_ingest import router as batch_ingest_router
from app.routers.stubs import (
    predict_router, results_router, chat_router, evaluate_router, auth_router
)

settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Disaster Assessment API",
        description=(
            "Backend API for the Automated Disaster Damage Assessment system. "
            "Manages aerial image ingestion, VLM-based damage prediction, "
            "geospatial queries, chatbot interface, and FEMA evaluation."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS — allow frontend dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:5173", "*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ──────────────────────────────────────────
    # Sprint 1: Foundation
    app.include_router(health.router)

    # Sprint 2: Data Ingestion (implemented)
    app.include_router(ingest.router)
    app.include_router(geojson_router)
    app.include_router(batch_ingest_router)

    # Sprints 3-5: Stub endpoints (visible in Swagger, implemented later)
    app.include_router(predict_router)
    app.include_router(results_router)
    app.include_router(chat_router)
    app.include_router(evaluate_router)
    app.include_router(auth_router)

    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "app": settings.app_name,
            "docs": "/docs",
            "health": "/health",
        }

    return app


app = create_app()
