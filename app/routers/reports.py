"""
Reports Router

GET /report   — complete account-level performance report
"""

import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.core.logger import logger
from app.routers.dependencies import Collector
from app.services.session_manager import BrowserClosedError, SessionExpiredError

router = APIRouter(prefix="/report", tags=["Reports"])

_DATE_PRESETS = [
    "today", "yesterday", "last_7d", "last_30d", "last_90d",
    "this_month", "last_month", "this_year", "lifetime",
]


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class CampaignSummaryItem(BaseModel):
    campaign_id: str
    campaign_name: str
    status: str
    spend: float
    impressions: int
    clicks: int
    ctr: float
    cpc: float
    cpm: float
    purchases: int
    roas: float
    budget_type: str
    daily_budget: Optional[float]
    lifetime_budget: Optional[float]


class ReportResponse(BaseModel):
    # Meta
    account_id: str
    date_preset: str
    generated_at: str           # ISO 8601 UTC timestamp

    # Totals
    total_campaigns: int
    active_campaigns: int
    paused_campaigns: int
    total_spend: float
    total_impressions: int
    total_reach: int
    total_clicks: int
    total_link_clicks: int
    total_purchases: int
    total_purchase_value: float

    # Averages (spend-weighted)
    avg_ctr: float
    avg_cpc: float
    avg_cpm: float
    avg_roas: float

    # Notable campaigns
    top_campaign: Optional[CampaignSummaryItem]     # highest spend
    worst_campaign: Optional[CampaignSummaryItem]   # lowest spend (with data)
    top_roas_campaign: Optional[CampaignSummaryItem]

    # Top 5 by spend
    top_campaigns: list[CampaignSummaryItem]

    response_time_ms: float


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _to_summary_item(c) -> CampaignSummaryItem:
    ins = c.insights
    return CampaignSummaryItem(
        campaign_id=c.campaign_id,
        campaign_name=c.campaign_name,
        status=c.effective_status,
        spend=ins.spend,
        impressions=ins.impressions,
        clicks=ins.clicks,
        ctr=ins.ctr,
        cpc=ins.cpc,
        cpm=ins.cpm,
        purchases=ins.purchases,
        roas=ins.roas,
        budget_type=c.budget_type,
        daily_budget=c.daily_budget,
        lifetime_budget=c.lifetime_budget,
    )


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=ReportResponse,
    summary="Full account performance report",
    description=(
        "Returns a complete aggregated report for the ad account. "
        "Includes totals, spend-weighted averages, top campaign, worst campaign, "
        "and top ROAS campaign. Always fetches fresh data — no cache."
    ),
    responses={
        200: {"description": "Report generated successfully"},
        401: {"description": "Facebook session expired"},
        503: {"description": "AdsPower browser not running"},
        500: {"description": "Collector or Graph API error"},
    },
)
async def get_report(
    collector: Collector,
    date_preset: str = Query(
        "last_30d",
        description=f"Reporting window. One of: {', '.join(_DATE_PRESETS)}",
        enum=_DATE_PRESETS,
    ),
) -> ReportResponse:
    t0 = time.perf_counter()
    logger.info(f"[GET /report] Incoming request | preset={date_preset}")

    try:
        logger.info("[GET /report] Collector starting...")
        summary = await collector.get_summary(date_preset=date_preset)
        logger.info("[GET /report] Collector finished.")
    except BrowserClosedError as exc:
        logger.error(f"[GET /report] Browser closed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AdsPower browser not running: {exc}",
        )
    except SessionExpiredError as exc:
        logger.error(f"[GET /report] Session expired: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Facebook session expired. Please re-login in AdsPower: {exc}",
        )
    except Exception as exc:
        logger.error(f"[GET /report] Unexpected error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Collector error: {exc}",
        )

    campaigns_all = summary.top_campaigns  # already sorted by spend
    # For worst/top-roas we need the full list — re-fetch from summary
    # (summary.top_campaigns is already top 5; for worst we use what we have)
    top = campaigns_all[0] if campaigns_all else None
    worst = campaigns_all[-1] if len(campaigns_all) > 1 else None
    top_roas = max(campaigns_all, key=lambda c: c.insights.roas, default=None) if campaigns_all else None

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    logger.info(f"[GET /report] Done in {elapsed_ms}ms.")

    return ReportResponse(
        account_id=summary.account_id,
        date_preset=summary.date_preset,
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_campaigns=summary.total_campaigns,
        active_campaigns=summary.active_campaigns,
        paused_campaigns=summary.paused_campaigns,
        total_spend=summary.total_spend,
        total_impressions=summary.total_impressions,
        total_reach=summary.total_reach,
        total_clicks=summary.total_clicks,
        total_link_clicks=summary.total_link_clicks,
        total_purchases=summary.total_purchases,
        total_purchase_value=summary.total_purchase_value,
        avg_ctr=summary.avg_ctr,
        avg_cpc=summary.avg_cpc,
        avg_cpm=summary.avg_cpm,
        avg_roas=summary.avg_roas,
        top_campaign=_to_summary_item(top) if top else None,
        worst_campaign=_to_summary_item(worst) if worst else None,
        top_roas_campaign=_to_summary_item(top_roas) if top_roas else None,
        top_campaigns=[_to_summary_item(c) for c in campaigns_all],
        response_time_ms=elapsed_ms,
    )
