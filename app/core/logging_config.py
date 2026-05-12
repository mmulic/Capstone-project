"""
Structured logging configuration (BE-027)
==========================================
JSON-formatted logs that play nicely with CloudWatch Logs Insights.
Captures request latency, error rates, and custom metrics.
"""

import json
import logging
import sys
import time
from datetime import datetime
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for CloudWatch ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include extras (custom fields)
        for key in ("request_id", "method", "path", "status_code", "duration_ms", "user_id"):
            if hasattr(record, key):
                log_data[key] = getattr(record, key)

        # Include exception info
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def configure_logging(level: str = "INFO"):
    """Set up structured JSON logging for the entire app."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Quiet down noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Log every HTTP request with: method, path, status_code, duration_ms.
    These structured fields are queryable in CloudWatch Logs Insights.
    """

    async def dispatch(self, request: Request, call_next):
        start = time.time()
        logger = logging.getLogger("app.requests")

        try:
            response = await call_next(request)
            duration_ms = int((time.time() - start) * 1000)

            logger.info(
                f"{request.method} {request.url.path} -> {response.status_code}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )

            response.headers["X-Response-Time-MS"] = str(duration_ms)
            return response

        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            logger.error(
                f"{request.method} {request.url.path} -> ERROR",
                exc_info=True,
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                    "duration_ms": duration_ms,
                },
            )
            raise
