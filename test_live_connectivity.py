"""Quick Live Connectivity and Portal Probe Script."""

import asyncio
import logging
import sys
from config.settings import get_settings
from database.session import init_db
from scraper.client import ResilientHttpClient
from scraper.portal_watcher import MPSCWatcher, MahaGRWatcher, PoliceBhartiWatcher, SaralSevaWatcher

# Fix Windows console encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("probe")


async def main():
    settings = get_settings()
    logger.info(f"Loaded configuration for Bot ID: {settings.bot_token.split(':')[0]}")
    logger.info(f"Main Channel: {settings.main_channel_id}")
    logger.info(f"Staging Channel: {settings.staging_channel_id}")
    logger.info(f"Backup Channel: {settings.backup_channel_id}")
    logger.info(f"Admin User IDs: {settings.admin_user_ids}")

    # 1. Initialize DB
    await init_db()
    logger.info("Database initialized successfully.")

    # 2. Check portals
    client = ResilientHttpClient(min_domain_interval_sec=1.0)
    watchers = [
        MPSCWatcher(client),
        MahaGRWatcher(client),
        PoliceBhartiWatcher(client),
        SaralSevaWatcher(client),
    ]

    print("\n--- LIVE PORTAL REACHABILITY ---")
    for w in watchers:
        try:
            html = await w.fetch_html()
            status = f"[OK] ({len(html)} bytes)" if html else "[Empty/Restricted]"
            print(f"{w.name:<22}: {status} -> {w.source_url}")
        except Exception as e:
            print(f"{w.name:<22}: [Error] {e}")

    print("\nAll live pre-flight checks completed!\n")


if __name__ == "__main__":
    asyncio.run(main())
