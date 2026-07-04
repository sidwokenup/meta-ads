"""
Account Router

GET /account   — live ad account overview
"""

import time
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.logger import logger
from app.routers.dependencies import Collector
from app.services.session_manager import BrowserClosedError, SessionExpiredError

router = APIRouter(prefix="/account", tags=["Account"])


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------


class AccountResponse(BaseModel):
    account_id: str
    account_name: str
    currency: str
    timezone: str
    account_status: int
    business_name: Optional[str]
    amount_spent: float
    balance: float
    spend_cap: Optional[float]
    # Derived from campaigns (fetched separately)
    total_campaigns: int
    active_campaigns: int
    paused_campaigns: int
    response_time_ms: float


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=AccountResponse,
    summary="Ad account overview",
    description=(
        "Returns live ad account details including name, currency, timezone, "
        "lifetime spend, balance, and a breakdown of campaign counts by status. "
        "Always fetches fresh data — no cache."
    ),
    responses={
        200: {"description": "Account data fetched successfully"},
        503: {"description": "AdsPower not running or browser closed"},
        401: {"description": "Facebook session expired"},
        500: {"description": "Collector or Graph API error"},
    },
)
async def get_account(collector: Collector) -> AccountResponse:
    t0 = time.perf_counter()
    logger.info("[GET /account] Incoming request")

    try:
        # Fetch account and campaign counts concurrently via two separate sessions
        # (CollectorService creates a fresh session per call)
        logger.info("[GET /account] Collector starting...")
        account, campaigns = await _fetch_account_and_campaigns(collector)
        logger.info("[GET /account] Collector finished")

    except BrowserClosedError as exc:
        logger.error(f"[GET /account] Browser closed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AdsPower browser not running: {exc}",
        )
    except SessionExpiredError as exc:
        logger.error(f"[GET /account] Session expired: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Facebook session expired. Please re-login in AdsPower: {exc}",
        )
    except Exception as exc:
        logger.error(f"[GET /account] Unexpected error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Collector error: {exc}",
        )

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    logger.info(f"[GET /account] Done in {elapsed_ms}ms")

    return AccountResponse(
        account_id=account.account_id,
        account_name=account.account_name,
        currency=account.currency,
        timezone=account.timezone,
        account_status=account.account_status,
        business_name=account.business_name,
        amount_spent=account.amount_spent,
        balance=account.balance,
        spend_cap=account.spend_cap,
        total_campaigns=len(campaigns),
        active_campaigns=sum(1 for c in campaigns if c.effective_status == "ACTIVE"),
        paused_campaigns=sum(1 for c in campaigns if c.effective_status == "PAUSED"),
        response_time_ms=elapsed_ms,
    )


async def _fetch_account_and_campaigns(collector):
    """Fetch account info and campaign list (two calls, sequential)."""
    account = await collector.get_account()
    campaigns = await collector.get_campaigns()
    return account, campaigns
