import asyncio
import httpx
from typing import Dict, Any
from app.config import settings
from app.core.logger import logger
from app.services.collector_service import CollectorService
from app.models.campaign import CampaignModel

# In-memory state: account_id -> { campaign_id: CampaignModel }
_previous_state: Dict[str, Dict[str, Any]] = {}


async def send_telegram_message(text: str) -> None:
    if not settings.BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        logger.warning("[AlertWorker] Telegram token or chat ID not set. Skipping alert.")
        return

    url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(url, json=payload)
            res.raise_for_status()
            logger.info("[AlertWorker] Sent Telegram alert.")
    except Exception as exc:
        logger.error(f"[AlertWorker] Failed to send Telegram alert: {exc}")


async def poll_account(profile_id: str, account_id: str) -> None:
    logger.info(f"[AlertWorker] Polling account {account_id}...")
    try:
        collector = CollectorService(profile_id=profile_id, ad_account_id=account_id)
        # Using date_preset="today" is usually best for immediate real-time alerts
        # but we can use last_30d to ensure we see all active campaigns.
        campaigns = await collector.get_campaigns(date_preset="today")
        
        current_state = {c.campaign_id: c for c in campaigns}
        
        if account_id in _previous_state:
            prev_state = _previous_state[account_id]
            for cid, current in current_state.items():
                if cid in prev_state:
                    prev = prev_state[cid]
                    
                    alerts = []
                    
                    # 1. Status change
                    if current.effective_status != prev.effective_status:
                        alerts.append(f"🔄 *Status Changed*: `{current.effective_status}`")
                    
                    # 2. Spend increased
                    if current.insights.spend > prev.insights.spend:
                        diff = current.insights.spend - prev.insights.spend
                        alerts.append(f"💸 *Spend*: +${diff:.2f} (Total: ${current.insights.spend:.2f})")
                        
                    # 3. New purchase
                    if current.insights.purchases > prev.insights.purchases:
                        diff = current.insights.purchases - prev.insights.purchases
                        alerts.append(f"🎉 *New Purchase!*: +{diff} (Total: {current.insights.purchases})")
                        
                    if alerts:
                        msg = f"🔔 *Alert | Account {account_id}*\n*Campaign:* {current.campaign_name}\n" + "\n".join(alerts)
                        await send_telegram_message(msg)

        _previous_state[account_id] = current_state
        
    except Exception as exc:
        logger.error(f"[AlertWorker] Error polling account {account_id}: {exc}")


async def alert_worker_loop() -> None:
    """Background task loop that periodically polls accounts."""
    if not settings.BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        logger.warning("[AlertWorker] Bot token or Chat ID not configured. Worker will not send messages. Worker disabled.")
        return # Disable the worker entirely if no chat ID is configured to prevent unwanted polling

    logger.info(f"[AlertWorker] Started. Polling every {settings.ALERT_POLL_INTERVAL_SECONDS} seconds.")
    
    while True:
        logger.info("[AlertWorker] Running poll cycle...")
        for account_id in settings.monitor_accounts:
            await poll_account(settings.ADSPOWER_PROFILE_ID, account_id)
            # Sleep a bit between accounts to avoid slamming the browser
            await asyncio.sleep(5)
            
        logger.info(f"[AlertWorker] Cycle complete. Sleeping for {settings.ALERT_POLL_INTERVAL_SECONDS} seconds.")
        await asyncio.sleep(settings.ALERT_POLL_INTERVAL_SECONDS)
