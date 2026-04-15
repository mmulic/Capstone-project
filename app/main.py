from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.rate_limit import RateLimitMiddleware
from app.core.logging_config import configure_logging, RequestLoggingMiddleware
from app.routers import health, ingest
from app.routers.geojson import router as geojson_router
from app.routers.batch_ingest import router as batch_ingest_router
from app.routers.predict import router as predict_router
from app.routers.results import router as results_router
from app.routers.chat import router as chat_router
from app.routers.stats import router as stats_router
from app.routers.evaluate import router as evaluate_router
from app.routers.auth import router as auth_router
from app.routers.ml_bridge import router as ml_bridge_router
from app.routers.frontend_compat import router as frontend_compat_router

settings = get_settings()
configure_logging(level="DEBUG" if settings.debug else "INFO")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Disaster Assessment API",
        description=(
            "Backend API for the Automated Disaster Damage Assessment system. "
            "Manages aerial image ingestion, VLM-based damage prediction, "
            "geospatial queries, chatbot interface, and FEMA evaluation."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── Middleware ───────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:5173", "*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    # ── Routers ──────────────────────────────────────────
    # Sprint 1: Foundation
    app.include_router(health.router)

    # Sprint 2: Data Ingestion
    app.include_router(ingest.router)
    app.include_router(geojson_router)
    app.include_router(batch_ingest_router)

    # Sprint 3: Predictions + Results
    app.include_router(predict_router)
    app.include_router(results_router)

    # Sprint 4: Chatbot + Stats
    app.include_router(chat_router)
    app.include_router(stats_router)

    # Sprint 5: Evaluation + Auth
    app.include_router(evaluate_router)
    app.include_router(auth_router)

    # Bridge to ML teammate's Supabase database
    app.include_router(ml_bridge_router)

    # Frontend compatibility aliases (no /api prefix — frontend calls these at root)
    app.include_router(frontend_compat_router)

    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "app": settings.app_name,
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/health",
        }

    return app


app = create_app()
