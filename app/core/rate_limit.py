"""
Rate Limiting Middleware (BE-022)
==================================
Simple in-memory rate limiter using a sliding window.
For production, consider using Redis-backed slowapi.
"""

import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware


# In-memory rate limit tracking — {(ip, route): deque of timestamps}
_rate_limit_store: dict[tuple, deque] = defaultdict(deque)


class RateLimitConfig:
    """Per-route rate limit settings."""
    LIMITS = {
        "/api/predict": (10, 60),    # 10 requests per 60 seconds
        "/api/chat": (30, 60),       # 30 requests per 60 seconds
        "/api/ingest": (20, 60),
        "/api/ingest/batch": (5, 60),
    }
    DEFAULT_LIMIT = (100, 60)  # Fallback


def _get_client_ip(request: Request) -> str:
    """Extract client IP, accounting for reverse proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(ip: str, route: str) -> tuple[bool, int]:
    """
    Check if request should be allowed.
    Returns (allowed, retry_after_seconds).
    """
    limit, window = RateLimitConfig.LIMITS.get(route, RateLimitConfig.DEFAULT_LIMIT)

    key = (ip, route)
    now = time.time()
    cutoff = now - window

    # Remove expired entries
    timestamps = _rate_limit_store[key]
    while timestamps and timestamps[0] < cutoff:
        timestamps.popleft()

    if len(timestamps) >= limit:
        retry_after = int(timestamps[0] + window - now) + 1
        return False, retry_after

    timestamps.append(now)
    return True, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply rate limiting to specific endpoints."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Only rate-limit configured routes
        if path in RateLimitConfig.LIMITS:
            ip = _get_client_ip(request)
            allowed, retry_after = _check_rate_limit(ip, path)

            if not allowed:
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": f"Rate limit exceeded. Retry in {retry_after} seconds.",
                        "retry_after": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)},
                )

        return await call_next(request)
