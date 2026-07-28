"""FastAPI middleware for structured request logging.

Uses structlog so every request emits a single JSON line containing the
method, path, status code, and duration. This replaces ad-hoc print()
debugging and makes request traces queryable in log aggregation tools.
"""
from __future__ import annotations

import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.utils.logger import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that logs request lifecycle with structured fields."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        path = request.url.path
        method = request.method

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            status_code = 500
            logger.exception(
                "request_failed",
                method=method,
                path=path,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "request_finished",
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=round(duration_ms, 3),
            )

        return response
