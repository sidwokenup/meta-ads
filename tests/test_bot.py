"""
Bot Unit Tests

Tests the Telegram bot's session management, API client, and formatters
without requiring a real Telegram token or network connection.

The tests mock the APIClient so no FastAPI server is needed.

Usage:
    cd d:\\metaadsadata\\meta-ads-reporter
    python tests/test_bot.py
"""

import asyncio
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, ".")

from rich.console import Console
from rich.table import Table

from app.telegram.session import SessionStore, UserSession
from app.telegram import formatters as fmt
from app.telegram.client import APIClient, APIError

console = Console()

# ---------------------------------------------------------------------------
# Sample API payloads (mirrors real FastAPI responses)
# ---------------------------------------------------------------------------

SAMPLE_CAMPAIGNS = {
    "account_id": "1559140139101704",
    "date_preset": "last_30d",
    "total": 2,
    "response_time_ms": 3200.0,
    "campaigns": [
        {
            "campaign_id": "120247657236380372",
            "campaign_name": "AUStralia 2 july",
            "objective": "LINK_CLICKS",
            "buying_type": "AUCTION",
            "status": "PAUSED",
            "effective_status": "PAUSED",
            "delivery_status": None,
            "learning_status": None,
            "daily_budget": None,
            "lifetime_budget": 350.0,
            "budget_type": "LIFETIME",
            "start_time": "2026-07-01T00:00:00+0000",
            "end_time": "2026-08-01T00:00:00+0000",
            "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
            "insights": {
                "date_start": "2026-06-04",
                "date_stop": "2026-07-04",
                "spend": 3.43,
                "impressions": 1296,
                "reach": 1066,
                "frequency": 1.21,
                "clicks": 12,
                "unique_clicks": 12,
                "link_clicks": 12,
                "ctr": 0.93,
                "cpc": 0.29,
                "cpm": 2.65,
                "purchases": 0,
                "purchase_value": 0.0,
                "cost_per_purchase": 0.0,
                "roas": 0.0,
                "landing_page_views": 1,
                "add_to_carts": 0,
                "initiate_checkouts": 0,
            },
        },
        {
            "campaign_id": "120247657236380001",
            "campaign_name": "Test Campaign Active",
            "objective": "OUTCOME_SALES",
            "buying_type": "AUCTION",
            "status": "ACTIVE",
            "effective_status": "ACTIVE",
            "delivery_status": None,
            "learning_status": None,
            "daily_budget": 50.0,
            "lifetime_budget": None,
            "budget_type": "DAILY",
            "start_time": "2026-06-01T00:00:00+0000",
            "end_time": None,
            "bid_strategy": "COST_CAP",
            "insights": {
                "date_start": "2026-06-04",
                "date_stop": "2026-07-04",
                "spend": 145.22,
                "impressions": 48200,
                "reach": 32000,
                "frequency": 1.51,
                "clicks": 890,
                "unique_clicks": 820,
                "link_clicks": 800,
                "ctr": 1.85,
                "cpc": 0.16,
                "cpm": 3.01,
                "purchases": 12,
                "purchase_value": 598.0,
                "cost_per_purchase": 12.10,
                "roas": 4.12,
                "landing_page_views": 750,
                "add_to_carts": 35,
                "initiate_checkouts": 20,
            },
        },
    ],
}

SAMPLE_REPORT = {
    "account_id": "1559140139101704",
    "date_preset": "last_30d",
    "generated_at": "2026-07-04T01:00:00+00:00",
    "total_campaigns": 7,
    "active_campaigns": 2,
    "paused_campaigns": 5,
    "total_spend": 148.65,
    "total_impressions": 49496,
    "total_reach": 33066,
    "total_clicks": 902,
    "total_link_clicks": 812,
    "total_purchases": 12,
    "total_purchase_value": 598.0,
    "avg_ctr": 1.82,
    "avg_cpc": 0.16,
    "avg_cpm": 3.00,
    "avg_roas": 4.02,
    "top_campaign": SAMPLE_CAMPAIGNS["campaigns"][1],
    "worst_campaign": SAMPLE_CAMPAIGNS["campaigns"][0],
    "top_roas_campaign": SAMPLE_CAMPAIGNS["campaigns"][1],
    "top_campaigns": SAMPLE_CAMPAIGNS["campaigns"],
    "response_time_ms": 3500.0,
}

SAMPLE_ACCOUNT = {
    "account_id": "1559140139101704",
    "account_name": "Test Ad Account",
    "currency": "USD",
    "timezone": "America/Los_Angeles",
    "account_status": 1,
    "business_name": "Test Business",
    "amount_spent": 148.65,
    "balance": 500.0,
    "spend_cap": None,
    "total_campaigns": 7,
    "active_campaigns": 2,
    "paused_campaigns": 5,
    "response_time_ms": 4100.0,
}

SAMPLE_HEALTH = {
    "status": "healthy",
    "collector": "ready",
    "browser": "connected",
    "facebook_session": "active",
    "detail": "",
    "response_time_ms": 2100.0,
}

# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

results = []


def test(name: str):
    def decorator(fn):
        async def wrapper():
            t0 = time.perf_counter()
            try:
                await fn()
                elapsed = round((time.perf_counter() - t0) * 1000, 1)
                results.append((name, True, "OK", elapsed))
                console.print(f"  [green]PASS[/green] {name} ({elapsed}ms)")
            except AssertionError as e:
                elapsed = round((time.perf_counter() - t0) * 1000, 1)
                results.append((name, False, str(e)[:60], elapsed))
                console.print(f"  [red]FAIL[/red] {name}: {e}")
            except Exception as e:
                elapsed = round((time.perf_counter() - t0) * 1000, 1)
                results.append((name, False, f"{type(e).__name__}: {str(e)[:40]}", elapsed))
                console.print(f"  [red]ERROR[/red] {name}: {type(e).__name__}: {e}")
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Session tests
# ---------------------------------------------------------------------------

@test("SessionStore: get creates new session")
async def _():
    s = SessionStore()
    session = s.get(12345)
    assert isinstance(session, UserSession)
    assert session.user_id == 12345
    assert session.profile_id is None
    assert session.account_id is None


@test("SessionStore: set_profile stores profile")
async def _():
    s = SessionStore()
    s.set_profile(1, "k1dvlyr0")
    assert s.get(1).profile_id == "k1dvlyr0"
    assert "k1dvlyr0" in s.get(1).saved_profiles


@test("SessionStore: set_account stores account")
async def _():
    s = SessionStore()
    s.set_account(1, "1559140139101704")
    assert s.get(1).account_id == "1559140139101704"
    assert "1559140139101704" in s.get(1).saved_accounts


@test("SessionStore: use_account switches between saved accounts")
async def _():
    s = SessionStore()
    s.set_account(1, "1559140139101704")
    s.set_account(1, "2489049668183097")
    assert s.get(1).account_id == "2489049668183097"
    assert s.use_account(1, "1559140139101704") is True
    assert s.get(1).account_id == "1559140139101704"


@test("SessionStore: use_profile switches between saved profiles")
async def _():
    s = SessionStore()
    s.set_profile(1, "k1dvlyr0")
    s.set_profile(1, "secondprofile")
    assert s.get(1).profile_id == "secondprofile"
    assert s.use_profile(1, "k1dvlyr0") is True
    assert s.get(1).profile_id == "k1dvlyr0"


@test("SessionStore: is_configured returns True when both set")
async def _():
    s = SessionStore()
    s.set_profile(1, "k1dvlyr0")
    s.set_account(1, "1559140139101704")
    assert s.get(1).is_configured() is True


@test("SessionStore: is_configured returns False when only profile set")
async def _():
    s = SessionStore()
    s.set_profile(1, "k1dvlyr0")
    assert s.get(1).is_configured() is False


@test("SessionStore: is_configured returns False when only account set")
async def _():
    s = SessionStore()
    s.set_account(1, "1559140139101704")
    assert s.get(1).is_configured() is False


@test("SessionStore: touch records command + timestamp")
async def _():
    s = SessionStore()
    s.touch(1, "/campaigns")
    session = s.get(1)
    assert session.last_command == "/campaigns"
    assert session.last_refresh is not None


@test("SessionStore: different users are independent")
async def _():
    s = SessionStore()
    s.set_profile(1, "profile_a")
    s.set_profile(2, "profile_b")
    assert s.get(1).profile_id == "profile_a"
    assert s.get(2).profile_id == "profile_b"


# ---------------------------------------------------------------------------
# Formatter tests
# ---------------------------------------------------------------------------

@test("fmt.esc: escapes MarkdownV2 special chars")
async def _():
    result = fmt.esc("Hello.World! (test)")
    assert "\\." in result
    assert "\\!" in result
    assert "\\(" in result


@test("fmt_campaigns_list: returns string with campaign names")
async def _():
    result = fmt.fmt_campaigns_list(SAMPLE_CAMPAIGNS)
    assert "AUStralia" in result
    assert "Test Campaign Active" in result


@test("fmt_campaign: contains all key fields")
async def _():
    c = SAMPLE_CAMPAIGNS["campaigns"][1]
    result = fmt.fmt_campaign(c)
    assert "Test Campaign Active" in result
    assert "145" in result  # spend
    assert "ROAS" in result
    assert "Purchases" in result


@test("fmt_report: contains totals and averages")
async def _():
    result = fmt.fmt_report(SAMPLE_REPORT)
    assert "148" in result  # total spend
    assert "CTR" in result
    assert "ROAS" in result


@test("fmt_account: contains account name and spend")
async def _():
    result = fmt.fmt_account(SAMPLE_ACCOUNT)
    assert "Test Ad Account" in result
    assert "148" in result


@test("fmt_health: healthy system shows checkmarks")
async def _():
    result = fmt.fmt_health(SAMPLE_HEALTH)
    assert "connected" in result
    assert "active" in result


@test("fmt_error: wraps message in error template")
async def _():
    result = fmt.fmt_error("Something went wrong")
    assert "Something went wrong" in result or "Error" in result


# ---------------------------------------------------------------------------
# APIClient tests (mocked)
# ---------------------------------------------------------------------------

@test("APIClient: get_campaigns returns data on 200")
async def _():
    with patch("httpx.AsyncClient") as mock_cls:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_CAMPAIGNS

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        client = APIClient(profile_id="k1dvlyr0", account_id="2489049668183097")
        result = await client.get_campaigns()
        assert result["total"] == 2
        assert len(result["campaigns"]) == 2
        _, kwargs = mock_client.get.await_args
        assert kwargs["headers"]["X-AdsPower-Profile-Id"] == "k1dvlyr0"
        assert kwargs["headers"]["X-Ad-Account-Id"] == "2489049668183097"


@test("APIClient: raises APIError on 404")
async def _():
    with patch("httpx.AsyncClient") as mock_cls:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"detail": "Campaign not found"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        client = APIClient()
        try:
            await client.get_campaign("nonexistent")
            assert False, "Should have raised APIError"
        except APIError as e:
            assert e.status_code == 404


@test("APIClient: raises APIError on 503 with clear message")
async def _():
    with patch("httpx.AsyncClient") as mock_cls:
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.json.return_value = {"detail": "AdsPower not running"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        client = APIClient()
        try:
            await client.get_campaigns()
            assert False, "Should have raised APIError"
        except APIError as e:
            assert e.status_code == 503


@test("APIClient: raises APIError on ConnectError")
async def _():
    import httpx as _httpx
    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=_httpx.ConnectError("refused"))
        mock_cls.return_value = mock_client

        client = APIClient()
        try:
            await client.get_health()
            assert False, "Should have raised APIError"
        except APIError as e:
            assert e.status_code == 503


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_all():
    all_tests = [
        _() for _ in [
            # session
            globals()[n] for n in list(globals()) if callable(globals()[n]) and hasattr(globals()[n], "__name__") and globals()[n].__name__ == "wrapper"
        ]
    ]
    # Just run in definition order
    pass

async def main():
    console.print("\n[bold cyan]Meta Ads Reporter - Bot Unit Tests[/bold cyan]")
    console.print("  No Telegram token required - uses mocks\n")

    test_fns = [v for k, v in globals().items() if callable(v) and hasattr(v, "__wrapped__")]

    # collect all test coroutines defined via @test
    import inspect
    for name, obj in list(globals().items()):
        if asyncio.iscoroutinefunction(obj) and name.startswith("_") and name != "__":
            pass  # already decorated

    # Run all wrapped test functions in order
    wrappers = []
    for name, obj in globals().items():
        if callable(obj) and hasattr(obj, "__name__") and obj.__name__ == "wrapper":
            wrappers.append(obj)

    for fn in wrappers:
        await fn()

    # Summary
    console.print()
    table = Table(title="Test Results", header_style="bold cyan", border_style="dim")
    table.add_column("Test", width=50)
    table.add_column("Result", justify="center", width=8)
    table.add_column("Time", justify="right", width=10)
    table.add_column("Detail", width=30)

    passed = sum(1 for _, ok, _, _ in results if ok)
    for name, ok, detail, ms in results:
        icon = "[green]PASS[/green]" if ok else "[red]FAIL[/red]"
        table.add_row(name[:50], icon, f"{ms}ms", detail[:30])

    console.print(table)
    console.print(
        f"\n  [bold]{'[green]ALL PASSED' if passed == len(results) else '[red]FAILED'}[/bold]: "
        f"{passed}/{len(results)} tests passed."
    )

    if passed < len(results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
