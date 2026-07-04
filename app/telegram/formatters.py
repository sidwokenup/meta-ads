"""
Formatters

Converts FastAPI JSON responses into Telegram MarkdownV2-formatted messages.
All special characters are escaped. Emojis used throughout.

MarkdownV2 special chars that MUST be escaped:
  _ * [ ] ( ) ~ ` > # + - = | { } . !
"""

from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Escape helper
# ---------------------------------------------------------------------------

_SPECIAL = r"\_*[]()~`>#+-=|{}.!"


def esc(text: str) -> str:
    """Escape all MarkdownV2 special characters in a string."""
    for ch in _SPECIAL:
        text = text.replace(ch, f"\\{ch}")
    return text


def money(value: float) -> str:
    return esc(f"${value:,.2f}")


def pct(value: float) -> str:
    return esc(f"{value:.2f}%")


def roas(value: float) -> str:
    return esc(f"{value:.2f}x")


def num(value: int) -> str:
    return esc(f"{value:,}")


def status_emoji(s: str) -> str:
    return {
        "ACTIVE": "🟢",
        "PAUSED": "🟡",
        "DELETED": "🔴",
        "ARCHIVED": "⚫",
    }.get(s.upper(), "⚪")


def health_emoji(ok: bool) -> str:
    return "✅" if ok else "❌"


def budget_str(campaign: dict) -> str:
    bt = campaign.get("budget_type", "UNKNOWN")
    daily = campaign.get("daily_budget")
    lifetime = campaign.get("lifetime_budget")
    if bt == "DAILY" and daily:
        return esc(f"${daily:,.2f}/day")
    if bt == "LIFETIME" and lifetime:
        return esc(f"${lifetime:,.2f} lifetime")
    return esc("—")


def now_str() -> str:
    return esc(datetime.now().strftime("%H:%M:%S"))


# ---------------------------------------------------------------------------
# Campaign list formatter
# ---------------------------------------------------------------------------


def fmt_campaigns_list(data: dict) -> str:
    campaigns = data.get("campaigns", [])
    total = data.get("total", 0)
    preset = esc(data.get("date_preset", "last_30d"))
    ms = esc(f"{data.get('response_time_ms', 0):.0f}ms")

    if not campaigns:
        return "📭 *No campaigns found* for this date range\\."

    lines = [
        f"📊 *Campaign Overview* \\| {esc(str(total))} campaigns \\| {preset}",
        "",
    ]

    for i, c in enumerate(campaigns, 1):
        ins = c.get("insights", {})
        em = status_emoji(c.get("effective_status", ""))
        name = esc(c.get("campaign_name", "Unknown"))
        spend = money(ins.get("spend", 0))
        ctr = pct(ins.get("ctr", 0))
        r = roas(ins.get("roas", 0))

        lines.append(
            f"{esc(str(i))}\\. {em} *{name}*\n"
            f"   💰 Spend: {spend}  📈 CTR: {ctr}  🎯 ROAS: {r}"
        )

    lines += ["", f"⏱ Fetched in {ms} — live data"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Single campaign formatter
# ---------------------------------------------------------------------------


def fmt_campaign(data: dict) -> str:
    ins = data.get("insights", {})
    em = status_emoji(data.get("effective_status", ""))
    name = esc(data.get("campaign_name", "Unknown"))
    cid = esc(data.get("campaign_id", "—"))
    obj = esc(data.get("objective") or "—")
    status = esc(data.get("effective_status", "—"))
    bid = esc(data.get("bid_strategy") or "—")
    start = esc(str(data.get("start_time") or "—")[:10])
    end = esc(str(data.get("end_time") or "ongoing")[:10])
    bud = budget_str(data)

    spend = money(ins.get("spend", 0))
    impr = num(ins.get("impressions", 0))
    reach = num(ins.get("reach", 0))
    freq = esc(f"{ins.get('frequency', 0):.2f}")
    clicks = num(ins.get("clicks", 0))
    lc = num(ins.get("link_clicks", 0))
    uc = num(ins.get("unique_clicks", 0))
    ctr = pct(ins.get("ctr", 0))
    cpc = money(ins.get("cpc", 0))
    cpm = money(ins.get("cpm", 0))
    purch = num(ins.get("purchases", 0))
    pval = money(ins.get("purchase_value", 0))
    cpp = money(ins.get("cost_per_purchase", 0))
    r = roas(ins.get("roas", 0))
    lpv = num(ins.get("landing_page_views", 0))
    atc = num(ins.get("add_to_carts", 0))
    chk = num(ins.get("initiate_checkouts", 0))
    d_start = esc(str(ins.get("date_start") or "—"))
    d_stop = esc(str(ins.get("date_stop") or "—"))

    return (
        f"📊 *Campaign Report*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏷 *{name}*\n"
        f"🆔 ID: `{cid}`\n"
        f"📌 Objective: `{obj}`\n"
        f"{em} Status: `{status}`\n"
        f"🎯 Bid Strategy: `{bid}`\n"
        f"💵 Budget: {bud}\n"
        f"📅 Period: {start} → {end}\n"
        f"📆 Data: {d_start} → {d_stop}\n"
        f"\n"
        f"*── Performance ──*\n"
        f"💰 Spend: *{spend}*\n"
        f"👁 Impressions: {impr}\n"
        f"🧑 Reach: {reach}\n"
        f"🔄 Frequency: {freq}\n"
        f"🖱 Clicks: {clicks}  \\(Link: {lc}  Unique: {uc}\\)\n"
        f"📈 CTR: *{ctr}*\n"
        f"💸 CPC: {cpc}\n"
        f"📺 CPM: {cpm}\n"
        f"\n"
        f"*── Conversions ──*\n"
        f"🛒 Purchases: *{purch}*\n"
        f"💳 Purchase Value: {pval}\n"
        f"💲 Cost/Purchase: {cpp}\n"
        f"🎯 ROAS: *{r}*\n"
        f"📄 LP Views: {lpv}\n"
        f"🛍 Add to Cart: {atc}\n"
        f"💳 Checkout: {chk}\n"
        f"\n"
        f"⏱ Generated: {now_str()} — live data"
    )


# ---------------------------------------------------------------------------
# Report formatter
# ---------------------------------------------------------------------------


def fmt_report(data: dict) -> str:
    preset = esc(data.get("date_preset", "last_30d"))
    gen = esc(str(data.get("generated_at", ""))[:19].replace("T", " "))
    total_c = esc(str(data.get("total_campaigns", 0)))
    active_c = esc(str(data.get("active_campaigns", 0)))
    paused_c = esc(str(data.get("paused_campaigns", 0)))
    total_spend = money(data.get("total_spend", 0))
    total_impr = num(data.get("total_impressions", 0))
    total_reach = num(data.get("total_reach", 0))
    total_clicks = num(data.get("total_clicks", 0))
    total_purch = esc(str(data.get("total_purchases", 0)))
    total_pval = money(data.get("total_purchase_value", 0))
    avg_ctr = pct(data.get("avg_ctr", 0))
    avg_cpc = money(data.get("avg_cpc", 0))
    avg_cpm = money(data.get("avg_cpm", 0))
    avg_roas = roas(data.get("avg_roas", 0))
    ms = esc(f"{data.get('response_time_ms', 0):.0f}ms")

    top = data.get("top_campaign")
    worst = data.get("worst_campaign")
    top_roas = data.get("top_roas_campaign")

    def _camp_line(label: str, c: Optional[dict]) -> str:
        if not c:
            return f"{label}: —"
        n = esc(c.get("campaign_name", "Unknown")[:35])
        sp = money(c.get("spend", 0))
        return f"{label}: *{n}*\n      💰 {sp}"

    top_line = _camp_line("🥇 Top Spender", top)
    worst_line = _camp_line("🔻 Lowest Spend", worst)
    roas_line = _camp_line("🏆 Best ROAS", top_roas)

    return (
        f"📋 *Account Report* \\| {preset}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 Generated: `{gen}`\n"
        f"\n"
        f"*── Campaigns ──*\n"
        f"📊 Total: {total_c}  🟢 Active: {active_c}  🟡 Paused: {paused_c}\n"
        f"\n"
        f"*── Totals ──*\n"
        f"💰 Total Spend: *{total_spend}*\n"
        f"👁 Impressions: {total_impr}\n"
        f"🧑 Reach: {total_reach}\n"
        f"🖱 Clicks: {total_clicks}\n"
        f"🛒 Purchases: {total_purch}\n"
        f"💳 Purchase Value: {total_pval}\n"
        f"\n"
        f"*── Averages ──*\n"
        f"📈 Avg CTR: {avg_ctr}\n"
        f"💸 Avg CPC: {avg_cpc}\n"
        f"📺 Avg CPM: {avg_cpm}\n"
        f"🎯 Avg ROAS: {avg_roas}\n"
        f"\n"
        f"*── Notable ──*\n"
        f"{top_line}\n"
        f"{worst_line}\n"
        f"{roas_line}\n"
        f"\n"
        f"⏱ Fetched in {ms} — live data"
    )


# ---------------------------------------------------------------------------
# Account formatter
# ---------------------------------------------------------------------------


def fmt_account(data: dict) -> str:
    name = esc(data.get("account_name", "Unknown"))
    aid = esc(data.get("account_id", "—"))
    currency = esc(data.get("currency", "—"))
    tz = esc(data.get("timezone", "—"))
    biz = esc(data.get("business_name") or "—")
    spent = money(data.get("amount_spent", 0))
    balance = money(data.get("balance", 0))
    total_c = esc(str(data.get("total_campaigns", 0)))
    active_c = esc(str(data.get("active_campaigns", 0)))
    paused_c = esc(str(data.get("paused_campaigns", 0)))
    ms = esc(f"{data.get('response_time_ms', 0):.0f}ms")

    status_val = data.get("account_status", 0)
    status_map = {1: "🟢 Active", 2: "🔴 Disabled", 3: "⚠️ Unsettled", 7: "⚫ Closed"}
    acc_status = esc(status_map.get(status_val, f"Unknown ({status_val})"))

    return (
        f"🏦 *Ad Account*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏷 Name: *{name}*\n"
        f"🆔 ID: `{aid}`\n"
        f"🏢 Business: {biz}\n"
        f"💱 Currency: {currency}\n"
        f"🌍 Timezone: {tz}\n"
        f"📊 Status: {acc_status}\n"
        f"\n"
        f"*── Spend ──*\n"
        f"💰 Lifetime Spend: *{spent}*\n"
        f"💳 Balance: {balance}\n"
        f"\n"
        f"*── Campaigns ──*\n"
        f"📋 Total: {total_c}  🟢 Active: {active_c}  🟡 Paused: {paused_c}\n"
        f"\n"
        f"⏱ Fetched in {ms} — live data"
    )


# ---------------------------------------------------------------------------
# Health / Status formatter
# ---------------------------------------------------------------------------


def fmt_health(data: dict) -> str:
    overall = data.get("status", "unknown")
    browser = data.get("browser", "unknown")
    fb_session = data.get("facebook_session", "unknown")
    collector = data.get("collector", "unknown")
    ms = esc(f"{data.get('response_time_ms', 0):.0f}ms")
    detail = esc(data.get("detail", ""))

    ok_overall = overall == "healthy"
    ok_browser = browser == "connected"
    ok_session = fb_session == "active"
    ok_collector = collector == "ready"

    lines = [
        f"{health_emoji(ok_overall)} *System Status*",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"{health_emoji(True)} FastAPI: 🟢 Online",
        f"{health_emoji(ok_browser)} AdsPower Browser: `{esc(browser)}`",
        f"{health_emoji(ok_session)} Facebook Session: `{esc(fb_session)}`",
        f"{health_emoji(ok_collector)} Collector: `{esc(collector)}`",
        f"",
        f"⏱ Check took {ms}",
    ]
    if detail:
        lines += ["", f"⚠️ {detail}"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Error formatter
# ---------------------------------------------------------------------------


def fmt_error(message: str) -> str:
    return f"❌ *Error*\n\n{esc(message)}"


def fmt_not_configured(missing_msg: str) -> str:
    return f"⚙️ *Session not configured*\n\n{missing_msg}"
