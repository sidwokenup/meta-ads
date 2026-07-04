"""
Handlers

Registers all command handlers onto a telegram Application.
Keeps bot.py clean — only registration logic lives here.
"""

from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from app.telegram.commands import (
    cmd_account,
    cmd_accounts,
    cmd_campaign,
    cmd_campaigns,
    cmd_help,
    cmd_metrics,
    cmd_profile,
    cmd_profiles,
    cmd_refresh,
    cmd_report,
    cmd_setaccount,
    cmd_setprofile,
    cmd_start,
    cmd_status,
    cmd_useaccount,
    cmd_useprofile,
    cmd_pause,
    cmd_activate,
    handle_callback,
)


def register(app: Application) -> None:
    """Register all command handlers on the Application."""
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("setprofile", cmd_setprofile))
    app.add_handler(CommandHandler("profiles", cmd_profiles))
    app.add_handler(CommandHandler("useprofile", cmd_useprofile))
    app.add_handler(CommandHandler("setaccount", cmd_setaccount))
    app.add_handler(CommandHandler("accounts", cmd_accounts))
    app.add_handler(CommandHandler("useaccount", cmd_useaccount))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("account", cmd_account))
    app.add_handler(CommandHandler("campaigns", cmd_campaigns))
    app.add_handler(CommandHandler("campaign", cmd_campaign))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("metrics", cmd_metrics))
    app.add_handler(CommandHandler("refresh", cmd_refresh))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("activate", cmd_activate))
    app.add_handler(CallbackQueryHandler(handle_callback))
