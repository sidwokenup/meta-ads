"""
test_collector.py

Standalone test script for Phase 2.

Usage:
    python test_collector.py --profile <ADSPOWER_PROFILE_ID> --account <AD_ACCOUNT_ID>

Example:
    python test_collector.py --profile abc123 --account 123456789

This script:
  1. Starts the AdsPower browser profile.
  2. Connects to the browser via CDP.
  3. Navigates to Ads Manager.
  4. Intercepts GraphQL network responses.
  5. Parses campaign metrics.
  6. Prints a clean summary table for each campaign.

Does NOT print raw JSON.
Does NOT require FastAPI to be running.
"""

import argparse
import asyncio
import sys

from rich.console import Console
from rich.table import Table

from app.collectors.campaign_collector import (
    CampaignCollector,
    CollectorError,
    FacebookSessionExpiredError,
)
from app.core.logger import logger
from app.models.campaign import CampaignModel

console = Console()


# ------------------------------------------------------------------
# Display helpers
# ------------------------------------------------------------------


def _fmt_currency(value: float) -> str:
    """Format a float as currency with 2 decimal places."""
    return f"${value:,.2f}"


def _fmt_percent(value: float) -> str:
    return f"{value:.2f}%"


def _fmt_roas(value: float) -> str:
    return f"{value:.2f}x"


def _fmt_int(value: int) -> str:
    return f"{value:,}"


def _budget_str(campaign: CampaignModel) -> str:
    b = campaign.budget
    if b.budget_type == "DAILY" and b.daily_budget is not None:
        return f"{_fmt_currency(b.daily_budget)}/day"
    if b.budget_type == "LIFETIME" and b.lifetime_budget is not None:
        return f"{_fmt_currency(b.lifetime_budget)} lifetime"
    return "—"


def print_campaigns(campaigns: list[CampaignModel]) -> None:
    """Print a Rich formatted table of campaign metrics."""
    console.print()
    console.rule("[bold green]Meta Ads Reporter — Campaign Results[/bold green]")
    console.print(f"  [dim]Total campaigns captured: {len(campaigns)}[/dim]")
    console.print()

    for i, c in enumerate(campaigns, start=1):
        table = Table(
            title=f"[bold]{i}. {c.campaign_name}[/bold]",
            show_header=True,
            header_style="bold cyan",
            min_width=60,
        )
        table.add_column("Metric", style="dim", width=24)
        table.add_column("Value", justify="right")

        # Identity
        table.add_section()
        table.add_row("Campaign ID", c.campaign_id)
        table.add_row("Objective", c.objective or "—")

        # Delivery
        table.add_section()
        table.add_row("Status", c.delivery.status)
        table.add_row("Effective Status", c.delivery.effective_status)
        table.add_row(
            "Delivery",
            c.delivery.delivery_status or "—",
        )
        table.add_row(
            "Learning Phase",
            c.delivery.learning_status or "—",
        )
        table.add_row("Bid Strategy", c.delivery.bid_strategy or "—")

        # Budget
        table.add_section()
        table.add_row("Budget", _budget_str(c))
        table.add_row(
            "Start Date",
            (c.delivery.start_date or "—")[:10] if c.delivery.start_date else "—",
        )
        table.add_row(
            "End Date",
            (c.delivery.end_date or "—")[:10] if c.delivery.end_date else "ongoing",
        )

        # Performance
        table.add_section()
        p = c.performance
        table.add_row("Spend", _fmt_currency(p.spend))
        table.add_row("Impressions", _fmt_int(p.impressions))
        table.add_row("Reach", _fmt_int(p.reach))
        table.add_row("Frequency", f"{p.frequency:.2f}")
        table.add_row("Clicks (All)", _fmt_int(p.clicks))
        table.add_row("Link Clicks", _fmt_int(p.link_clicks))
        table.add_row("CTR", _fmt_percent(p.ctr))
        table.add_row("CPC", _fmt_currency(p.cpc))
        table.add_row("CPM", _fmt_currency(p.cpm))

        # Conversions
        table.add_section()
        cv = c.conversion
        table.add_row("Purchases", _fmt_int(cv.purchases))
        table.add_row("Cost / Purchase", _fmt_currency(cv.cost_per_purchase))
        table.add_row("ROAS", _fmt_roas(cv.roas))
        table.add_row("Conversion Value", _fmt_currency(cv.conversion_value))

        console.print(table)
        console.print()

    console.rule("[dim]End of Report[/dim]")


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------


async def run(profile_id: str, ad_account_id: str, timeout: float) -> None:
    collector = CampaignCollector(
        profile_id=profile_id,
        ad_account_id=ad_account_id,
        date_preset="last_30d",
        stop_browser_on_finish=False,
    )

    try:
        campaigns = await collector.collect()
        print_campaigns(campaigns)

    except FacebookSessionExpiredError as exc:
        logger.error(f"Facebook session expired: {exc}")
        console.print(
            "\n[bold red]ERROR:[/bold red] Facebook session has expired. "
            "Please log back in using AdsPower and retry."
        )
        sys.exit(1)

    except CollectorError as exc:
        logger.error(f"Collector failed: {exc}")
        console.print(f"\n[bold red]ERROR:[/bold red] {exc}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Meta Ads Reporter — Phase 2 Collector Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_collector.py --profile abc123 --account 123456789
  python test_collector.py --profile myprofile --account 987654321 --timeout 90
        """,
    )
    parser.add_argument(
        "--profile",
        required=True,
        metavar="PROFILE_ID",
        help="AdsPower profile/user ID (shown in AdsPower profile list).",
    )
    parser.add_argument(
        "--account",
        required=True,
        metavar="AD_ACCOUNT_ID",
        help="Facebook Ad Account ID (numeric, without 'act_' prefix).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        metavar="SECONDS",
        help="Max seconds to wait for GraphQL responses (default: 60).",
    )
    args = parser.parse_args()

    console.print(
        "\n[bold green]Meta Ads Reporter[/bold green] — Phase 2 Collector Test"
    )
    console.print(f"  Profile ID  : [cyan]{args.profile}[/cyan]")
    console.print(f"  Account ID  : [cyan]{args.account}[/cyan]")
    console.print(f"  Timeout     : [cyan]{args.timeout}s[/cyan]")
    console.print()

    asyncio.run(run(args.profile, args.account, args.timeout))


if __name__ == "__main__":
    main()
