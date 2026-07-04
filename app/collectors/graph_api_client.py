"""
Facebook Graph API Client

Executes Graph API calls from inside the authenticated AdsPower browser
using CDP Runtime.evaluate with fetch() and credentials: "include".

This is required because the access token embedded in Ads Manager is
an internal app token that only works with the browser's session cookies.
External httpx calls are rejected with OAuthException code=1.

By using Runtime.evaluate, the fetch() call runs in the browser context
with all cookies automatically attached — the API accepts it.
"""

import json
from typing import Optional

from app.collectors.cdp_client import CDPClient, CDPError
from app.core.logger import logger

GRAPH_API_BASE = "https://graph.facebook.com"
GRAPH_API_VERSION = "v22.0"

# All campaign fields mapped to CampaignModel
_CAMPAIGN_FIELDS = ",".join([
    "id",
    "name",
    "objective",
    "status",
    "effective_status",
    "bid_strategy",
    "daily_budget",
    "lifetime_budget",
    "start_time",
    "stop_time",
    (
        "insights.date_preset(last_30d)"
        "{spend,impressions,reach,frequency,clicks,ctr,cpc,cpm,"
        "actions,cost_per_action_type,purchase_roas,conversion_values,"
        "date_start,date_stop}"
    ),
])


class GraphAPIError(Exception):
    """Raised when the Graph API returns an error response."""


class GraphAPIAuthError(GraphAPIError):
    """Raised when the session or token is invalid/expired."""


class GraphAPIClient:
    """
    Facebook Graph API client that runs fetch() inside the AdsPower browser
    via CDP Runtime.evaluate. This ensures all session cookies are included.

    Usage:
        client = GraphAPIClient(cdp=cdp_instance, access_token="EAA...")
        campaigns = await client.get_campaigns(account_id="1559140139101704")
    """

    def __init__(
        self,
        cdp: CDPClient,
        access_token: str,
        api_version: str = GRAPH_API_VERSION,
    ) -> None:
        self._cdp = cdp
        self.access_token = access_token
        self._base = f"{GRAPH_API_BASE}/{api_version}"

    async def get_campaigns(
        self,
        account_id: str,
        date_preset: str = "last_30d",
        limit: int = 100,
    ) -> list[dict]:
        """
        Fetch all campaigns with metrics for an ad account.
        Handles pagination automatically.

        Args:
            account_id: Numeric ad account ID (without 'act_' prefix).
            date_preset: Reporting window for insights.
            limit: Results per page (max 100).

        Returns:
            List of raw campaign dicts ready for parser._parse_campaign_node().
        """
        fields = _CAMPAIGN_FIELDS.replace("last_30d", date_preset)
        url = (
            f"{self._base}/act_{account_id}/campaigns"
            f"?fields={fields}&limit={limit}&access_token={self.access_token}"
        )

        logger.info(
            f"Fetching campaigns via browser fetch(): "
            f"act_{account_id}, date_preset={date_preset}"
        )

        all_campaigns: list[dict] = []
        page_num = 1
        current_url: Optional[str] = url

        while current_url:
            logger.info(f"Fetching page {page_num}...")
            data = await self._browser_fetch(current_url)

            page_campaigns: list[dict] = data.get("data", [])
            all_campaigns.extend(page_campaigns)
            logger.info(
                f"Page {page_num}: {len(page_campaigns)} campaign(s). "
                f"Total: {len(all_campaigns)}."
            )

            # Follow pagination
            paging = data.get("paging", {})
            current_url = paging.get("next")
            if current_url:
                page_num += 1

        logger.info(f"Graph API complete. Total campaigns: {len(all_campaigns)}.")
        return all_campaigns

    async def _browser_fetch(self, url: str) -> dict:
        """
        Execute a fetch() call inside the browser via CDP Runtime.evaluate.
        Returns the parsed JSON response dict.
        """
        # Escape the URL for embedding in a JS string literal
        safe_url = url.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "")

        js = f"""
(async () => {{
    try {{
        const response = await fetch("{safe_url}", {{
            method: "GET",
            credentials: "include",
            headers: {{"Accept": "application/json"}}
        }});
        const text = await response.text();
        return JSON.stringify({{status: response.status, body: text}});
    }} catch (e) {{
        return JSON.stringify({{error: e.message}});
    }}
}})()
"""
        try:
            result = await self._cdp._send("Runtime.evaluate", {
                "expression": js,
                "awaitPromise": True,
                "returnByValue": True,
                "timeout": 30000,
            })
        except CDPError as exc:
            raise GraphAPIError(f"CDP Runtime.evaluate failed: {exc}") from exc

        raw_value: str = result.get("result", {}).get("value", "{}")

        try:
            envelope = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise GraphAPIError(
                f"CDP returned non-JSON envelope: {raw_value[:200]}"
            ) from exc

        if "error" in envelope:
            raise GraphAPIError(
                f"Browser fetch() failed: {envelope['error']}"
            )

        status = envelope.get("status", 0)
        body_str = envelope.get("body", "{}")

        try:
            data = json.loads(body_str)
        except json.JSONDecodeError as exc:
            raise GraphAPIError(
                f"Graph API returned non-JSON body (HTTP {status}): {body_str[:200]}"
            ) from exc

        if "error" in data:
            error = data["error"]
            code = error.get("code", 0)
            message = error.get("message", "Unknown error")
            if code in (190, 102, 104):
                raise GraphAPIAuthError(
                    f"Access token expired (code={code}): {message}"
                )
            raise GraphAPIError(f"Graph API error (code={code}): {message}")

        if status not in (200, 201):
            raise GraphAPIError(f"Graph API HTTP {status}: {body_str[:200]}")

        return data
