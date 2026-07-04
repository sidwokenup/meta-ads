"""
System Router

GET /         — project info
GET /health   — live health check (verifies AdsPower + Facebook session)
"""

import time
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.logger import logger
from app.routers.dependencies import Collector

router = APIRouter(tags=["System"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class RootResponse(BaseModel):
    project: str
    version: str
    status: str


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    collector: Literal["ready", "error"]
    browser: Literal["connected", "disconnected"]
    facebook_session: Literal["active", "expired", "unknown"]
    detail: str = ""
    response_time_ms: float = 0.0


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=RootResponse,
    summary="Project info",
    description="Returns project name, version, and current run status.",
)
async def root() -> RootResponse:
    return RootResponse(
        project="Meta Ads Reporter",
        version="1.0.0",
        status="running",
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Live health check",
    description=(
        "Performs a live check by connecting to AdsPower and verifying the "
        "Facebook session is active. This makes a real request — do not poll rapidly."
    ),
    responses={
        200: {"description": "Service healthy or degraded (check fields)"},
        503: {"description": "Service unavailable"},
    },
)
async def health(collector: Collector) -> HealthResponse:
    """
    Health check that actually exercises the full pipeline:
    1. Connects to AdsPower browser
    2. Verifies Facebook session (token extraction)
    """
    t0 = time.perf_counter()
    logger.info("[/health] Starting live health check...")

    try:
        # Attempt to get a session — this exercises AdsPower + token extraction
        from app.services.session_manager import (
            BrowserClosedError,
            SessionExpiredError,
            SessionManager,
        )

        sm = collector._session_manager
        session = await sm.get_session()
        await sm.release_session(session)

        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info(f"[/health] Healthy. {elapsed_ms:.0f}ms")
        return HealthResponse(
            status="healthy",
            collector="ready",
            browser="connected",
            facebook_session="active",
            response_time_ms=round(elapsed_ms, 1),
        )

    except BrowserClosedError as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.warning(f"[/health] Browser closed: {exc}")
        return HealthResponse(
            status="unhealthy",
            collector="error",
            browser="disconnected",
            facebook_session="unknown",
            detail=str(exc),
            response_time_ms=round(elapsed_ms, 1),
        )

    except SessionExpiredError as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.warning(f"[/health] Session expired: {exc}")
        return HealthResponse(
            status="degraded",
            collector="ready",
            browser="connected",
            facebook_session="expired",
            detail=str(exc),
            response_time_ms=round(elapsed_ms, 1),
        )

    except Exception as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.error(f"[/health] Unexpected error: {exc}")
        return HealthResponse(
            status="unhealthy",
            collector="error",
            browser="disconnected",
            facebook_session="unknown",
            detail=str(exc),
            response_time_ms=round(elapsed_ms, 1),
        )
