"""
Graph Client

Executes ALL Facebook Graph API requests from inside the authenticated
AdsPower browser using CDP Runtime.evaluate + fetch() with credentials:"include".

Rules:
  - NEVER use httpx / requests / aiohttp for Graph API calls.
  - ALWAYS use Runtime.evaluate.
  - ALWAYS include credentials:"include" in every fetch().
  - Accepts a BrowserSession (from SessionManager) per call — no stored state.
  - Returns parsed JSON dicts — no normalization here (that is CampaignMapper's job).

Supported methods:
  get_campaigns(session, account_id, date_preset, filters)
  get_campaign(session, account_id, campaign_name_or_id)
  get_adsets(session, account_id, date_preset)
  get_ads(session, account_id, date_preset)
  get_account(session, account_id)
  get_insights(session, account_id, date_preset)
"""

import json
from typing import Any, Optional

from app.core.logger import logger
from app.services.session_manager import BrowserSession

# ---------------------------------------------------------------------------
# Graph API constants
# ---------------------------------------------------------------------------

_GRAPH_BASE = "https://graph.facebook.com/v22.0"

# All campaign fields — includes insights nested query with configurable date_preset
_CAMPAIGN_FIELDS = (
    "id,name,objective,status,effective_status,buying_type,"
    "bid_strategy,daily_budget,lifetime_budget,start_time,stop_time,"
    "insights.date_preset(PRESET){"
    "spend,impressions,reach,frequency,clicks,unique_clicks,"
    "actions,cost_per_action_type,purchase_roas,conversion_values,"
    "ctr,cpc,cpm,date_start,date_stop"
    "}"
)

# Ad set fields with insights
_ADSET_FIELDS = (
    "id,name,status,effective_status,campaign_id,optimization_goal,"
    "bid_strategy,daily_budget,lifetime_budget,start_time,end_time,"
    "insights.date_preset(PRESET){"
    "spend,impressions,reach,clicks,ctr,cpc,cpm,"
    "actions,cost_per_action_type,date_start,date_stop"
    "}"
)

# Ad fields with insights
_AD_FIELDS = (
    "id,name,status,effective_status,adset_id,campaign_id,creative{id,name},"
    "insights.date_preset(PRESET){"
    "spend,impressions,reach,clicks,ctr,cpc,cpm,"
    "actions,cost_per_action_type,date_start,date_stop"
    "}"
)

# Account overview fields
_ACCOUNT_FIELDS = (
    "id,name,account_id,account_status,currency,timezone_name,"
    "business_name,amount_spent,balance,spend_cap"
)

# Insights fields (account-level)
_INSIGHTS_FIELDS = (
    "spend,impressions,reach,frequency,clicks,unique_clicks,"
    "actions,cost_per_action_type,purchase_roas,conversion_values,"
    "ctr,cpc,cpm,date_start,date_stop"
)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class GraphClientError(Exception):
    """Raised when a Graph API call fails."""


class GraphClientAuthError(GraphClientError):
    """Raised when the token is invalid or the session is expired."""


class GraphClientRateLimitError(GraphClientError):
    """Raised when Facebook rate-limits the request."""


# ---------------------------------------------------------------------------
# Graph Client
# ---------------------------------------------------------------------------


class GraphClient:
    """
    Facebook Graph API client.

    All API calls run inside the browser via CDP Runtime.evaluate + fetch()
    with credentials:"include". This is the ONLY correct way to use the
    window.__accessToken — it is bound to browser session cookies.

    Usage:
        client = GraphClient()
        campaigns = await client.get_campaigns(session, account_id="1559140139101704")
    """

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    async def get_campaigns(
        self,
        session: BrowserSession,
        account_id: str,
        date_preset: str = "last_30d",
        limit: int = 100,
        status_filter: Optional[list[str]] = None,
    ) -> list[dict]:
        """
        Fetch all campaigns for an ad account with performance metrics.

        Args:
            session: Live BrowserSession from SessionManager.
            account_id: Numeric ad account ID (no "act_" prefix).
            date_preset: Reporting window. Options:
                today | yesterday | last_7d | last_30d | last_90d |
                this_month | last_month | this_year | lifetime
            limit: Page size (max 100).
            status_filter: Optional list of statuses to filter, e.g. ["ACTIVE"].

        Returns:
            List of raw campaign dicts (ready for CampaignMapper).
        """
        logger.info(f"[GraphClient] get_campaigns: act_{account_id}, preset={date_preset}")

        fields = _CAMPAIGN_FIELDS.replace("PRESET", date_preset)
        url = f"{_GRAPH_BASE}/act_{account_id}/campaigns?fields={fields}&limit={limit}&access_token={session.access_token}"

        if status_filter:
            # Facebook requires effective_status as a JSON array: ["ACTIVE","PAUSED"]
            import json as _json
            url += f"&effective_status={_json.dumps(status_filter)}"

        results = await self._paginate(session, url)
        logger.info(f"[GraphClient] get_campaigns: returned {len(results)} campaigns.")
        return results

    async def get_campaign(
        self,
        session: BrowserSession,
        account_id: str,
        campaign_name_or_id: str,
        date_preset: str = "last_30d",
    ) -> Optional[dict]:
        """
        Fetch a single campaign by name or ID.

        Returns the first campaign matching the name (case-insensitive) or exact ID.
        Returns None if not found.
        """
        logger.info(f"[GraphClient] get_campaign: '{campaign_name_or_id}'")
        all_campaigns = await self.get_campaigns(session, account_id, date_preset)

        # Try exact ID match first
        for c in all_campaigns:
            if c.get("id") == campaign_name_or_id:
                return c

        # Then case-insensitive name match
        name_lower = campaign_name_or_id.lower()
        for c in all_campaigns:
            if c.get("name", "").lower() == name_lower:
                return c

        logger.warning(f"[GraphClient] Campaign not found: '{campaign_name_or_id}'")
        return None

    async def get_adsets(
        self,
        session: BrowserSession,
        account_id: str,
        date_preset: str = "last_30d",
        limit: int = 100,
    ) -> list[dict]:
        """
        Fetch all ad sets for an ad account with metrics.
        """
        logger.info(f"[GraphClient] get_adsets: act_{account_id}, preset={date_preset}")
        fields = _ADSET_FIELDS.replace("PRESET", date_preset)
        url = f"{_GRAPH_BASE}/act_{account_id}/adsets?fields={fields}&limit={limit}&access_token={session.access_token}"
        results = await self._paginate(session, url)
        logger.info(f"[GraphClient] get_adsets: returned {len(results)} ad sets.")
        return results

    async def get_ads(
        self,
        session: BrowserSession,
        account_id: str,
        date_preset: str = "last_30d",
        limit: int = 100,
    ) -> list[dict]:
        """
        Fetch all ads for an ad account with metrics.
        """
        logger.info(f"[GraphClient] get_ads: act_{account_id}, preset={date_preset}")
        fields = _AD_FIELDS.replace("PRESET", date_preset)
        url = f"{_GRAPH_BASE}/act_{account_id}/ads?fields={fields}&limit={limit}&access_token={session.access_token}"
        results = await self._paginate(session, url)
        logger.info(f"[GraphClient] get_ads: returned {len(results)} ads.")
        return results

    async def get_account(
        self,
        session: BrowserSession,
        account_id: str,
    ) -> dict:
        """
        Fetch account-level details (name, status, currency, spend, balance).
        """
        logger.info(f"[GraphClient] get_account: act_{account_id}")
        url = f"{_GRAPH_BASE}/act_{account_id}?fields={_ACCOUNT_FIELDS}&access_token={session.access_token}"
        data = await self._browser_fetch(session, url)
        logger.info(f"[GraphClient] get_account: account name='{data.get('name', '?')}'")
        return data

    async def get_insights(
        self,
        session: BrowserSession,
        account_id: str,
        date_preset: str = "last_30d",
        date_start: Optional[str] = None,
        date_stop: Optional[str] = None,
    ) -> dict:
        """
        Fetch account-level aggregated insights.

        Args:
            session: Live BrowserSession.
            account_id: Numeric ad account ID.
            date_preset: Standard preset (ignored if date_start/date_stop given).
            date_start: Custom range start, ISO format (YYYY-MM-DD).
            date_stop: Custom range end, ISO format (YYYY-MM-DD).

        Returns:
            Insights dict with spend, impressions, clicks, etc.
        """
        logger.info(f"[GraphClient] get_insights: act_{account_id}, preset={date_preset}")

        if date_start and date_stop:
            time_range = f"&time_range={{\"since\":\"{date_start}\",\"until\":\"{date_stop}\"}}"
            url = (
                f"{_GRAPH_BASE}/act_{account_id}/insights"
                f"?fields={_INSIGHTS_FIELDS}&level=account{time_range}"
                f"&access_token={session.access_token}"
            )
        else:
            url = (
                f"{_GRAPH_BASE}/act_{account_id}/insights"
                f"?fields={_INSIGHTS_FIELDS}&level=account&date_preset={date_preset}"
                f"&access_token={session.access_token}"
            )

        data = await self._browser_fetch(session, url)
        items = data.get("data", [])
        if items:
            logger.info("[GraphClient] get_insights: insights data received.")
            return items[0]
        logger.warning("[GraphClient] get_insights: no data returned.")
        return {}

    async def update_campaign_status(
        self,
        session: BrowserSession,
        campaign_id: str,
        status: str,
    ) -> dict:
        """
        Update the status of a campaign.
        status should be one of: ACTIVE, PAUSED, DELETED, ARCHIVED
        """
        logger.info(f"[GraphClient] update_campaign_status: {campaign_id} -> {status}")
        # Add access token in body instead of URL for POST requests
        url = f"{_GRAPH_BASE}/{campaign_id}"
        body = f"status={status}&access_token={session.access_token}"
        
        data = await self._browser_fetch(session, url, method="POST", body=body)
        logger.info(f"[GraphClient] update_campaign_status: success")
        return data

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    async def _paginate(self, session: BrowserSession, url: str) -> list[dict]:
        """
        Follow Facebook's cursor-based pagination until all pages are fetched.
        Returns a flat list of all items from all pages.
        """
        all_items: list[dict] = []
        current_url: Optional[str] = url
        page = 1

        while current_url:
            logger.info(f"[GraphClient] Fetching page {page}...")
            data = await self._browser_fetch(session, current_url)

            items: list[dict] = data.get("data", [])
            all_items.extend(items)
            logger.info(f"[GraphClient] Page {page}: {len(items)} items. Total: {len(all_items)}.")

            next_url = data.get("paging", {}).get("next")
            current_url = next_url
            if current_url:
                page += 1

        return all_items

    # ------------------------------------------------------------------
    # Core: browser fetch via CDP Runtime.evaluate
    # ------------------------------------------------------------------

    async def _browser_fetch(self, session: BrowserSession, url: str, method: str = "GET", body: Optional[str] = None) -> dict:
        """
        Execute a fetch() call INSIDE the browser via CDP Runtime.evaluate.

        This is the ONLY correct way to call the Graph API with window.__accessToken.
        The token only works with the browser's session cookies attached.
        credentials:"include" ensures all cookies are automatically sent.

        Args:
            session: BrowserSession with live CDPClient and access token.
            url: Full Graph API URL including access_token query param.
            method: HTTP method (GET, POST).
            body: Optional body string for POST requests.

        Returns:
            Parsed JSON response dict.

        Raises:
            GraphClientAuthError: Token invalid or session expired.
            GraphClientRateLimitError: Facebook rate limit hit.
            GraphClientError: Any other Graph API or CDP failure.
        """
        logger.info(f"[GraphClient] Executing Graph API call via Runtime.evaluate... ({method})")

        # Escape URL safely for embedding in a JS string literal
        safe_url = url.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "").replace("\r", "")
        
        fetch_options = f"""{{
            method: "{method}",
            credentials: "include",
            headers: {{"Accept": "application/json"}}
"""
        if method == "POST" and body:
            safe_body = body.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "").replace("\r", "")
            fetch_options += f""",
            body: "{safe_body}",
            headers: {{"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}}
"""
        fetch_options += "        }"

        js = f"""
(async () => {{
    try {{
        const response = await fetch("{safe_url}", {fetch_options});
        const text = await response.text();
        return JSON.stringify({{status: response.status, body: text}});
    }} catch (e) {{
        return JSON.stringify({{error: e.message || String(e)}});
    }}
}})()
"""
        try:
            result = await session.cdp._send("Runtime.evaluate", {
                "expression": js,
                "awaitPromise": True,
                "returnByValue": True,
                "timeout": 30000,
            })
        except Exception as exc:
            raise GraphClientError(f"CDP Runtime.evaluate failed: {exc}") from exc

        raw_value: str = result.get("result", {}).get("value", "{}")

        # Parse the envelope {status, body} or {error}
        try:
            envelope = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise GraphClientError(
                f"CDP returned non-JSON envelope: {raw_value[:300]}"
            ) from exc

        if "error" in envelope:
            raise GraphClientError(f"Browser fetch() threw: {envelope['error']}")

        status: int = envelope.get("status", 0)
        body_str: str = envelope.get("body", "{}")

        logger.info(f"[GraphClient] Graph API response: HTTP {status}, body={len(body_str)} chars.")

        # Parse the actual Graph API JSON body
        try:
            data = json.loads(body_str)
        except json.JSONDecodeError:
            # Facebook occasionally sends NDJSON (multiple objects separated by newlines)
            data = self._parse_ndjson(body_str)

        # Handle Graph API error object
        if "error" in data:
            error: dict = data["error"]
            code: int = error.get("code", 0)
            message: str = error.get("message", "Unknown Graph API error")

            # Auth / token errors
            if code in (190, 102, 104, 1):
                raise GraphClientAuthError(
                    f"Token invalid or session expired (code={code}): {message}"
                )
            # Rate limit
            if code in (4, 17, 32, 613):
                raise GraphClientRateLimitError(
                    f"Graph API rate limit (code={code}): {message}"
                )
            raise GraphClientError(f"Graph API error (code={code}): {message}")

        if status not in (200, 201):
            raise GraphClientError(f"Graph API HTTP {status}: {body_str[:300]}")

        return data

    @staticmethod
    def _parse_ndjson(body: str) -> dict:
        """
        Parse NDJSON (newline-delimited JSON) body from Facebook.
        Facebook sometimes sends multiple JSON objects per response.
        We take the first valid JSON object that contains "data" or "error".
        """
        for line in body.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                continue
        return {}
