"""
Command Handlers

Every Telegram bot command lives here.
Each handler:
  1. Reads the user's session (profile_id, account_id)
  2. Calls APIClient to hit the FastAPI server
  3. Formats the response with formatters.py
  4. Sends the message back

No Facebook, AdsPower, CDP, or collector logic here.
Only: session → API → format → reply.
"""

import os
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from app.core.logger import logger
from app.telegram.client import APIClient, APIError
from app.telegram.session import store
from app.telegram import formatters as fmt

_API_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")


def _client() -> APIClient:
    return APIClient(base_url=_API_URL)


def _client_for_session(session) -> APIClient:
    return APIClient(
        base_url=_API_URL,
        profile_id=session.profile_id,
        account_id=session.account_id,
    )


async def _reply(update: Update, text: str) -> None:
    """Send a MarkdownV2 message. Falls back to plain text on parse error."""
    try:
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except Exception:
        # Strip all markdown as fallback
        plain = text.replace("*", "").replace("`", "").replace("\\", "")
        await update.message.reply_text(plain)


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    uid = user.id
    session = store.get(uid)
    logger.info(f"[Bot] /start from user {uid}")

    text = (
        "👋 *Welcome to Meta Ads Reporter\\!*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "I give you live Facebook campaign data straight from your AdsPower browser\\.\n\n"
        "*Quick setup:*\n"
        "1\\. `/setprofile k1dvlyr0` — add and activate a profile\n"
        "2\\. `/setaccount 1559140139101704` — add and activate an account\n\n"
        "*Then use:*\n"
        "📊 `/campaigns` — all campaigns\n"
        "🔍 `/campaign <name>` — single campaign\n"
        "📋 `/report` — full account report\n"
        "🏦 `/account` — account overview\n"
        "❤️ `/status` — system health check\n\n"
        "*Multi account:*\n"
        "📚 `/accounts` — list saved accounts\n"
        "🎯 `/useaccount 2489049668183097` — switch active account\n\n"
        "Type `/help` for the full command list\\."
    )

    if session.is_configured():
        text += (
            f"\n\n✅ *Already configured:*\n"
            f"Profile: `{fmt.esc(session.profile_id)}`\n"
            f"Account: `{fmt.esc(session.account_id)}`"
        )

    await _reply(update, text)


# ---------------------------------------------------------------------------
# /help
# ---------------------------------------------------------------------------


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"[Bot] /help from user {update.effective_user.id}")
    text = (
        "📖 *Command List*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "*Setup*\n"
        "`/setprofile <id>` — add and activate a profile\n"
        "`/profiles` — list saved profiles\n"
        "`/useprofile <id>` — switch active profile\n"
        "`/setaccount <id>` — add and activate an account\n"
        "`/accounts` — list saved accounts\n"
        "`/useaccount <id>` — switch active account\n"
        "`/profile` — show current session info\n\n"
        "*Data*\n"
        "`/campaigns` — all campaigns \\(last 30d\\)\n"
        "`/campaigns today` — today only\n"
        "`/campaigns last_7d` — last 7 days\n"
        "`/campaign <name>` — full campaign details\n"
        "`/report` — account\\-level report\n"
        "`/account` — account overview\n"
        "`/metrics` — live account summary\n"
        "`/refresh` — force fresh data fetch\n\n"
        "*System*\n"
        "`/status` — FastAPI \\+ browser \\+ session health\n"
        "`/help` — this message\n\n"
        "📡 Every command fetches *live* data\\. No cache\\."
    )
    await _reply(update, text)


# ---------------------------------------------------------------------------
# /profile
# ---------------------------------------------------------------------------


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    session = store.get(uid)
    logger.info(f"[Bot] /profile from user {uid}")
    text = f"⚙️ *Your Session*\n━━━━━━━━━━━━━━━━━━━━\n\n{session.summary()}"
    await _reply(update, text)


# ---------------------------------------------------------------------------
# /setprofile
# ---------------------------------------------------------------------------


async def cmd_setprofile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    logger.info(f"[Bot] /setprofile from user {uid}, args={context.args}")

    if not context.args:
        await _reply(
            update,
            "⚙️ Usage: `/setprofile <profile_id>`\n\nExample: `/setprofile k1dvlyr0`",
        )
        return

    profile_id = context.args[0].strip()
    store.set_profile(uid, profile_id)
    session = store.get(uid)

    text = (
        f"✅ *Profile saved and activated\\!*\n\n"
        f"Profile ID: `{fmt.esc(profile_id)}`\n"
    )
    if session.account_id:
        text += f"Account ID: `{fmt.esc(session.account_id)}`\n\nYou're ready\\! Try `/campaigns`"
    else:
        text += "\nNow set your account: `/setaccount <account_id>`"

    await _reply(update, text)


# ---------------------------------------------------------------------------
# /profiles
# ---------------------------------------------------------------------------


async def cmd_profiles(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    session = store.get(uid)
    logger.info(f"[Bot] /profiles from user {uid}")

    items = session.saved_profiles or ([] if not session.profile_id else [session.profile_id])
    if not items:
        await _reply(
            update,
            "📚 *No saved profiles yet*\n\nAdd one with `/setprofile <profile_id>`",
        )
        return

    lines = ["📚 *Saved Profiles*", "━━━━━━━━━━━━━━━━━━━━", ""]
    for profile_id in items:
        marker = "✅" if profile_id == session.profile_id else "•"
        lines.append(f"{marker} `{fmt.esc(profile_id)}`")
    lines.append("")
    lines.append("Use `/useprofile <profile_id>` to switch\\.")
    await _reply(update, "\n".join(lines))


# ---------------------------------------------------------------------------
# /useprofile
# ---------------------------------------------------------------------------


async def cmd_useprofile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    logger.info(f"[Bot] /useprofile from user {uid}, args={context.args}")

    if not context.args:
        await _reply(
            update,
            "⚙️ Usage: `/useprofile <profile_id>`\n\nExample: `/useprofile k1dvlyr0`",
        )
        return

    profile_id = context.args[0].strip()
    if not store.use_profile(uid, profile_id):
        await _reply(
            update,
            f"❌ *Profile not found*\n\n`{fmt.esc(profile_id)}`\n\nAdd it first with `/setprofile {fmt.esc(profile_id)}`",
        )
        return

    session = store.get(uid)
    text = (
        f"✅ *Active profile switched\\!*\n\n"
        f"Profile ID: `{fmt.esc(profile_id)}`\n"
        f"Account ID: `{fmt.esc(session.account_id or 'not set')}`"
    )
    await _reply(update, text)


# ---------------------------------------------------------------------------
# /setaccount
# ---------------------------------------------------------------------------


async def cmd_setaccount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    logger.info(f"[Bot] /setaccount from user {uid}, args={context.args}")

    if not context.args:
        await _reply(
            update,
            "⚙️ Usage: `/setaccount <account_id>`\n\nExample: `/setaccount 1559140139101704`",
        )
        return

    account_id = context.args[0].strip()
    store.set_account(uid, account_id)
    session = store.get(uid)

    text = (
        f"✅ *Account saved and activated\\!*\n\n"
        f"Account ID: `{fmt.esc(account_id)}`\n"
    )
    if session.profile_id:
        text += f"Profile ID: `{fmt.esc(session.profile_id)}`\n\nYou're ready\\! Try `/campaigns`"
    else:
        text += "\nNow set your profile: `/setprofile <profile_id>`"

    await _reply(update, text)


# ---------------------------------------------------------------------------
# /accounts
# ---------------------------------------------------------------------------


async def cmd_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    session = store.get(uid)
    logger.info(f"[Bot] /accounts from user {uid}")

    items = session.saved_accounts or ([] if not session.account_id else [session.account_id])
    if not items:
        await _reply(
            update,
            "📚 *No saved accounts yet*\n\nAdd one with `/setaccount <account_id>`",
        )
        return

    lines = ["📚 *Saved Accounts*", "━━━━━━━━━━━━━━━━━━━━", ""]
    for account_id in items:
        marker = "✅" if account_id == session.account_id else "•"
        lines.append(f"{marker} `{fmt.esc(account_id)}`")
    lines.append("")
    lines.append("Use `/useaccount <account_id>` to switch\\.")
    await _reply(update, "\n".join(lines))


# ---------------------------------------------------------------------------
# /useaccount
# ---------------------------------------------------------------------------


async def cmd_useaccount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    logger.info(f"[Bot] /useaccount from user {uid}, args={context.args}")

    if not context.args:
        await _reply(
            update,
            "⚙️ Usage: `/useaccount <account_id>`\n\nExample: `/useaccount 2489049668183097`",
        )
        return

    account_id = context.args[0].strip()
    if not store.use_account(uid, account_id):
        await _reply(
            update,
            f"❌ *Account not found*\n\n`{fmt.esc(account_id)}`\n\nAdd it first with `/setaccount {fmt.esc(account_id)}`",
        )
        return

    session = store.get(uid)
    text = (
        f"✅ *Active account switched\\!*\n\n"
        f"Account ID: `{fmt.esc(account_id)}`\n"
        f"Profile ID: `{fmt.esc(session.profile_id or 'not set')}`\n\n"
        "Try `/campaigns` now\\."
    )
    await _reply(update, text)


# ---------------------------------------------------------------------------
# /status
# ---------------------------------------------------------------------------


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    session = store.get(uid)
    logger.info(f"[Bot] /status from user {uid}")
    await update.message.reply_text("🔍 Checking system status\\.\\.\\.", parse_mode=ParseMode.MARKDOWN_V2)

    try:
        client = _client_for_session(session) if session.is_configured() else _client()
        data = await client.get_health()
        store.touch(uid, "/status")
        await _reply(update, fmt.fmt_health(data))
    except APIError as e:
        await _reply(update, fmt.fmt_error(str(e)))


# ---------------------------------------------------------------------------
# /account
# ---------------------------------------------------------------------------


async def cmd_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    session = store.get(uid)
    logger.info(f"[Bot] /account from user {uid}")

    if not session.is_configured():
        await _reply(update, fmt.fmt_not_configured(session.missing_config()))
        return

    await update.message.reply_text("🏦 Fetching account info\\.\\.\\.", parse_mode=ParseMode.MARKDOWN_V2)

    try:
        data = await _client_for_session(session).get_account()
        store.touch(uid, "/account")
        await _reply(update, fmt.fmt_account(data))
    except APIError as e:
        await _reply(update, fmt.fmt_error(str(e)))


# ---------------------------------------------------------------------------
# /campaigns
# ---------------------------------------------------------------------------


async def cmd_campaigns(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    session = store.get(uid)
    logger.info(f"[Bot] /campaigns from user {uid}, args={context.args}")

    if not session.is_configured():
        await _reply(update, fmt.fmt_not_configured(session.missing_config()))
        return

    # Optional date preset as first argument: /campaigns today
    preset = context.args[0] if context.args else session.date_preset
    valid_presets = ["today", "yesterday", "last_7d", "last_30d", "last_90d",
                     "this_month", "last_month", "this_year", "lifetime"]
    if preset not in valid_presets:
        preset = session.date_preset

    await update.message.reply_text(
        f"📊 Fetching campaigns \\(`{fmt.esc(preset)}`\\)\\.\\.\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    try:
        data = await _client_for_session(session).get_campaigns(date_preset=preset)
        store.touch(uid, "/campaigns")
        await _reply(update, fmt.fmt_campaigns_list(data))
    except APIError as e:
        await _reply(update, fmt.fmt_error(str(e)))


# ---------------------------------------------------------------------------
# Interactive Menu Logic for /pause and /activate
# ---------------------------------------------------------------------------

async def start_interactive_status_flow(update: Update, session, target_status: str) -> None:
    """Launch the interactive menu to select accounts and campaigns."""
    accounts = session.saved_accounts
    if not accounts and session.account_id:
        accounts = [session.account_id]
        
    if not accounts:
        await _reply(update, "❌ *No accounts saved*\\.\n\nUse `/setaccount <id>` first\\.")
        return

    # Initialize menu state
    session.menu_state = {
        "action": target_status,
        "step": "select_account" if len(accounts) > 1 else "select_campaigns",
        "account_id": accounts[0] if len(accounts) == 1 else None,
        "selected_campaigns": set(),
        "available_campaigns": {}
    }

    if len(accounts) > 1:
        # Ask user to pick an account first
        keyboard = []
        for acc in accounts:
            marker = "🟢 " if acc == session.account_id else ""
            keyboard.append([InlineKeyboardButton(f"{marker}Account {acc}", callback_data=f"acc_{acc}")])
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"Select an Ad Account to *{target_status}* campaigns in:", 
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2
        )
    else:
        # Only one account, go straight to fetching campaigns
        await fetch_and_show_campaigns_menu(update.message, session)


async def fetch_and_show_campaigns_menu(message, session) -> None:
    target_status = session.menu_state["action"]
    filter_status = "ACTIVE" if target_status == "PAUSED" else "PAUSED"
    account_id = session.menu_state["account_id"]
    action_verb = "Pause" if target_status == "PAUSED" else "Activate"
    
    await message.edit_text(f"📡 Fetching *{filter_status}* campaigns from `{fmt.esc(account_id)}`\\.\\.\\.", parse_mode=ParseMode.MARKDOWN_V2)
    
    try:
        client = APIClient(base_url=_API_URL, profile_id=session.profile_id, account_id=account_id)
        data = await client.get_campaigns(campaign_status=filter_status, date_preset="last_30d")
        campaigns = data.get("campaigns", [])
        
        if not campaigns:
            await message.edit_text(f"✅ No *{filter_status}* campaigns found in this account\\.", parse_mode=ParseMode.MARKDOWN_V2)
            return
            
        # Store available campaigns with short UUIDs for callback data limits
        available = {}
        for c in campaigns:
            short_id = str(uuid.uuid4())[:8]
            available[short_id] = {
                "id": c["campaign_id"],
                "name": c["campaign_name"]
            }
        session.menu_state["available_campaigns"] = available
        session.menu_state["selected_campaigns"] = set()
        
        await show_campaigns_menu(message, session)
        
    except Exception as e:
        await message.edit_text(f"❌ Error fetching campaigns: {e}")


async def show_campaigns_menu(message, session) -> None:
    available = session.menu_state["available_campaigns"]
    selected = session.menu_state["selected_campaigns"]
    target_status = session.menu_state["action"]
    action_verb = "Pause" if target_status == "PAUSED" else "Activate"
    
    keyboard = []
    for short_id, camp in available.items():
        is_selected = short_id in selected
        checkbox = "✅" if is_selected else "⬜️"
        name = camp["name"][:30] + ("..." if len(camp["name"]) > 30 else "")
        keyboard.append([InlineKeyboardButton(f"{checkbox} {name}", callback_data=f"tg_{short_id}")])
        
    keyboard.append([
        InlineKeyboardButton(f"🚀 {action_verb} Selected ({len(selected)})", callback_data="confirm"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"Select campaigns to *{action_verb}*:"
    
    try:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception:
        pass  # Message content hasn't changed


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process inline keyboard button clicks."""
    query = update.callback_query
    await query.answer()
    
    uid = update.effective_user.id
    session = store.get(uid)
    data = query.data
    
    if data == "cancel":
        session.menu_state.clear()
        await query.edit_message_text("❌ Action cancelled.")
        return
        
    if not session.menu_state:
        await query.edit_message_text("⚠️ Menu expired. Please send the command again.")
        return
        
    if data.startswith("acc_"):
        acc_id = data.split("_")[1]
        session.menu_state["account_id"] = acc_id
        session.menu_state["step"] = "select_campaigns"
        await fetch_and_show_campaigns_menu(query.message, session)
        return
        
    if data.startswith("tg_"):
        short_id = data.split("_")[1]
        if short_id in session.menu_state["selected_campaigns"]:
            session.menu_state["selected_campaigns"].remove(short_id)
        else:
            session.menu_state["selected_campaigns"].add(short_id)
        await show_campaigns_menu(query.message, session)
        return
        
    if data == "confirm":
        selected = session.menu_state["selected_campaigns"]
        available = session.menu_state["available_campaigns"]
        target_status = session.menu_state["action"]
        action_verb = "Paused" if target_status == "PAUSED" else "Activated"
        
        if not selected:
            await query.answer("Please select at least one campaign!", show_alert=True)
            return
            
        await query.edit_message_text("⏳ Processing your request... This may take a moment.")
        
        client = APIClient(
            base_url=_API_URL, 
            profile_id=session.profile_id, 
            account_id=session.menu_state["account_id"]
        )
        
        success_list = []
        error_list = []
        
        for short_id in selected:
            camp = available[short_id]
            try:
                await client.update_campaign_status(camp["id"], target_status)
                success_list.append(camp["name"])
            except Exception as e:
                error_list.append(f"{camp['name']}: {e}")
                
        # Format results without strict markdown to avoid escaping issues with campaign names
        res = f"✅ {action_verb} {len(success_list)} campaigns!\n\n"
        for name in success_list:
            res += f"• {name}\n"
        
        if error_list:
            res += f"\n❌ Failed ({len(error_list)}):\n"
            for err in error_list:
                res += f"• {err}\n"
                
        session.menu_state.clear()
        await query.edit_message_text(res)


# ---------------------------------------------------------------------------
# /pause and /activate
# ---------------------------------------------------------------------------


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    session = store.get(uid)
    logger.info(f"[Bot] /pause from user {uid}, args={context.args}")

    if not session.is_configured():
        await _reply(update, fmt.fmt_not_configured(session.missing_config()))
        return

    # If user provided args, do the quick pause by name
    if context.args:
        campaign_name = " ".join(context.args)
        await update.message.reply_text(f"⏸ Looking up campaign `{fmt.esc(campaign_name)}`\\.\\.\\.", parse_mode=ParseMode.MARKDOWN_V2)

        try:
            client = _client_for_session(session)
            campaign = await client.get_campaign(campaign_name, date_preset=session.date_preset)
            campaign_id = campaign.get("campaign_id")
            exact_name = campaign.get("campaign_name", campaign_name)
            
            await update.message.reply_text(f"⏸ Pausing `{fmt.esc(exact_name)}` \\.\\.\\.", parse_mode=ParseMode.MARKDOWN_V2)
            await client.update_campaign_status(campaign_id, "PAUSED")
            await _reply(update, f"✅ Campaign `{fmt.esc(exact_name)}` has been **PAUSED**\\.")
        except APIError as e:
            if e.status_code == 404:
                await _reply(update, f"🔍 *Campaign not found*\n\n`{fmt.esc(campaign_name)}`\n\nTry `/campaigns` to see all names\\.")
            else:
                await _reply(update, fmt.fmt_error(str(e)))
        return

    # No args provided -> Launch Interactive Menu
    await start_interactive_status_flow(update, session, "PAUSED")


async def cmd_activate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    session = store.get(uid)
    logger.info(f"[Bot] /activate from user {uid}, args={context.args}")

    if not session.is_configured():
        await _reply(update, fmt.fmt_not_configured(session.missing_config()))
        return

    # If user provided args, do the quick activate by name
    if context.args:
        campaign_name = " ".join(context.args)
        await update.message.reply_text(f"▶️ Looking up campaign `{fmt.esc(campaign_name)}`\\.\\.\\.", parse_mode=ParseMode.MARKDOWN_V2)

        try:
            client = _client_for_session(session)
            campaign = await client.get_campaign(campaign_name, date_preset=session.date_preset)
            campaign_id = campaign.get("campaign_id")
            exact_name = campaign.get("campaign_name", campaign_name)
            
            await update.message.reply_text(f"▶️ Activating `{fmt.esc(exact_name)}` \\.\\.\\.", parse_mode=ParseMode.MARKDOWN_V2)
            await client.update_campaign_status(campaign_id, "ACTIVE")
            await _reply(update, f"✅ Campaign `{fmt.esc(exact_name)}` has been **ACTIVATED**\\.")
        except APIError as e:
            if e.status_code == 404:
                await _reply(update, f"🔍 *Campaign not found*\n\n`{fmt.esc(campaign_name)}`\n\nTry `/campaigns` to see all names\\.")
            else:
                await _reply(update, fmt.fmt_error(str(e)))
        return

    # No args provided -> Launch Interactive Menu
    await start_interactive_status_flow(update, session, "ACTIVE")


# ---------------------------------------------------------------------------
# /campaign <name>
# ---------------------------------------------------------------------------


async def cmd_campaign(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    session = store.get(uid)
    logger.info(f"[Bot] /campaign from user {uid}, args={context.args}")

    if not session.is_configured():
        await _reply(update, fmt.fmt_not_configured(session.missing_config()))
        return

    if not context.args:
        await _reply(
            update,
            "🔍 Usage: `/campaign <campaign name>`\n\nExample:\n`/campaign Australia 2 july`",
        )
        return

    name = " ".join(context.args)
    await update.message.reply_text(
        f"🔍 Looking up *{fmt.esc(name)}*\\.\\.\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    try:
        data = await _client_for_session(session).get_campaign(name, date_preset=session.date_preset)
        store.touch(uid, "/campaign")
        await _reply(update, fmt.fmt_campaign(data))
    except APIError as e:
        if e.status_code == 404:
            await _reply(
                update,
                f"🔍 *Campaign not found*\n\n`{fmt.esc(name)}`\n\nTry `/campaigns` to see all campaign names\\.",
            )
        else:
            await _reply(update, fmt.fmt_error(str(e)))


# ---------------------------------------------------------------------------
# /report
# ---------------------------------------------------------------------------


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    session = store.get(uid)
    logger.info(f"[Bot] /report from user {uid}")

    if not session.is_configured():
        await _reply(update, fmt.fmt_not_configured(session.missing_config()))
        return

    preset = context.args[0] if context.args else session.date_preset
    await update.message.reply_text(
        f"📋 Generating report \\(`{fmt.esc(preset)}`\\)\\.\\.\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    try:
        data = await _client_for_session(session).get_report(date_preset=preset)
        store.touch(uid, "/report")
        await _reply(update, fmt.fmt_report(data))
    except APIError as e:
        await _reply(update, fmt.fmt_error(str(e)))


# ---------------------------------------------------------------------------
# /metrics  (alias for account-level summary)
# ---------------------------------------------------------------------------


async def cmd_metrics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    session = store.get(uid)
    logger.info(f"[Bot] /metrics from user {uid}")

    if not session.is_configured():
        await _reply(update, fmt.fmt_not_configured(session.missing_config()))
        return

    await update.message.reply_text("📡 Fetching live metrics\\.\\.\\.", parse_mode=ParseMode.MARKDOWN_V2)

    try:
        data = await _client_for_session(session).get_report(date_preset=session.date_preset)
        store.touch(uid, "/metrics")
        preset = fmt.esc(data.get("date_preset", "last_30d"))
        rt = data.get("response_time_ms", 0)
        ms = fmt.esc(f"{rt:.0f}ms")
        total_c = fmt.esc(str(data.get("total_campaigns", 0)))
        active_c = fmt.esc(str(data.get("active_campaigns", 0)))
        total_purch = fmt.esc(str(data.get("total_purchases", 0)))
        text = (
            f"📡 *Live Account Metrics* \\| {preset}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Campaigns: {total_c} \\(🟢 {active_c} active\\)\n"
            f"💰 Spend: *{fmt.money(data.get('total_spend', 0))}*\n"
            f"👁 Impressions: {fmt.num(data.get('total_impressions', 0))}\n"
            f"🖱 Clicks: {fmt.num(data.get('total_clicks', 0))}\n"
            f"🛒 Purchases: {total_purch}\n"
            f"📈 Avg CTR: {fmt.pct(data.get('avg_ctr', 0))}\n"
            f"💸 Avg CPC: {fmt.money(data.get('avg_cpc', 0))}\n"
            f"🎯 Avg ROAS: {fmt.roas(data.get('avg_roas', 0))}\n"
            f"\n"
            f"⏱ {ms} — live data"
        )
        await _reply(update, text)
    except APIError as e:
        await _reply(update, fmt.fmt_error(str(e)))


# ---------------------------------------------------------------------------
# /refresh
# ---------------------------------------------------------------------------


async def cmd_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    session = store.get(uid)
    logger.info(f"[Bot] /refresh from user {uid}")

    if not session.is_configured():
        await _reply(update, fmt.fmt_not_configured(session.missing_config()))
        return

    await update.message.reply_text(
        "🔄 *Forcing fresh data fetch\\.\\.\\.*\n\nConnecting to AdsPower browser and querying Facebook\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    try:
        data = await _client_for_session(session).get_campaigns(date_preset=session.date_preset)
        store.touch(uid, "/refresh")
        total = data.get("total", 0)
        ms = fmt.esc(f"{data.get('response_time_ms', 0):.0f}ms")
        await _reply(
            update,
            f"✅ *Refresh complete\\!*\n\n"
            f"Fetched {fmt.esc(str(total))} campaigns in {ms}\\.\n"
            f"Use `/campaigns` or `/report` to view the data\\.",
        )
    except APIError as e:
        await _reply(update, fmt.fmt_error(str(e)))
