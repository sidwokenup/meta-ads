"""
API Client

The Telegram bot's ONLY connection to the outside world.
Calls FastAPI endpoints via httpx. Never touches AdsPower, CDP, or Facebook directly.

All methods raise APIError on failure with a clean human-readable message.
"""

import httpx
from app.core.logger import logger

_DEFAULT_TIMEOUT = 120.0  # Graph API calls can take ~5-10s; health check is fast


class APIError(Exception):
    """Raised when FastAPI returns an error or is unreachable."""
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class APIClient:
    """
    Async httpx client that wraps all FastAPI endpoints.

    Usage:
        client = APIClient(base_url="http://127.0.0.1:8000")
        campaigns = await client.get_campaigns()
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        timeout: float = _DEFAULT_TIMEOUT,
        profile_id: str | None = None,
        account_id: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._profile_id = profile_id
        self._account_id = account_id

    # ------------------------------------------------------------------
    # Internal request helper
    # ------------------------------------------------------------------

    async def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self._base_url}{path}"
        logger.info(f"[APIClient] GET {path} params={params}")
        headers: dict[str, str] = {}
        if self._profile_id:
            headers["X-AdsPower-Profile-Id"] = self._profile_id
        if self._account_id:
            headers["X-Ad-Account-Id"] = self._account_id
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                r = await client.get(url, params=params, headers=headers)
        except httpx.ConnectError:
            raise APIError(
                "Cannot reach the FastAPI server. Is it running on port 8000?", 503
            )
        except httpx.TimeoutException:
            raise APIError(
                "FastAPI request timed out. The collector may be slow — try again.", 408
            )

        logger.info(f"[APIClient] {r.status_code} {path}")

        if r.status_code == 404:
            detail = r.json().get("detail", "Not found")
            raise APIError(detail, 404)
        if r.status_code == 401:
            raise APIError(
                "Facebook session expired. Please re-login in AdsPower.", 401
            )
        if r.status_code == 503:
            raise APIError(
                "AdsPower browser is not running. Please start your profile.", 503
            )
        if r.status_code >= 400:
            detail = r.json().get("detail", f"HTTP {r.status_code}")
            raise APIError(detail, r.status_code)

        return r.json()

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    async def get_health(self) -> dict:
        return await self._get("/health")

    async def get_account(self) -> dict:
        return await self._get("/account")

    async def get_campaigns(
        self,
        date_preset: str = "last_30d",
        campaign_status: str | None = None,
        objective: str | None = None,
        campaign_name: str | None = None,
    ) -> dict:
        params: dict = {"date_preset": date_preset}
        if campaign_status:
            params["campaign_status"] = campaign_status
        if objective:
            params["objective"] = objective
        if campaign_name:
            params["campaign_name"] = campaign_name
        return await self._get("/campaigns", params=params)

    async def get_campaign(self, name_or_id: str, date_preset: str = "last_30d") -> dict:
        return await self._get(f"/campaign/{name_or_id}", params={"date_preset": date_preset})

    async def get_report(self, date_preset: str = "last_30d") -> dict:
        return await self._get("/report", params={"date_preset": date_preset})

    async def update_campaign_status(self, campaign_id: str, status: str) -> dict:
        """Update campaign status via POST request"""
        import httpx
        
        url = f"{self._base_url}/campaign/{campaign_id}/status"
        logger.debug(f"[APIClient] POST {url} | status={status}")

        headers: dict[str, str] = {}
        if self._profile_id:
            headers["X-AdsPower-Profile-Id"] = self._profile_id
        if self._account_id:
            headers["X-Ad-Account-Id"] = self._account_id

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(
                    url,
                    headers=headers,
                    json={"status": status},
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                raise APIError(f"HTTP Error: {exc}", exc.response.status_code)
            except httpx.RequestError as exc:
                raise APIError(f"Failed to connect to FastAPI: {exc}", 500)
