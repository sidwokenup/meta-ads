"""
Session Manager

Responsible for maintaining a live, authenticated connection to the
AdsPower browser and providing fresh credentials (cookies + access token)
for every request.

Rules:
  - Never store the access token permanently.
  - Never store cookies permanently.
  - Every get_session() call reconnects if needed and extracts a fresh token.
  - Session expiry is detected and reported clearly.

Architecture:
    SessionManager
        ↓ AdsPowerClient  → verify profile is running → get CDP WebSocket URL
        ↓ CDPClient       → connect to browser, prefer Ads Manager tab
        ↓ Network.getCookies → get live session cookies
        ↓ httpx GET       → fetch Ads Manager HTML
        ↓ regex           → extract window.__accessToken
        → return BrowserSession (cdp handle + fresh token)
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

from app.collectors.adspower import AdsPowerClient, AdsPowerError
from app.collectors.cdp_client import CDPClient, CDPError
from app.collectors.token_extractor import TokenExtractionError, extract_token_via_cdp
from app.core.logger import logger


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class SessionError(Exception):
    """Raised when a browser session cannot be established."""


class SessionExpiredError(SessionError):
    """Raised when the Facebook session is expired or logged out."""


class BrowserClosedError(SessionError):
    """Raised when AdsPower or the browser profile is not running."""


# ---------------------------------------------------------------------------
# Session data class
# ---------------------------------------------------------------------------


@dataclass
class BrowserSession:
    """
    A live, authenticated browser session.

    Contains:
      - cdp: Active CDPClient connected to the Ads Manager tab.
      - access_token: Fresh window.__accessToken extracted from page HTML.
      - token_expiry_seconds: How long until the token expires (~24h typically).
      - account_id: The ad account ID this session was created for.

    This object is consumed by GraphClient to execute Graph API calls.
    It is NOT cached — a new one is created for every collector request.
    """
    cdp: CDPClient
    access_token: str
    token_expiry_seconds: Optional[int]
    account_id: str


# ---------------------------------------------------------------------------
# Session Manager
# ---------------------------------------------------------------------------


class SessionManager:
    """
    Manages connection lifecycle for an AdsPower browser profile.

    Usage:
        manager = SessionManager(
            profile_id="k1dvlyr0",
            ad_account_id="1559140139101704",
        )
        async with manager.get_session() as session:
            # session.cdp and session.access_token are ready
            data = await graph_client.get_campaigns(session)

    Every call to get_session() creates a fresh connection.
    No session state is retained between calls.
    """

    def __init__(
        self,
        profile_id: str,
        ad_account_id: str,
        adspower_base_url: str = "http://local.adspower.net:50325",
        max_retries: int = 2,
    ) -> None:
        """
        Args:
            profile_id: AdsPower profile/user ID (e.g. "k1dvlyr0").
            ad_account_id: Numeric Facebook ad account ID (no "act_" prefix).
            adspower_base_url: Local AdsPower API URL.
            max_retries: How many times to retry CDP connection on transient failures.
        """
        self._profile_id = profile_id
        self._ad_account_id = ad_account_id
        self._max_retries = max_retries
        self._adspower = AdsPowerClient(base_url=adspower_base_url)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def get_session(self) -> BrowserSession:
        """
        Build and return a fresh BrowserSession.

        Steps:
          1. Verify AdsPower profile is running → get CDP WebSocket URL.
          2. Connect CDPClient to the Ads Manager tab.
          3. Extract fresh access token via cookies + httpx.

        Returns:
            BrowserSession ready for GraphClient use.

        Raises:
            BrowserClosedError: AdsPower not running or profile not found.
            SessionExpiredError: Facebook session expired / not logged in.
            SessionError: Any other connection failure.
        """
        logger.info(f"[SessionManager] Starting session for profile={self._profile_id}, account={self._ad_account_id}")

        ws_url = await self._get_ws_url()
        cdp = await self._connect_cdp(ws_url)
        session = await self._build_session(cdp)

        logger.info(
            f"[SessionManager] Session ready. "
            f"Token expires in {session.token_expiry_seconds}s "
            f"(~{(session.token_expiry_seconds or 0) // 3600}h)."
        )
        return session

    async def release_session(self, session: BrowserSession) -> None:
        """
        Disconnect the CDP connection from a session.
        Call this after you are done with the session.

        Does NOT stop the AdsPower browser — the profile keeps running.
        """
        logger.info("[SessionManager] Releasing session (disconnecting CDP).")
        try:
            await session.cdp.disconnect()
        except Exception as exc:
            logger.warning(f"[SessionManager] CDP disconnect warning: {exc}")

    # ------------------------------------------------------------------
    # Internal steps
    # ------------------------------------------------------------------

    async def _get_ws_url(self) -> str:
        """Step 1: Get CDP WebSocket URL from AdsPower."""
        logger.info(f"[SessionManager] Verifying AdsPower profile: {self._profile_id}")
        try:
            ws_url = await self._adspower.get_websocket(self._profile_id)
            logger.info(f"[SessionManager] Connected to AdsPower browser: {ws_url[:60]}...")
            return ws_url
        except AdsPowerError as exc:
            msg = str(exc).lower()
            if "not found" in msg or "failed" in msg or "not running" in msg:
                raise BrowserClosedError(
                    f"AdsPower profile '{self._profile_id}' is not running or not found. "
                    f"Please open AdsPower and start the profile. Detail: {exc}"
                ) from exc
            raise SessionError(f"AdsPower error: {exc}") from exc

    async def _connect_cdp(self, ws_url: str) -> CDPClient:
        """
        Step 2: Connect CDPClient with automatic retry on transient failures.
        Prefers the existing Ads Manager tab if open.
        """
        logger.info("[SessionManager] Connecting to browser via CDP...")
        last_exc: Optional[Exception] = None

        for attempt in range(1, self._max_retries + 2):
            try:
                cdp = CDPClient(
                    ws_url=ws_url,
                    prefer_url_fragment="adsmanager",
                )
                await cdp.connect()
                await cdp.enable_network()
                logger.info(f"[SessionManager] CDP connected (attempt {attempt}).")
                return cdp
            except CDPError as exc:
                last_exc = exc
                if attempt <= self._max_retries:
                    logger.warning(
                        f"[SessionManager] CDP connect attempt {attempt} failed: {exc}. "
                        f"Retrying in 2s..."
                    )
                    await asyncio.sleep(2)
                else:
                    logger.error("[SessionManager] All CDP connect attempts exhausted.")

        raise BrowserClosedError(
            f"Could not connect to browser via CDP after {self._max_retries + 1} attempts. "
            f"Is the browser open? Detail: {last_exc}"
        ) from last_exc

    async def _build_session(self, cdp: CDPClient) -> BrowserSession:
        """
        Step 3: Extract fresh access token from Ads Manager HTML.
        Handles session expiry detection.
        """
        logger.info("[SessionManager] Extracting fresh access token...")
        try:
            result = await extract_token_via_cdp(cdp, self._ad_account_id)
        except TokenExtractionError as exc:
            await cdp.disconnect()
            msg = str(exc).lower()
            if "login" in msg or "session" in msg or "redirect" in msg or "checkpoint" in msg:
                raise SessionExpiredError(
                    f"Facebook session expired or not logged in. "
                    f"Please re-login in AdsPower. Detail: {exc}"
                ) from exc
            raise SessionError(f"Token extraction failed: {exc}") from exc

        return BrowserSession(
            cdp=cdp,
            access_token=result.token,
            token_expiry_seconds=result.expiry_seconds,
            account_id=self._ad_account_id,
        )
