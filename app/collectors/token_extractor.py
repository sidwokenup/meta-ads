"""
Token Extractor

Extracts the Facebook Graph API access token that is embedded in the
Ads Manager page HTML as:

    window.__accessToken = "EAA..."

Strategy:
  1. Connect to the AdsPower browser via CDP.
  2. Use CDP's Network.getCookies to get all facebook.com cookies from
     the live, authenticated browser session.
  3. Use httpx with those cookies to fetch the Ads Manager HTML page.
  4. Regex-extract window.__accessToken from the HTML.

This is simpler and more reliable than intercepting GraphQL requests.
The extracted token is valid for 24 hours (window.__accessTokenExpirySecondsRemaining).
"""

import re
from typing import Optional

import httpx

from app.collectors.cdp_client import CDPClient, CDPError
from app.core.logger import logger

# Regex patterns for extracting token fields from Ads Manager HTML
_TOKEN_RE = re.compile(r'window\.__accessToken\s*=\s*"([^"]+)"')
_EXPIRY_RE = re.compile(r'window\.__accessTokenExpirySecondsRemaining\s*=\s*(\d+)')
_ACCOUNT_RE = re.compile(r'"ad_account_id"\s*:\s*"(\d+)"')

# Ads Manager URL template
_ADS_MANAGER_URL = (
    "https://adsmanager.facebook.com/adsmanager/manage/campaigns?act={account_id}&business_id={account_id}"
)

_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Dest": "document",
}


class TokenExtractionError(Exception):
    """Raised when the access token cannot be extracted."""


class TokenResult:
    """Container for the extracted access token and metadata."""

    def __init__(
        self,
        token: str,
        expiry_seconds: Optional[int] = None,
        account_id: Optional[str] = None,
    ) -> None:
        self.token = token
        self.expiry_seconds = expiry_seconds
        self.account_id = account_id

    def __repr__(self) -> str:
        return (
            f"TokenResult(token={self.token[:20]}..., "
            f"expiry={self.expiry_seconds}s, account={self.account_id})"
        )


async def extract_token_via_cdp(
    cdp: CDPClient,
    account_id: str,
) -> TokenResult:
    """
    Extract the Facebook access token from the Ads Manager page using:
    1. CDP Network.getCookies → live browser session cookies
    2. httpx GET → Ads Manager HTML
    3. Regex → window.__accessToken

    Args:
        cdp: Connected CDPClient instance (browser already attached).
        account_id: Ad account ID (numeric, without 'act_' prefix).

    Returns:
        TokenResult with the access token and metadata.

    Raises:
        TokenExtractionError: If the token cannot be found.
    """
    logger.info("Extracting access token from Ads Manager page HTML...")

    # Step 1: Get cookies from the live browser session via CDP
    cookies = await _get_cookies_via_cdp(cdp)

    # Step 2: Fetch the Ads Manager page with those cookies
    html = await _fetch_ads_manager_html(account_id, cookies)

    # Step 3: Extract the token
    return _extract_token_from_html(html)


async def _get_cookies_via_cdp(cdp: CDPClient) -> dict[str, str]:
    """
    Use CDP Network.getCookies to retrieve facebook.com session cookies
    from the live browser.
    """
    logger.info("Retrieving session cookies from AdsPower browser via CDP...")
    try:
        result = await cdp._send(
            "Network.getCookies",
            {"urls": [
                "https://adsmanager.facebook.com",
                "https://www.facebook.com",
                "https://facebook.com",
                "https://business.facebook.com",
            ]},
        )
    except CDPError as exc:
        raise TokenExtractionError(
            f"Failed to retrieve cookies from browser via CDP: {exc}"
        ) from exc

    raw_cookies: list[dict] = result.get("cookies", [])
    cookies: dict[str, str] = {c["name"]: c["value"] for c in raw_cookies}

    # Log which critical cookies are present (without values)
    critical = {"c_user", "xs", "datr", "fr"}
    found = critical & set(cookies.keys())
    missing = critical - found
    logger.info(
        f"Cookies retrieved: {len(cookies)} total. "
        f"Critical: {found}. "
        + (f"Missing: {missing}." if missing else "All critical cookies present.")
    )

    if "c_user" not in cookies or "xs" not in cookies:
        raise TokenExtractionError(
            "Missing critical Facebook session cookies (c_user, xs). "
            "The browser may not be logged in to Facebook."
        )

    return cookies


async def _fetch_ads_manager_html(account_id: str, cookies: dict[str, str]) -> str:
    """
    Use httpx with live browser cookies to fetch the Ads Manager HTML page.
    The page embeds window.__accessToken if the session is valid.
    """
    url = _ADS_MANAGER_URL.format(account_id=account_id)
    logger.info(f"Fetching Ads Manager page: {url}")

    async with httpx.AsyncClient(
        headers=_FETCH_HEADERS,
        cookies=cookies,
        follow_redirects=True,  # allow Facebook's URL normalization redirects
        timeout=30.0,
    ) as client:
        try:
            response = await client.get(url)
        except httpx.RequestError as exc:
            raise TokenExtractionError(
                f"HTTP request to Ads Manager failed: {exc}"
            ) from exc

    # A redirect to the login page means session expired
    final_url = str(response.url)
    if "login" in final_url or "checkpoint" in final_url:
        raise TokenExtractionError(
            f"Redirected to login: {final_url}. "
            "Facebook session may have expired. Please re-login in AdsPower."
        )

    if response.status_code != 200:
        raise TokenExtractionError(
            f"Ads Manager returned HTTP {response.status_code}. "
            "Cannot extract access token."
        )

    logger.info(f"Page fetched successfully ({len(response.text):,} characters).")
    return response.text


def _extract_token_from_html(html: str) -> TokenResult:
    """
    Extract window.__accessToken, window.__accessTokenExpirySecondsRemaining,
    and ad_account_id from the Ads Manager HTML page.
    """
    token_match = _TOKEN_RE.search(html)
    if not token_match:
        raise TokenExtractionError(
            "window.__accessToken not found in Ads Manager HTML. "
            "The session may have expired or Facebook changed the page structure."
        )

    token = token_match.group(1)

    expiry_match = _EXPIRY_RE.search(html)
    expiry_seconds = int(expiry_match.group(1)) if expiry_match else None

    account_match = _ACCOUNT_RE.search(html)
    account_id = account_match.group(1) if account_match else None

    logger.info(
        f"Access token extracted successfully. "
        f"Expires in: {expiry_seconds}s (~{(expiry_seconds or 0) // 3600}h). "
        f"Account: {account_id}."
    )

    return TokenResult(
        token=token,
        expiry_seconds=expiry_seconds,
        account_id=account_id,
    )
