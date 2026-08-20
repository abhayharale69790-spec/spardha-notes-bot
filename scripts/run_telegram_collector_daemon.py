"""Background Daemon for Continuous Telegram MTProto Channel Monitoring & Sync."""

import asyncio
from datetime import datetime, timezone
import logging
import os
import signal
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import get_settings
from database.session import get_session, init_db
from collectors.telegram_channel_registry import telegram_channel_registry
from collectors.telegram_user_collector import telegram_user_collector

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
settings = get_settings()


async def run_collector_loop():
    """Main continuous harvesting loop for approved Telegram channels."""
    await init_db()

    logger.info("=" * 80)
    logger.info(f"🚀 Starting Continuous Telegram MTProto Collector Daemon")
    logger.info(f"   Brand: {settings.brand_name}")
    logger.info(f"   Scan Interval: {settings.scrape_interval_minutes} minutes")
    logger.info("=" * 80)

    # Initialize Telethon user client if configured
    is_client_ready = await telegram_user_collector.initialize_client()

    while True:
        try:
            async with get_session() as session:
                sources = await telegram_channel_registry.get_all_approved_sources(session)
                if not sources:
                    sources = await telegram_channel_registry.initialize_defaults(session)

            logger.info(f"📡 Polling {len(sources)} approved Telegram channels for new study materials...")

            total_harvested = 0
            for s in sources:
                if not s.is_active:
                    continue
                try:
                    if is_client_ready:
                        added = await telegram_user_collector.scan_channel_messages(s, limit=30)
                        total_harvested += added
                except Exception as ex:
                    logger.error(f"Error scanning channel {s.title}: {ex}")

            logger.info(f"✅ Cycle complete. Ingested {total_harvested} verified PDFs.")
            logger.info(f"💤 Sleeping for {settings.scrape_interval_minutes} minutes...")
            await asyncio.sleep(settings.scrape_interval_minutes * 60)

        except asyncio.CancelledError:
            logger.info("🛑 Telegram collector loop received cancellation signal.")
            break
        except Exception as e:
            logger.error(f"Unexpected error in collector daemon loop: {e}", exc_info=True)
            await asyncio.sleep(60)


if __name__ == "__main__":
    try:
        asyncio.run(run_collector_loop())
    except KeyboardInterrupt:
        logger.info("Collector daemon stopped by user.")
