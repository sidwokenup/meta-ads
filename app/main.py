"""
Meta Ads Reporter — FastAPI Application

Entry point. Registers all routers. Knows nothing about:
  - AdsPower
  - CDP
  - Graph API
  - Tokens
  - Browser sessions

FastAPI only knows: CollectorService exists and is injected via get_collector().
"""

import time
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.logger import logger
from app.routers import account, campaigns, reports, system
from app.workers.alert_worker import alert_worker_loop


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("=" * 60)
    logger.info(f"  {settings.APP_NAME} starting [{settings.APP_ENV}]")
    logger.info(f"  Swagger UI : http://{settings.HOST}:{settings.PORT}/docs")
    logger.info(f"  OpenAPI    : http://{settings.HOST}:{settings.PORT}/openapi.json")
    logger.info("=" * 60)
    
    # Start the background alert worker
    worker_task = asyncio.create_task(alert_worker_loop())
    
    yield
    
    # Cancel the worker on shutdown
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
        
    logger.info(f"  {settings.APP_NAME} shutting down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


app = FastAPI(
    title="Meta Ads Reporter",
    version="1.0.0",
    description=(
        "Real-time Facebook Ads reporting API. "
        "Every endpoint fetches live data directly from the authenticated "
        "AdsPower browser via CDP. No cache. No database. Always fresh."
    ),
    contact={"name": "Meta Ads Reporter"},
    license_info={"name": "Private"},
    lifespan=lifespan,
    debug=settings.DEBUG,
)

# ---------------------------------------------------------------------------
# CORS (allow all origins in dev — tighten in production)
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],  # Changed from ["GET"] to ["*"] to allow POST, OPTIONS, etc.
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------


@app.middleware("http")
async def log_requests(request: Request, call_next):
    t0 = time.perf_counter()
    logger.info(f"--> {request.method} {request.url.path}")
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    logger.info(f"<-- {request.method} {request.url.path} [{response.status_code}] {elapsed_ms}ms")
    return response


# ---------------------------------------------------------------------------
# Global exception handler (last-resort)
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {exc}"},
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(system.router)       # GET /    GET /health
app.include_router(account.router)      # GET /account
app.include_router(campaigns.router)    # GET /campaigns  GET /campaign/{name}
app.include_router(reports.router)      # GET /report
