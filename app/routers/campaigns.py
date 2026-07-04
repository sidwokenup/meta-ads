"""
Campaigns Router

GET /campaigns                    — all campaigns (live)
GET /campaign/{campaign_name}     — single campaign by name or ID
GET /campaign/{campaign_name}/raw — raw Graph API JSON for debugging
POST /campaign/{campaign_id}/status — update campaign status
"""

import time
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.core.logger import logger
from app.routers.dependencies import Collector
from app.services.session_manager import BrowserClosedError, SessionExpiredError

router = APIRouter(tags=["Campaigns"])

# Valid date presets accepted by Facebook Graph API
_DATE_PRESETS = [
    "today", "yesterday", "last_7d", "last_30d", "last_90d",
    "this_month", "last_month", "this_year", "lifetime",
]

_STATUS_OPTIONS = ["ACTIVE", "PAUSED", "ARCHIVED", "DELETED"]


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class InsightsResponse(BaseModel):
    date_start: Optional[str]
    date_stop: Optional[str]
    spend: float
    impressions: int
    reach: int
    frequency: float
    clicks: int
    unique_clicks: int
    link_clicks: int
    ctr: float
    cpc: float
    cpm: float
    purchases: int
    purchase_value: float
    cost_per_purchase: float
    roas: float
    landing_page_views: int
    add_to_carts: int
    initiate_checkouts: int


class CampaignResponse(BaseModel):
    # Identity
    campaign_id: str
    campaign_name: str
    objective: Optional[str]
    buying_type: Optional[str]
    # Delivery
    status: str
    effective_status: str
    delivery_status: Optional[str]
    learning_status: Optional[str]
    # Budget
    daily_budget: Optional[float]
    lifetime_budget: Optional[float]
    budget_type: str
    # Schedule
    start_time: Optional[str]
    end_time: Optional[str]
    # Strategy
    bid_strategy: Optional[str]
    # Metrics
    insights: InsightsResponse


class CampaignsListResponse(BaseModel):
    account_id: str
    date_preset: str
    total: int
    campaigns: list[CampaignResponse]
    response_time_ms: float


class CampaignStatusUpdateRequest(BaseModel):
    status: Literal["ACTIVE", "PAUSED", "ARCHIVED", "DELETED"]


# ---------------------------------------------------------------------------
# Error handler helper
# ---------------------------------------------------------------------------


def _handle_collector_error(exc: Exception, context: str) -> None:
    if isinstance(exc, BrowserClosedError):
        logger.error(f"[{context}] Browser closed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AdsPower browser not running: {exc}",
        )
    if isinstance(exc, SessionExpiredError):
        logger.error(f"[{context}] Session expired: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Facebook session expired. Please re-login in AdsPower: {exc}",
        )
    logger.error(f"[{context}] Unexpected error: {exc}")
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Collector error: {exc}",
    )


def _campaign_to_response(c) -> CampaignResponse:
    ins = c.insights
    return CampaignResponse(
        campaign_id=c.campaign_id,
        campaign_name=c.campaign_name,
        objective=c.objective,
        buying_type=c.buying_type,
        status=c.status,
        effective_status=c.effective_status,
        delivery_status=c.delivery_status,
        learning_status=c.learning_status,
        daily_budget=c.daily_budget,
        lifetime_budget=c.lifetime_budget,
        budget_type=c.budget_type,
        start_time=c.start_time,
        end_time=c.end_time,
        bid_strategy=c.bid_strategy,
        insights=InsightsResponse(
            date_start=ins.date_start,
            date_stop=ins.date_stop,
            spend=ins.spend,
            impressions=ins.impressions,
            reach=ins.reach,
            frequency=ins.frequency,
            clicks=ins.clicks,
            unique_clicks=ins.unique_clicks,
            link_clicks=ins.link_clicks,
            ctr=ins.ctr,
            cpc=ins.cpc,
            cpm=ins.cpm,
            purchases=ins.purchases,
            purchase_value=ins.purchase_value,
            cost_per_purchase=ins.cost_per_purchase,
            roas=ins.roas,
            landing_page_views=ins.landing_page_views,
            add_to_carts=ins.add_to_carts,
            initiate_checkouts=ins.initiate_checkouts,
        ),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(
    "/campaigns",
    response_model=CampaignsListResponse,
    summary="List all campaigns",
    description=(
        "Returns all campaigns with live performance metrics. "
        "Always fetches fresh data from Facebook — no cache. "
        "Results are sorted by spend (highest first)."
    ),
    responses={
        200: {"description": "Campaigns fetched successfully"},
        401: {"description": "Facebook session expired"},
        503: {"description": "AdsPower browser not running"},
        500: {"description": "Collector error"},
    },
)
async def list_campaigns(
    collector: Collector,
    date_preset: str = Query(
        "last_30d",
        description=f"Reporting window. One of: {', '.join(_DATE_PRESETS)}",
        enum=_DATE_PRESETS,
    ),
    campaign_status: Optional[str] = Query(
        None,
        description="Filter by status. One of: ACTIVE, PAUSED, ARCHIVED, DELETED",
        enum=_STATUS_OPTIONS,
    ),
    objective: Optional[str] = Query(
        None,
        description="Filter by campaign objective (case-insensitive, e.g. OUTCOME_SALES)",
    ),
    campaign_name: Optional[str] = Query(
        None,
        description="Filter by partial campaign name (case-insensitive)",
    ),
) -> CampaignsListResponse:
    t0 = time.perf_counter()
    logger.info(
        f"[GET /campaigns] Incoming request | preset={date_preset} "
        f"| status={campaign_status} | objective={objective} | name={campaign_name}"
    )

    status_filter = [campaign_status] if campaign_status else None

    try:
        logger.info("[GET /campaigns] Collector starting...")
        campaigns = await collector.get_campaigns(
            date_preset=date_preset,
            status_filter=status_filter,
        )
        logger.info(f"[GET /campaigns] Collector finished. {len(campaigns)} campaigns.")
    except Exception as exc:
        _handle_collector_error(exc, "GET /campaigns")

    # Apply additional filters (objective, partial name)
    if objective:
        obj_upper = objective.upper()
        campaigns = [c for c in campaigns if (c.objective or "").upper() == obj_upper]

    if campaign_name:
        name_lower = campaign_name.lower()
        campaigns = [c for c in campaigns if name_lower in c.campaign_name.lower()]

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    logger.info(f"[GET /campaigns] Done in {elapsed_ms}ms. Returning {len(campaigns)} campaigns.")

    return CampaignsListResponse(
        account_id=collector._ad_account_id,
        date_preset=date_preset,
        total=len(campaigns),
        campaigns=[_campaign_to_response(c) for c in campaigns],
        response_time_ms=elapsed_ms,
    )


@router.get(
    "/campaign/{campaign_name}",
    response_model=CampaignResponse,
    summary="Get single campaign",
    description=(
        "Returns full details for a single campaign by name (case-insensitive) "
        "or exact campaign ID. Includes all metrics, budget, delivery, and conversion data."
    ),
    responses={
        200: {"description": "Campaign found and returned"},
        404: {"description": "Campaign not found"},
        401: {"description": "Facebook session expired"},
        503: {"description": "AdsPower browser not running"},
        500: {"description": "Collector error"},
    },
)
async def get_campaign(
    campaign_name: str,
    collector: Collector,
    date_preset: str = Query(
        "last_30d",
        description=f"Reporting window. One of: {', '.join(_DATE_PRESETS)}",
        enum=_DATE_PRESETS,
    ),
) -> CampaignResponse:
    t0 = time.perf_counter()
    logger.info(f"[GET /campaign/{campaign_name}] Incoming request | preset={date_preset}")

    try:
        logger.info(f"[GET /campaign/{campaign_name}] Collector starting...")
        campaign = await collector.get_campaign(
            name_or_id=campaign_name,
            date_preset=date_preset,
        )
        logger.info(f"[GET /campaign/{campaign_name}] Collector finished.")
    except Exception as exc:
        _handle_collector_error(exc, f"GET /campaign/{campaign_name}")

    if campaign is None:
        logger.warning(f"[GET /campaign/{campaign_name}] Not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign '{campaign_name}' not found in account.",
        )

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    logger.info(f"[GET /campaign/{campaign_name}] Done in {elapsed_ms}ms.")
    return _campaign_to_response(campaign)


@router.get(
    "/campaign/{campaign_name}/raw",
    response_model=dict[str, Any],
    summary="Raw Graph API JSON for a campaign",
    description=(
        "Returns the raw, unnormalized Graph API JSON for a campaign. "
        "Useful for debugging, building new features, or inspecting fields "
        "that are not yet normalized by CampaignMapper."
    ),
    responses={
        200: {"description": "Raw Graph API JSON returned"},
        404: {"description": "Campaign not found"},
        401: {"description": "Facebook session expired"},
        503: {"description": "AdsPower browser not running"},
        500: {"description": "Collector error"},
    },
)
async def get_campaign_raw(
    campaign_name: str,
    collector: Collector,
    date_preset: str = Query("last_30d", enum=_DATE_PRESETS),
) -> dict[str, Any]:
    t0 = time.perf_counter()
    logger.info(f"[GET /campaign/{campaign_name}/raw] Incoming request")

    # To get raw JSON we go through GraphClient directly via the session manager
    # We expose it through CollectorService to keep boundaries clean:
    # collect all campaigns raw → find the matching one
    try:
        from app.services.graph_client import GraphClient
        from app.services.session_manager import (
            BrowserClosedError,
            SessionExpiredError,
        )

        sm = collector._session_manager
        gc = GraphClient()
        session = await sm.get_session()
        try:
            raw_list = await gc.get_campaigns(
                session,
                collector._ad_account_id,
                date_preset,
            )
        finally:
            await sm.release_session(session)

    except Exception as exc:
        _handle_collector_error(exc, f"GET /campaign/{campaign_name}/raw")

    # Find matching campaign
    name_lower = campaign_name.lower()
    for node in raw_list:
        if node.get("id") == campaign_name or node.get("name", "").lower() == name_lower:
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
            logger.info(f"[GET /campaign/{campaign_name}/raw] Done in {elapsed_ms}ms.")
            return node

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Campaign '{campaign_name}' not found.",
    )


@router.post(
    "/campaign/{campaign_id}/status",
    response_model=dict[str, Any],
    summary="Update campaign status",
    description=(
        "Updates the status of a specific campaign by ID. "
        "Allows pausing or activating campaigns directly from the dashboard."
    ),
    responses={
        200: {"description": "Status updated successfully"},
        400: {"description": "Invalid status"},
        401: {"description": "Facebook session expired"},
        503: {"description": "AdsPower browser not running"},
        500: {"description": "Collector error"},
    },
)
async def update_campaign_status(
    campaign_id: str,
    request: CampaignStatusUpdateRequest,
    collector: Collector,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    logger.info(f"[POST /campaign/{campaign_id}/status] Incoming request | status={request.status}")

    try:
        logger.info(f"[POST /campaign/{campaign_id}/status] Collector starting...")
        result = await collector.update_campaign_status(campaign_id, request.status)
        logger.info(f"[POST /campaign/{campaign_id}/status] Collector finished.")
    except Exception as exc:
        _handle_collector_error(exc, f"POST /campaign/{campaign_id}/status")

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    logger.info(f"[POST /campaign/{campaign_id}/status] Done in {elapsed_ms}ms.")
    return {"success": True, "result": result, "response_time_ms": elapsed_ms}
