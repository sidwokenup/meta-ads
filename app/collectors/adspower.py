"""
AdsPower Local API client.

Communicates with the AdsPower desktop application running locally.
Responsible for starting/stopping browser profiles and obtaining
the CDP WebSocket endpoint URL.

AdsPower API base: http://local.adspower.net:50325
"""

from typing import Any, Optional

import httpx

from app.core.logger import logger

ADSPOWER_BASE_URL = "http://local.adspower.net:50325"
DEFAULT_TIMEOUT = 30.0


class AdsPowerError(Exception):
    """Raised when the AdsPower API returns an error or is unreachable."""


class AdsPowerProfileNotFoundError(AdsPowerError):
    """Raised when the requested profile does not exist."""


class AdsPowerClient:
    """
    Client for the AdsPower Local API.

    Usage:
        client = AdsPowerClient()
        ws_url = await client.get_websocket(profile_id="abc123")
    """

    def __init__(
        self,
        base_url: str = ADSPOWER_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Low-level HTTP helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str, params: Optional[dict[str, Any]] = None) -> dict:
        """
        Perform a GET request against the AdsPower local API.
        Returns the parsed JSON body.
        Raises AdsPowerError on any failure.
        """
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.ConnectError as exc:
            raise AdsPowerError(
                "Cannot connect to AdsPower. Make sure AdsPower is running."
            ) from exc
        except httpx.TimeoutException as exc:
            raise AdsPowerError(
                f"AdsPower API timed out after {self.timeout}s: {url}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise AdsPowerError(
                f"AdsPower API returned HTTP {exc.response.status_code}: {url}"
            ) from exc

    def _check_response(self, data: dict, operation: str) -> dict:
        """
        Validate an AdsPower API response envelope.
        AdsPower uses { "code": 0, "data": {...} } for success.
        Any non-zero code is treated as an error.
        """
        code = data.get("code", -1)
        if code != 0:
            msg = data.get("msg", "Unknown error")
            raise AdsPowerError(f"AdsPower {operation} failed (code={code}): {msg}")
        return data.get("data", {})

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def check_status(self) -> bool:
        """
        Ping the AdsPower API to confirm it is reachable.
        Returns True if healthy, raises AdsPowerError otherwise.
        """
        logger.info("Checking AdsPower status...")
        data = await self._get("/status")
        self._check_response(data, "status check")
        logger.info("AdsPower is running and reachable.")
        return True

    async def start_profile(self, profile_id: str) -> dict:
        """
        Start an AdsPower browser profile.

        Args:
            profile_id: The AdsPower profile/user ID (e.g. "abc123").

        Returns:
            Dict containing at minimum:
            {
                "ws": {
                    "puppeteer": "ws://127.0.0.1:<port>/devtools/browser/<id>",
                    "selenium": "127.0.0.1:<port>"
                },
                "debug_port": <port>
            }

        Raises:
            AdsPowerProfileNotFoundError: Profile ID does not exist.
            AdsPowerError: Any other API failure.
        """
        logger.info(f"Starting AdsPower profile: {profile_id}")
        data = await self._get(
            "/api/v1/browser/start",
            params={"user_id": profile_id, "open_tabs": 1, "ip_tab": 0},
        )

        # Profile not found comes back as code=0 but empty data in some versions,
        # and code!=0 in others — handle both.
        code = data.get("code", -1)
        if code != 0:
            msg = data.get("msg", "Unknown error")
            if "not found" in msg.lower() or "does not exist" in msg.lower():
                raise AdsPowerProfileNotFoundError(
                    f"Profile '{profile_id}' not found in AdsPower."
                )
            raise AdsPowerError(
                f"Failed to start profile '{profile_id}' (code={code}): {msg}"
            )

        profile_data = data.get("data", {})
        ws = profile_data.get("ws", {})
        if not ws or not ws.get("puppeteer"):
            raise AdsPowerError(
                f"Profile '{profile_id}' started but no WebSocket URL was returned. "
                "Is the profile already running?"
            )

        logger.info(
            f"Profile '{profile_id}' started. "
            f"CDP port: {profile_data.get('debug_port', 'unknown')}"
        )
        return profile_data

    async def stop_profile(self, profile_id: str) -> bool:
        """
        Stop a running AdsPower browser profile.

        Args:
            profile_id: The AdsPower profile/user ID.

        Returns:
            True on success.
        """
        logger.info(f"Stopping AdsPower profile: {profile_id}")
        data = await self._get(
            "/api/v1/browser/stop",
            params={"user_id": profile_id},
        )
        self._check_response(data, f"stop_profile({profile_id})")
        logger.info(f"Profile '{profile_id}' stopped.")
        return True

    async def get_browser_info(self, profile_id: str) -> dict:
        """
        Return information about a running browser profile without
        starting it (uses the /active endpoint).

        Args:
            profile_id: The AdsPower profile/user ID.

        Returns:
            Dict with browser status and connection info.
        """
        logger.info(f"Fetching browser info for profile: {profile_id}")
        data = await self._get(
            "/api/v1/browser/active",
            params={"user_id": profile_id},
        )
        result = self._check_response(data, f"get_browser_info({profile_id})")
        return result

    async def get_websocket(self, profile_id: str) -> str:
        """
        Start the profile (if not already running) and return the
        CDP Puppeteer WebSocket URL.

        Args:
            profile_id: The AdsPower profile/user ID.

        Returns:
            WebSocket URL string, e.g.:
            "ws://127.0.0.1:9222/devtools/browser/abc..."

        Raises:
            AdsPowerError: If the WebSocket URL cannot be obtained.
        """
        profile_data = await self.start_profile(profile_id)
        ws_url: str = profile_data["ws"]["puppeteer"]
        logger.info(f"CDP WebSocket URL obtained: {ws_url}")
        return ws_url
