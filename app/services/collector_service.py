"""
Collector Service

The single entry point for all data collection.

Rules:
  - NOTHING outside this service communicates with Facebook.
  - FastAPI, Telegram Bot, Dashboard, AI Reporting — all go through this service.
  - Every method creates a fresh BrowserSession via SessionManager.
  - No caching. No database. No stored state. Always real-time.

Flow:
    CollectorService
        ↓ SessionManager.get_session()     → fresh BrowserSession
        ↓ GraphClient.get_*()              → raw Graph API JSON
        ↓ CampaignMapper.map_*()           → typed Python objects
        ↓ return to caller
        ↓ SessionManager.release_session() → disconnect CDP

Public methods:
    get_campaigns(date_preset, status_filter)  → list[CampaignData]
    get_campaign(name_or_id, date_preset)      → CampaignData | None
    get_campaign_metrics(name_or_id, preset)   → InsightsData
    get_adsets(date_preset)                    → list[AdSetData]
    get_ads(date_preset)                       → list[AdData]
    get_account()                              → AccountData
    get_summary(date_preset)                   → CollectorSummary
"""

from dataclasses import dataclass, field
from typing import Optional

from app.core.logger import logger
from app.services.campaign_mapper import (
    AccountData,
    AdData,
    AdSetData,
    CampaignData,
    InsightsData,
    map_account,
    map_ad,
    map_adset,
    map_campaign,
)
from app.services.graph_client import GraphClient
from app.services.session_manager import (
    BrowserClosedError,
    BrowserSession,
    SessionError,
    SessionExpiredError,
    SessionManager,
)


# ---------------------------------------------------------------------------
# Summary object
# ---------------------------------------------------------------------------


@dataclass
class CollectorSummary:
    """
    Account-level aggregated summary across all campaigns.
    Computed from campaign data — no separate Graph API call needed.
    """
    account_id: str = ""
    date_preset: str = ""
    total_campaigns: int = 0
    active_campaigns: int = 0
    paused_campaigns: int = 0

    # Totals across all campaigns
    total_spend: float = 0.0
    total_impressions: int = 0
    total_reach: int = 0
    total_clicks: int = 0
    total_link_clicks: int = 0
    total_purchases: int = 0
    total_purchase_value: float = 0.0

    # Averages (weighted)
    avg_ctr: float = 0.0
    avg_cpc: float = 0.0
    avg_cpm: float = 0.0
    avg_roas: float = 0.0

    # Top campaigns (by spend)
    top_campaigns: list[CampaignData] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Collector Service
# ---------------------------------------------------------------------------


class CollectorService:
    """
    Production collector — the only source of truth for Facebook data.

    Every method:
      1. Calls SessionManager.get_session() → fresh CDP connection + fresh token.
      2. Calls GraphClient to execute API calls inside the browser.
      3. Maps raw JSON to typed objects via CampaignMapper.
      4. Releases the session.
      5. Returns typed objects to the caller.

    No data is ever cached. Every call returns live Facebook data.

    Usage:
        service = CollectorService(
            profile_id="k1dvlyr0",
            ad_account_id="1559140139101704",
        )
        campaigns = await service.get_campaigns()
        account = await service.get_account()
        summary = await service.get_summary()
    """

    def __init__(
        self,
        profile_id: str,
        ad_account_id: str,
        adspower_base_url: str = "http://local.adspower.net:50325",
    ) -> None:
        """
        Args:
            profile_id: AdsPower profile ID (e.g. "k1dvlyr0").
            ad_account_id: Numeric Facebook ad account ID (no "act_" prefix).
            adspower_base_url: Local AdsPower API URL.
        """
        self._profile_id = profile_id
        self._ad_account_id = ad_account_id
        self._session_manager = SessionManager(
            profile_id=profile_id,
            ad_account_id=ad_account_id,
            adspower_base_url=adspower_base_url,
        )
        self._graph = GraphClient()

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    async def get_campaigns(
        self,
        date_preset: str = "last_30d",
        status_filter: Optional[list[str]] = None,
    ) -> list[CampaignData]:
        """
        Return all campaigns with live metrics.

        Args:
            date_preset: Reporting window (today|yesterday|last_7d|last_30d|
                         last_90d|this_month|last_month|this_year|lifetime).
            status_filter: Optional list of statuses to include, e.g. ["ACTIVE"].
                           None means all statuses.

        Returns:
            List of CampaignData objects, sorted by spend descending.

        Raises:
            BrowserClosedError: AdsPower not running.
            SessionExpiredError: Facebook session expired.
            CollectorServiceError: Any other failure.
        """
        logger.info(
            f"[CollectorService] get_campaigns | account={self._ad_account_id} "
            f"| preset={date_preset} | filter={status_filter}"
        )
        logger.info("[CollectorService] Starting collection...")

        session = await self._new_session()
        try:
            logger.info("[CollectorService] Connected to browser.")
            logger.info("[CollectorService] Extracting fresh access token...")
            logger.info("[CollectorService] Executing Graph API call...")
            raw = await self._graph.get_campaigns(
                session,
                self._ad_account_id,
                date_preset,
                status_filter=status_filter,
            )
            logger.info(f"[CollectorService] Receiving response: {len(raw)} campaigns.")
            logger.info("[CollectorService] Normalizing data...")
            campaigns = [map_campaign(node, date_preset) for node in raw]

            # Filter by status if requested
            if status_filter:
                filter_upper = [s.upper() for s in status_filter]
                campaigns = [
                    c for c in campaigns
                    if c.effective_status.upper() in filter_upper
                ]

            # Sort by spend descending (highest spend first)
            campaigns.sort(key=lambda c: c.insights.spend, reverse=True)

        finally:
            await self._session_manager.release_session(session)

        logger.info(
            f"[CollectorService] Collection complete. "
            f"Returned {len(campaigns)} campaign(s)."
        )
        return campaigns

    async def get_campaign(
        self,
        name_or_id: str,
        date_preset: str = "last_30d",
    ) -> Optional[CampaignData]:
        """
        Return a single campaign by name or ID.

        Args:
            name_or_id: Campaign name (case-insensitive) or exact campaign ID.
            date_preset: Reporting window.

        Returns:
            CampaignData if found, None otherwise.
        """
        logger.info(f"[CollectorService] get_campaign | query='{name_or_id}'")
        logger.info("[CollectorService] Starting collection...")

        session = await self._new_session()
        try:
            logger.info("[CollectorService] Connected to browser.")
            logger.info("[CollectorService] Extracting fresh access token...")
            logger.info("[CollectorService] Executing Graph API call...")
            raw = await self._graph.get_campaign(session, self._ad_account_id, name_or_id, date_preset)
            logger.info("[CollectorService] Receiving response.")
            if raw is None:
                logger.warning(f"[CollectorService] Campaign not found: '{name_or_id}'")
                return None
            logger.info("[CollectorService] Normalizing data...")
            result = map_campaign(raw, date_preset)
        finally:
            await self._session_manager.release_session(session)

        logger.info(f"[CollectorService] Collection complete. Campaign: {result.campaign_name}")
        return result

    async def get_campaign_metrics(
        self,
        name_or_id: str,
        date_preset: str = "last_30d",
    ) -> Optional[InsightsData]:
        """
        Return only the performance metrics for a single campaign.

        Args:
            name_or_id: Campaign name or ID.
            date_preset: Reporting window.

        Returns:
            InsightsData if campaign found, None otherwise.
        """
        logger.info(f"[CollectorService] get_campaign_metrics | query='{name_or_id}'")
        campaign = await self.get_campaign(name_or_id, date_preset)
        if campaign is None:
            return None
        return campaign.insights

    async def get_adsets(
        self,
        date_preset: str = "last_30d",
    ) -> list[AdSetData]:
        """
        Return all ad sets with live metrics.
        """
        logger.info(f"[CollectorService] get_adsets | preset={date_preset}")
        logger.info("[CollectorService] Starting collection...")

        session = await self._new_session()
        try:
            logger.info("[CollectorService] Connected to browser.")
            logger.info("[CollectorService] Extracting fresh access token...")
            logger.info("[CollectorService] Executing Graph API call...")
            raw = await self._graph.get_adsets(session, self._ad_account_id, date_preset)
            logger.info(f"[CollectorService] Receiving response: {len(raw)} ad sets.")
            logger.info("[CollectorService] Normalizing data...")
            adsets = [map_adset(node, date_preset) for node in raw]
        finally:
            await self._session_manager.release_session(session)

        logger.info(f"[CollectorService] Collection complete. Returned {len(adsets)} ad set(s).")
        return adsets

    async def get_ads(
        self,
        date_preset: str = "last_30d",
    ) -> list[AdData]:
        """
        Return all ads with live metrics.
        """
        logger.info(f"[CollectorService] get_ads | preset={date_preset}")
        logger.info("[CollectorService] Starting collection...")

        session = await self._new_session()
        try:
            logger.info("[CollectorService] Connected to browser.")
            logger.info("[CollectorService] Extracting fresh access token...")
            logger.info("[CollectorService] Executing Graph API call...")
            raw = await self._graph.get_ads(session, self._ad_account_id, date_preset)
            logger.info(f"[CollectorService] Receiving response: {len(raw)} ads.")
            logger.info("[CollectorService] Normalizing data...")
            ads = [map_ad(node, date_preset) for node in raw]
        finally:
            await self._session_manager.release_session(session)

        logger.info(f"[CollectorService] Collection complete. Returned {len(ads)} ad(s).")
        return ads

    async def get_account(self) -> AccountData:
        """
        Return live account overview (name, currency, spend, balance, status).
        """
        logger.info(f"[CollectorService] get_account | account={self._ad_account_id}")
        logger.info("[CollectorService] Starting collection...")

        session = await self._new_session()
        try:
            logger.info("[CollectorService] Connected to browser.")
            logger.info("[CollectorService] Extracting fresh access token...")
            logger.info("[CollectorService] Executing Graph API call...")
            raw = await self._graph.get_account(session, self._ad_account_id)
            logger.info("[CollectorService] Receiving response.")
            logger.info("[CollectorService] Normalizing data...")
            result = map_account(raw)
        finally:
            await self._session_manager.release_session(session)

        logger.info(f"[CollectorService] Collection complete. Account: {result.account_name}")
        return result

    async def get_summary(
        self,
        date_preset: str = "last_30d",
    ) -> CollectorSummary:
        """
        Return an aggregated account-level summary across all campaigns.

        Computed from campaign data — no extra API call.
        Totals are summed; averages are spend-weighted.

        Args:
            date_preset: Reporting window.

        Returns:
            CollectorSummary with totals and top campaigns.
        """
        logger.info(f"[CollectorService] get_summary | preset={date_preset}")
        campaigns = await self.get_campaigns(date_preset)

        if not campaigns:
            return CollectorSummary(
                account_id=self._ad_account_id,
                date_preset=date_preset,
            )

        total_spend = sum(c.insights.spend for c in campaigns)
        total_impr = sum(c.insights.impressions for c in campaigns)
        total_reach = sum(c.insights.reach for c in campaigns)
        total_clicks = sum(c.insights.clicks for c in campaigns)
        total_link_clicks = sum(c.insights.link_clicks for c in campaigns)
        total_purchases = sum(c.insights.purchases for c in campaigns)
        total_purchase_value = sum(c.insights.purchase_value for c in campaigns)

        # Spend-weighted averages (only campaigns that have spend contribute)
        spending = [c for c in campaigns if c.insights.spend > 0]
        avg_ctr = (
            sum(c.insights.ctr * c.insights.spend for c in spending) / total_spend
            if total_spend > 0 else 0.0
        )
        avg_cpc = (
            sum(c.insights.cpc * c.insights.spend for c in spending) / total_spend
            if total_spend > 0 else 0.0
        )
        avg_cpm = (
            sum(c.insights.cpm * c.insights.spend for c in spending) / total_spend
            if total_spend > 0 else 0.0
        )
        avg_roas = (
            total_purchase_value / total_spend if total_spend > 0 else 0.0
        )

        return CollectorSummary(
            account_id=self._ad_account_id,
            date_preset=date_preset,
            total_campaigns=len(campaigns),
            active_campaigns=sum(1 for c in campaigns if c.effective_status == "ACTIVE"),
            paused_campaigns=sum(1 for c in campaigns if c.effective_status == "PAUSED"),
            total_spend=round(total_spend, 2),
            total_impressions=total_impr,
            total_reach=total_reach,
            total_clicks=total_clicks,
            total_link_clicks=total_link_clicks,
            total_purchases=total_purchases,
            total_purchase_value=round(total_purchase_value, 2),
            avg_ctr=round(avg_ctr, 4),
            avg_cpc=round(avg_cpc, 4),
            avg_cpm=round(avg_cpm, 4),
            avg_roas=round(avg_roas, 4),
            top_campaigns=campaigns[:5],  # top 5 by spend (already sorted)
        )

    async def update_campaign_status(self, campaign_id: str, status: str) -> dict:
        """
        Update the status of a campaign.
        
        Args:
            campaign_id: Exact campaign ID to update.
            status: New status (ACTIVE, PAUSED, DELETED, ARCHIVED).
            
        Returns:
            Dict containing success response.
        """
        logger.info(f"[CollectorService] update_campaign_status | {campaign_id} -> {status}")
        logger.info("[CollectorService] Starting update...")

        session = await self._new_session()
        try:
            logger.info("[CollectorService] Connected to browser.")
            logger.info("[CollectorService] Executing Graph API call...")
            result = await self._graph.update_campaign_status(session, campaign_id, status)
        finally:
            await self._session_manager.release_session(session)

        logger.info(f"[CollectorService] Update complete for {campaign_id}.")
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _new_session(self) -> BrowserSession:
        """
        Get a fresh browser session. Re-raises as CollectorServiceError
        with a clear message for any failure type.
        """
        logger.info("[CollectorService] Requesting fresh browser session...")
        try:
            return await self._session_manager.get_session()
        except (BrowserClosedError, SessionExpiredError, SessionError):
            raise  # let caller handle specific session errors


class CollectorServiceError(Exception):
    """Generic error from CollectorService."""
