"""
Campaign Collector

Orchestrates the full data collection pipeline using the new architecture:

  1. AdsPower Local API  → start browser profile, obtain CDP WebSocket URL
  2. CDP WebSocket       → connect to browser, retrieve session cookies
  3. httpx + cookies     → fetch Ads Manager HTML, extract access token
  4. Graph API (httpx)   → query campaigns and metrics with the token
  5. Parser              → normalize raw API response into CampaignModel objects

No HTML scraping. No CDP network interception. No GraphQL sniffing.
No CSS selectors. No XPath. No Playwright.
"""

from typing import Optional

from app.collectors.adspower import AdsPowerClient, AdsPowerError
from app.collectors.cdp_client import CDPClient, CDPError
from app.collectors.graph_api_client import (
    GraphAPIAuthError,
    GraphAPIClient,
    GraphAPIError,
)
from app.collectors.token_extractor import TokenExtractionError, extract_token_via_cdp
from app.core.logger import logger
from app.models.campaign import CampaignModel
from app.services.parser import parse_campaign_node


class CollectorError(Exception):
    """Raised when the collector fails to obtain campaign data."""


class FacebookSessionExpiredError(CollectorError):
    """Raised when the Facebook session or access token has expired."""


class CampaignCollector:
    """
    Collects live campaign data from an authenticated AdsPower browser session.

    Architecture:
        AdsPower API → CDP WebSocket → cookies → access token → Graph API → campaigns

    Usage:
        collector = CampaignCollector(
            profile_id="k1dvlyr0",
            ad_account_id="1559140139101704",
        )
        campaigns = await collector.collect()
    """

    def __init__(
        self,
        profile_id: str,
        ad_account_id: str,
        adspower_base_url: str = "http://local.adspower.net:50325",
        date_preset: str = "last_30d",
        stop_browser_on_finish: bool = False,
    ) -> None:
        """
        Args:
            profile_id: AdsPower profile/user ID.
            ad_account_id: Facebook Ad Account ID (numeric, without 'act_' prefix).
            adspower_base_url: Base URL for the AdsPower local API.
            date_preset: Reporting window for campaign metrics.
                Options: today, yesterday, last_7d, last_30d, last_90d,
                         this_month, last_month, this_year, lifetime.
            stop_browser_on_finish: Whether to stop the AdsPower profile after collection.
        """
        self.profile_id = profile_id
        self.ad_account_id = ad_account_id
        self.date_preset = date_preset
        self.stop_browser_on_finish = stop_browser_on_finish

        self._adspower = AdsPowerClient(base_url=adspower_base_url)
        self._cdp: Optional[CDPClient] = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def collect(self) -> list[CampaignModel]:
        """
        Run the full collection pipeline.

        Returns:
            List of CampaignModel objects with live campaign metrics.

        Raises:
            CollectorError: If any stage of collection fails.
            FacebookSessionExpiredError: If the access token has expired.
        """
        logger.info("=" * 60)
        logger.info("Campaign Collector Starting...")
        logger.info("=" * 60)

        try:
            # Step 1: Start browser profile
            ws_url = await self._start_browser()

            # Step 2: Connect CDP
            await self._connect_cdp(ws_url)

            # Step 3: Extract access token
            access_token = await self._extract_access_token()

            # Step 4: Query Graph API
            raw_campaigns = await self._fetch_campaigns(access_token)

            # Step 5: Parse into models
            campaigns = self._parse_campaigns(raw_campaigns)

        except (FacebookSessionExpiredError, CollectorError):
            raise
        except Exception as exc:
            raise CollectorError(f"Unexpected collector error: {exc}") from exc
        finally:
            await self._cleanup()

        if not campaigns:
            logger.warning(
                "Collection complete but no campaigns found. "
                "The ad account may have no active campaigns for the selected date range."
            )

        logger.info(
            f"Collector Finished. Collected {len(campaigns)} campaign(s)."
        )
        return campaigns

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------

    async def _start_browser(self) -> str:
        """Step 1: Start AdsPower profile and obtain CDP WebSocket URL."""
        logger.info(f"Starting AdsPower Profile: {self.profile_id}")
        try:
            return await self._adspower.get_websocket(self.profile_id)
        except AdsPowerError as exc:
            raise CollectorError(f"AdsPower startup failed: {exc}") from exc

    async def _connect_cdp(self, ws_url: str) -> None:
        """Step 2: Connect to the browser via CDP, preferring an Ads Manager tab."""
        logger.info("Connecting to CDP...")
        try:
            self._cdp = CDPClient(
                ws_url=ws_url,
                prefer_url_fragment="adsmanager",
            )
            await self._cdp.connect()
            await self._cdp.enable_network()
        except CDPError as exc:
            raise CollectorError(f"CDP connection failed: {exc}") from exc

    async def _extract_access_token(self) -> str:
        """Step 3: Use CDP cookies + httpx to extract the access token from page HTML."""
        try:
            result = await extract_token_via_cdp(self._cdp, self.ad_account_id)
            return result.token
        except TokenExtractionError as exc:
            if "session" in str(exc).lower() or "redirect" in str(exc).lower():
                raise FacebookSessionExpiredError(str(exc)) from exc
            raise CollectorError(f"Token extraction failed: {exc}") from exc

    async def _fetch_campaigns(self, access_token: str) -> list[dict]:
        """Step 4: Query the Graph API via browser fetch() for campaign data."""
        logger.info("Querying Graph API for campaign data...")
        try:
            client = GraphAPIClient(cdp=self._cdp, access_token=access_token)
            return await client.get_campaigns(
                account_id=self.ad_account_id,
                date_preset=self.date_preset,
            )
        except GraphAPIAuthError as exc:
            raise FacebookSessionExpiredError(str(exc)) from exc
        except GraphAPIError as exc:
            raise CollectorError(f"Graph API error: {exc}") from exc

    def _parse_campaigns(self, raw_campaigns: list[dict]) -> list[CampaignModel]:
        """Step 5: Parse raw Graph API campaign dicts into CampaignModel objects."""
        campaigns: list[CampaignModel] = []
        for node in raw_campaigns:
            try:
                campaign = parse_campaign_node(node)
                campaigns.append(campaign)
                logger.info(
                    f"Campaign Parsed: [{campaign.delivery.status}] {campaign.campaign_name}"
                )
            except Exception as exc:
                logger.warning(
                    f"Failed to parse campaign {node.get('id', '?')}: {exc}"
                )
        return campaigns

    async def _cleanup(self) -> None:
        """Disconnect CDP and optionally stop the browser profile."""
        if self._cdp:
            try:
                await self._cdp.disconnect()
            except Exception:
                pass

        if self.stop_browser_on_finish:
            try:
                await self._adspower.stop_profile(self.profile_id)
            except AdsPowerError as exc:
                logger.warning(f"Failed to stop AdsPower profile: {exc}")
