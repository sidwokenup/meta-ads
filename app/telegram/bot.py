"""
Bot Entry Point

Reads BOT_TOKEN from .env, builds the Application, registers all handlers,
and starts long polling.

Usage:
    python app/telegram/bot.py

Environment variables required:
    BOT_TOKEN         — Telegram bot token from @BotFather
    API_BASE_URL      — FastAPI server URL (default: http://127.0.0.1:8000)
    DEFAULT_TIMEOUT   — Request timeout seconds (default: 120)

The bot uses long polling (no webhook needed for development).
"""

import os
import sys

# Ensure project root (meta-ads-reporter/) is on sys.path regardless of cwd
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()

from telegram.ext import Application

from app.core.logger import logger
from app.telegram import handlers


def main() -> None:
    token = os.getenv("BOT_TOKEN", "")
    if not token:
        logger.error(
            "BOT_TOKEN is not set. Add it to your .env file:\n"
            "  BOT_TOKEN=your_token_from_botfather"
        )
        sys.exit(1)

    api_url = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "not set")
    profile_id = os.getenv("ADSPOWER_PROFILE_ID", "not set")
    account_id = os.getenv("FACEBOOK_ACCOUNT_ID", "not set")

    logger.info("=" * 60)
    logger.info("  Meta Ads Reporter — Telegram Bot")
    logger.info(f"  FastAPI server  : {api_url}")
    logger.info(f"  Chat ID         : {chat_id}")
    logger.info(f"  AdsPower Profile: {profile_id}")
    logger.info(f"  Ad Account      : {account_id}")
    logger.info(f"  Mode            : Long Polling")
    logger.info("=" * 60)

    app = Application.builder().token(token).build()
    handlers.register(app)

    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
