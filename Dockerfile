# ==================================================================
# Multi-stage production Dockerfile (BE-024)
# Stage 1: Builder — installs dependencies
# Stage 2: Runtime — minimal image with only what's needed to run
# ==================================================================

# ─── Stage 1: Builder ─────────────────────────────────────────────
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install dependencies into a virtual env we'll copy to runtime
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# ─── Stage 2: Runtime ─────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Runtime system deps only (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser ./app ./app
COPY --chown=appuser:appuser ./alembic ./alembic
COPY --chown=appuser:appuser ./alembic.ini ./alembic.ini

USER appuser

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production: no --reload, multiple workers
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
