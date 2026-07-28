"""FastAPI application entry point.

Configures structured logging via structlog and error tracking via Sentry before
any routes are mounted. The Sentry ASGI integration captures unhandled
exceptions, performance traces, and request context automatically.
"""
from __future__ import annotations

import os

import sentry_sdk
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from backend.app.middleware import RequestLoggingMiddleware
from backend.app.routers import receipts
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _init_sentry() -> None:
    """Initialize Sentry only when a DSN is configured.

    Keeping init conditional lets the app run locally without Sentry while still
    being production-ready once the DSN env var is set.
    """
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        logger.info("sentry_skipped", reason="SENTRY_DSN not configured")
        return

    sentry_sdk.init(
        dsn=dsn,
        integrations=[
            StarletteIntegration(),
            FastApiIntegration(),
        ],
        # Capture 10% of transactions for performance monitoring.
        # Increase once the app is stable and Sentry quotas allow.
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        # Lower sample rate for profiles to control cost.
        profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.05")),
        environment=os.getenv("SENTRY_ENVIRONMENT", os.getenv("ENVIRONMENT", "development")),
        release=os.getenv("SENTRY_RELEASE", os.getenv("GITHUB_SHA", "unknown")),
    )
    logger.info("sentry_initialized", environment=os.getenv("SENTRY_ENVIRONMENT", "development"))


_init_sentry()

app = FastAPI(
    title="Socrates Automation API",
    description="Backend API for the Socrates Instagram content pipeline.",
    version="1.0.0",
)

# Log every request with structured fields (method, path, duration, status).
app.add_middleware(RequestLoggingMiddleware)

# Receipt upload API.
app.include_router(receipts.router)


@app.get("/health")
async def health_check() -> JSONResponse:
    """Lightweight health check for load balancers and deploy verification."""
    return JSONResponse({"status": "ok"})


@app.on_event("startup")
async def startup_event() -> None:
    logger.info("api_startup")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    logger.info("api_shutdown")
