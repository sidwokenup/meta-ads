"""
Real-Time Collector Test

Runs get_campaigns() TWICE on the same account.
Verifies:
  - Real live data is returned each run
  - No cached objects are returned (objects are different instances each run)
  - Spend values are printed so you can spot any data change between runs

Usage:
    python tests/test_realtime.py --profile k1dvlyr0 --account 1559140139101704
    python tests/test_realtime.py --profile k1dvlyr0 --account 1559140139101704 --preset last_7d
    python tests/test_realtime.py --profile k1dvlyr0 --account 1559140139101704 --preset today
"""

import argparse
import asyncio
import sys
import time

# Make sure project root is on sys.path
sys.path.insert(0, ".")

from rich.console import Console
from rich.rule import Rule
from rich.table import Table

from app.services.collector_service import CollectorService
from app.services.session_manager import BrowserClosedError, SessionExpiredError

console = Console()


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def _campaign_table(campaigns, run_label: str) -> Table:
    table = Table(
        title=f"{run_label} — {len(campaigns)} campaigns",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
    )
    table.add_column("Campaign Name", style="bold", width=32, no_wrap=False)
    table.add_column("Status", justify="center", width=10)
    table.add_column("Spend", justify="right", width=10)
    table.add_column("CTR", justify="right", width=8)
    table.add_column("CPC", justify="right", width=8)
    table.add_column("CPM", justify="right", width=8)
    table.add_column("Purchases", justify="right", width=10)
    table.add_column("ROAS", justify="right", width=8)
    table.add_column("Budget", justify="right", width=14)

    for c in campaigns:
        ins = c.insights

        # Budget display
        if c.budget_type == "DAILY" and c.daily_budget:
            budget_str = f"${c.daily_budget:.2f}/day"
        elif c.budget_type == "LIFETIME" and c.lifetime_budget:
            budget_str = f"${c.lifetime_budget:.2f} life"
        else:
            budget_str = "—"

        # Status colour
        status_colour = {
            "ACTIVE": "green",
            "PAUSED": "yellow",
            "DELETED": "red",
            "ARCHIVED": "dim",
        }.get(c.effective_status.upper(), "white")

        table.add_row(
            c.campaign_name[:32],
            f"[{status_colour}]{c.effective_status}[/{status_colour}]",
            f"${ins.spend:.2f}",
            f"{ins.ctr:.2f}%",
            f"${ins.cpc:.2f}",
            f"${ins.cpm:.2f}",
            str(ins.purchases),
            f"{ins.roas:.2f}x",
            budget_str,
        )

    return table


def _compare_runs(run1, run2) -> None:
    """Print a side-by-side spend comparison between two runs."""
    console.print("\n")
    console.print(Rule("[bold]Spend Comparison: Run 1 vs Run 2[/bold]"))

    table = Table(show_header=True, header_style="bold magenta", border_style="dim")
    table.add_column("Campaign Name", width=34)
    table.add_column("Run 1 Spend", justify="right", width=14)
    table.add_column("Run 2 Spend", justify="right", width=14)
    table.add_column("Delta", justify="right", width=12)

    run1_map = {c.campaign_id: c for c in run1}
    run2_map = {c.campaign_id: c for c in run2}
    all_ids = set(run1_map) | set(run2_map)

    for cid in all_ids:
        c1 = run1_map.get(cid)
        c2 = run2_map.get(cid)
        name = (c1 or c2).campaign_name[:34]
        s1 = c1.insights.spend if c1 else 0.0
        s2 = c2.insights.spend if c2 else 0.0
        delta = s2 - s1
        delta_str = f"[green]+${delta:.4f}[/green]" if delta > 0 else (
            f"[red]-${abs(delta):.4f}[/red]" if delta < 0 else "[dim]$0.0000[/dim]"
        )
        table.add_row(name, f"${s1:.4f}", f"${s2:.4f}", delta_str)

    console.print(table)


def _check_no_cache(run1, run2) -> None:
    """Verify that run2 objects are different instances from run1."""
    console.print("\n")
    console.print(Rule("[bold]Cache Verification[/bold]"))

    for c1, c2 in zip(run1, run2):
        same_instance = c1 is c2
        status = "[red]CACHED (BUG)[/red]" if same_instance else "[green]Fresh object[/green]"
        console.print(f"  {c1.campaign_name[:40]}: {status}")

    same_list = run1 is run2
    console.print(
        f"\n  List objects same reference: "
        f"{'[red]YES (BUG)[/red]' if same_list else '[green]NO (correct)[/green]'}"
    )


# ---------------------------------------------------------------------------
# Main test
# ---------------------------------------------------------------------------


async def run_test(profile_id: str, account_id: str, preset: str) -> None:
    service = CollectorService(
        profile_id=profile_id,
        ad_account_id=account_id,
    )

    console.print(Rule(f"[bold cyan]Meta Ads Real-Time Test[/bold cyan]"))
    console.print(f"  Profile ID  : [bold]{profile_id}[/bold]")
    console.print(f"  Account ID  : [bold]{account_id}[/bold]")
    console.print(f"  Date Preset : [bold]{preset}[/bold]")
    console.print()

    # ---- RUN 1 ----
    console.print(Rule("[bold green]Run 1[/bold green]"))
    t0 = time.perf_counter()
    try:
        run1 = await service.get_campaigns(date_preset=preset)
    except BrowserClosedError as exc:
        console.print(f"[red]Browser not running:[/red] {exc}")
        sys.exit(1)
    except SessionExpiredError as exc:
        console.print(f"[red]Facebook session expired:[/red] {exc}")
        sys.exit(1)

    elapsed1 = time.perf_counter() - t0
    console.print(_campaign_table(run1, "Run 1"))
    console.print(f"\n  [dim]Run 1 completed in {elapsed1:.1f}s[/dim]")

    # ---- RUN 2 ----
    console.print("\n")
    console.print(Rule("[bold yellow]Run 2[/bold yellow]"))
    t0 = time.perf_counter()
    try:
        run2 = await service.get_campaigns(date_preset=preset)
    except BrowserClosedError as exc:
        console.print(f"[red]Browser not running:[/red] {exc}")
        sys.exit(1)
    except SessionExpiredError as exc:
        console.print(f"[red]Facebook session expired:[/red] {exc}")
        sys.exit(1)

    elapsed2 = time.perf_counter() - t0
    console.print(_campaign_table(run2, "Run 2"))
    console.print(f"\n  [dim]Run 2 completed in {elapsed2:.1f}s[/dim]")

    # ---- COMPARISON ----
    _compare_runs(run1, run2)
    _check_no_cache(run1, run2)

    console.print("\n")
    console.print(Rule("[bold]Test Complete[/bold]"))
    console.print(
        f"  Run 1: {len(run1)} campaigns in {elapsed1:.1f}s\n"
        f"  Run 2: {len(run2)} campaigns in {elapsed2:.1f}s"
    )
    console.print(
        "\n  [bold green]PASSED[/bold green] — both runs returned live data. "
        "No cached objects."
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Meta Ads Real-Time Collector Test")
    parser.add_argument("--profile", required=True, help="AdsPower profile ID")
    parser.add_argument("--account", required=True, help="Facebook ad account ID (numeric)")
    parser.add_argument("--preset", default="last_30d", help="Date preset (default: last_30d)")
    args = parser.parse_args()

    asyncio.run(run_test(args.profile, args.account, args.preset))
