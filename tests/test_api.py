"""
API Integration Tests

Tests the FastAPI layer using httpx AsyncClient with real CollectorService calls.
These are LIVE tests — they require AdsPower to be running with profile k1dvlyr0
and Facebook Ads Manager open.

Usage:
    cd d:\\metaadsadata\\meta-ads-reporter
    python tests/test_api.py --profile k1dvlyr0 --account 1559140139101704

What is tested:
    GET /                        — 200, correct schema
    GET /health                  — 200, browser=connected
    GET /campaigns               — 200, list not empty, schema valid
    GET /campaigns?date_preset=today
    GET /campaigns?campaign_status=PAUSED
    GET /campaign/{name}         — 200, full campaign object
    GET /campaign/{name}/raw     — 200, raw dict contains 'id' and 'name'
    GET /campaign/NOTEXIST       — 404
    GET /account                 — 200, account_id present
    GET /report                  — 200, totals > 0
"""

import argparse
import asyncio
import os
import sys
import time

sys.path.insert(0, ".")

import httpx
from rich.console import Console
from rich.table import Table

console = Console()

BASE_URL = "http://127.0.0.1:8000"


# ---------------------------------------------------------------------------
# Test runner helpers
# ---------------------------------------------------------------------------


class TestResult:
    def __init__(self, name: str, passed: bool, detail: str = "", elapsed_ms: float = 0.0):
        self.name = name
        self.passed = passed
        self.detail = detail
        self.elapsed_ms = elapsed_ms


results: list[TestResult] = []


async def test(name: str, coro) -> TestResult:
    console.print(f"  [dim]Running:[/dim] {name}")
    t0 = time.perf_counter()
    try:
        await coro
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        r = TestResult(name, True, "OK", elapsed)
        console.print(f"  [green]PASS[/green] {name} ({elapsed}ms)")
    except AssertionError as exc:
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        r = TestResult(name, False, str(exc), elapsed)
        console.print(f"  [red]FAIL[/red] {name}: {exc}")
    except Exception as exc:
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        r = TestResult(name, False, f"{type(exc).__name__}: {exc}", elapsed)
        console.print(f"  [red]ERROR[/red] {name}: {type(exc).__name__}: {exc}")
    results.append(r)
    return r


# ---------------------------------------------------------------------------
# Individual test coroutines
# ---------------------------------------------------------------------------


async def test_root(client: httpx.AsyncClient):
    r = await client.get("/")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    assert data["project"] == "Meta Ads Reporter", "project field wrong"
    assert data["version"] == "1.0.0", "version field missing"
    assert data["status"] == "running", "status field wrong"


async def test_health(client: httpx.AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    assert "status" in data, "missing status field"
    assert "browser" in data, "missing browser field"
    assert "facebook_session" in data, "missing facebook_session field"
    assert data["browser"] == "connected", f"browser={data['browser']} (is AdsPower running?)"
    assert data["facebook_session"] == "active", f"session={data['facebook_session']} (is FB logged in?)"


async def test_campaigns(client: httpx.AsyncClient):
    r = await client.get("/campaigns")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    assert "campaigns" in data, "missing campaigns field"
    assert "total" in data, "missing total field"
    assert isinstance(data["campaigns"], list), "campaigns not a list"
    assert data["total"] > 0, "No campaigns returned"
    # Validate first campaign schema
    c = data["campaigns"][0]
    for field in ["campaign_id", "campaign_name", "status", "insights"]:
        assert field in c, f"missing field: {field}"
    ins = c["insights"]
    for metric in ["spend", "impressions", "ctr", "cpc", "cpm", "roas"]:
        assert metric in ins, f"missing insight field: {metric}"


async def test_campaigns_today(client: httpx.AsyncClient):
    r = await client.get("/campaigns?date_preset=today")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    assert data["date_preset"] == "today", "date_preset not reflected in response"


async def test_campaigns_filter_paused(client: httpx.AsyncClient):
    r = await client.get("/campaigns?campaign_status=PAUSED")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    # All returned campaigns should be PAUSED (or response may be empty)
    for c in data["campaigns"]:
        assert c["effective_status"] == "PAUSED", (
            f"Expected PAUSED, got {c['effective_status']} for {c['campaign_name']}"
        )


async def test_campaign_by_name(client: httpx.AsyncClient, campaign_name: str):
    r = await client.get(f"/campaign/{campaign_name}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    assert "campaign_id" in data, "missing campaign_id"
    assert "insights" in data, "missing insights"
    assert data["campaign_name"].lower() == campaign_name.lower(), (
        f"Name mismatch: {data['campaign_name']} != {campaign_name}"
    )


async def test_campaign_raw(client: httpx.AsyncClient, campaign_name: str):
    r = await client.get(f"/campaign/{campaign_name}/raw")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    assert "id" in data, "raw response missing 'id'"
    assert "name" in data, "raw response missing 'name'"


async def test_campaign_not_found(client: httpx.AsyncClient):
    r = await client.get("/campaign/THIS_CAMPAIGN_DOES_NOT_EXIST_XYZ123")
    assert r.status_code == 404, f"Expected 404, got {r.status_code}"


async def test_account(client: httpx.AsyncClient):
    r = await client.get("/account")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    for field in ["account_id", "account_name", "currency", "total_campaigns"]:
        assert field in data, f"missing field: {field}"
    assert data["total_campaigns"] > 0, "total_campaigns is 0"


async def test_report(client: httpx.AsyncClient):
    r = await client.get("/report")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    for field in [
        "account_id", "date_preset", "generated_at",
        "total_campaigns", "total_spend", "avg_ctr",
        "avg_cpc", "avg_cpm", "avg_roas", "top_campaigns",
    ]:
        assert field in data, f"missing field: {field}"
    assert data["total_campaigns"] > 0, "total_campaigns is 0"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def run_tests(profile_id: str, account_id: str) -> None:
    headers = {
        "X-AdsPower-Profile-Id": profile_id,
        "X-Ad-Account-Id": account_id,
    }

    console.print(f"\n[bold cyan]Meta Ads Reporter — API Tests[/bold cyan]")
    console.print(f"  Target     : [bold]{BASE_URL}[/bold]")
    console.print(f"  Profile    : [bold]{profile_id}[/bold]")
    console.print(f"  Account    : [bold]{account_id}[/bold]")
    console.print(f"\n  [dim]Note: The API server must already be running.[/dim]")
    console.print(f"  [dim]Start with: uvicorn app.main:app --reload --port 8000[/dim]\n")

    # First get a campaign name from /campaigns to use in targeted tests
    first_campaign_name: str | None = None

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=120.0, headers=headers) as client:

        # System
        await test("GET /", test_root(client))
        await test("GET /health", test_health(client))

        # Campaigns
        r = await test("GET /campaigns", test_campaigns(client))
        # Try to grab a campaign name for subsequent tests
        if r.passed:
            try:
                resp = await client.get("/campaigns")
                items = resp.json().get("campaigns", [])
                if items:
                    first_campaign_name = items[0]["campaign_name"]
                    console.print(f"\n  [dim]Using campaign name for targeted tests: '{first_campaign_name}'[/dim]\n")
            except Exception:
                pass

        await test("GET /campaigns?date_preset=today", test_campaigns_today(client))
        await test("GET /campaigns?campaign_status=PAUSED", test_campaigns_filter_paused(client))

        # Single campaign (use first found name)
        if first_campaign_name:
            await test(
                f"GET /campaign/{{name}} -> '{first_campaign_name[:30]}'",
                test_campaign_by_name(client, first_campaign_name),
            )
            await test(
                f"GET /campaign/{{name}}/raw",
                test_campaign_raw(client, first_campaign_name),
            )
        else:
            console.print("  [yellow]SKIP[/yellow] Campaign-specific tests (no campaigns found).")

        await test("GET /campaign/NOT_EXIST -> 404", test_campaign_not_found(client))

        # Account
        await test("GET /account", test_account(client))

        # Report
        await test("GET /report", test_report(client))

    # ---------------------------------------------------------------------------
    # Summary table
    # ---------------------------------------------------------------------------
    console.print()
    table = Table(title="Test Results", header_style="bold cyan", border_style="dim")
    table.add_column("Test", width=52)
    table.add_column("Result", justify="center", width=8)
    table.add_column("Time (ms)", justify="right", width=10)
    table.add_column("Detail", width=30)

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    for r in results:
        icon = "[green]PASS[/green]" if r.passed else "[red]FAIL[/red]"
        table.add_row(r.name[:52], icon, f"{r.elapsed_ms}", r.detail[:30])

    console.print(table)
    console.print(
        f"\n  [bold]{'[green]ALL PASSED' if failed == 0 else '[red]FAILED'}[/bold]: "
        f"{passed}/{len(results)} tests passed."
    )

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Meta Ads Reporter API Tests")
    parser.add_argument("--profile", default="k1dvlyr0", help="AdsPower profile ID")
    parser.add_argument("--account", default="1559140139101704", help="Facebook ad account ID")
    args = parser.parse_args()
    asyncio.run(run_tests(args.profile, args.account))
