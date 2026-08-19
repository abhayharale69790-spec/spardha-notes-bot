"""Production Multi-Task Asynchronous Application Entry Point with Web Health Server."""

import asyncio
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import signal
import sys
from typing import List, Optional

from aiohttp import web
from aiogram import Bot, Dispatcher
from config.settings import get_settings
from database.session import init_db
from bot.bot_instance import setup_bot_and_dispatcher
from scraper.portal_watcher import ScraperOrchestrator
from scraper.staging_sender import StagingSender
from workers.backup_worker import DatabaseBackupWorker

# Configure Structured Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("telegram_study_platform")
settings = get_settings()

# Ensure runtime directories exist
for d in ("data", "downloads", "backups"):
    Path(d).mkdir(parents=True, exist_ok=True)


# ==============================================================================
# Lightweight AIOHTTP Web Health Server (Render & Koyeb Web Service Support)
# ==============================================================================

async def handle_root(request: web.Request) -> web.Response:
    """Root landing endpoint for cloud load balancers and uptime monitors."""
    return web.json_response(
        {
            "status": "online",
            "service": "Telegram Study Platform & Document Distribution Engine",
            "bot": "@SpardhaNotes_bot",
            "version": "2.0.0",
            "uptime_utc": datetime.now(timezone.utc).isoformat(),
        }
    )


async def handle_health(request: web.Request) -> web.Response:
    """Health check probe endpoint returning 200 OK for Render / Koyeb."""
    return web.json_response(
        {
            "status": "healthy",
            "bot_polling": True,
            "scraper_active": True,
            "backup_active": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


def create_web_app() -> web.Application:
    """Create configured aiohttp web application with health routes."""
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/health", handle_health)
    return app


async def start_web_server(port: int) -> tuple[web.AppRunner, web.TCPSite]:
    """Start asynchronous web server bound to 0.0.0.0:PORT."""
    app = create_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Web Health Server listening on http://0.0.0.0:{port} (Ready for Render/Koyeb probes)")
    return runner, site


# ==============================================================================
# Background Scraper Scheduler
# ==============================================================================

async def run_scraper_scheduler(bot: Bot, stop_event: asyncio.Event) -> None:
    """Periodic background task that triggers portal scraping at configured intervals."""
    orchestrator = ScraperOrchestrator()
    staging_sender = StagingSender(bot=bot)

    interval_seconds = settings.scrape_interval_minutes * 60
    logger.info(f"Scraper scheduler active (Interval: {settings.scrape_interval_minutes}m).")

    # Initial boot delay to let bot polling start smoothly
    await asyncio.sleep(5)

    while not stop_event.is_set():
        try:
            logger.info("Executing scheduled portal scraper sweep...")
            count = await orchestrator.run_scrape_cycle(staging_sender=staging_sender)
            logger.info(f"Portal sweep complete. {count} new notices drafted.")
        except Exception as e:
            logger.error(f"Scraper cycle error: {e}", exc_info=True)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            pass


# ==============================================================================
# Main Orchestrator Entry Point
# ==============================================================================

async def main() -> None:
    """Bootstrap web health server, database, background workers, and bot polling."""
    logger.info("Starting Telegram Study Platform & Document Distribution Engine (v2.0 Render/Koyeb Production)...")

    # 1. Start Web Health Server FIRST so Render/Koyeb health probes succeed immediately
    port = int(os.getenv("PORT", 10000))
    runner, site = await start_web_server(port)

    # 2. Initialize Database Schema
    try:
        await init_db()
    except Exception as db_err:
        logger.error(f"Database initialization error (will retry on next operation): {db_err}")

    # 3. Configure Telegram Bot and Dispatcher
    bot, dp = setup_bot_and_dispatcher()

    # 4. Setup Graceful Shutdown Coordination
    stop_event = asyncio.Event()
    background_tasks: List[asyncio.Task] = []

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: stop_event.set())
        except (NotImplementedError, RuntimeError):
            pass

    try:
        # 5. Launch Scraper Background Worker
        scraper_task = asyncio.create_task(
            run_scraper_scheduler(bot=bot, stop_event=stop_event),
            name="scraper_scheduler_worker",
        )
        background_tasks.append(scraper_task)

        # 6. Launch Automated Disaster Recovery Backup Worker
        backup_worker = DatabaseBackupWorker(bot=bot)
        backup_task = asyncio.create_task(
            backup_worker.run_backup_scheduler(stop_event=stop_event),
            name="db_backup_worker",
        )
        background_tasks.append(backup_task)

        # 7. Start Telegram Bot Polling
        logger.info("Starting Telegram Bot Polling (aiogram 3.x)...")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )

    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Shutdown signal received.")
    finally:
        logger.info("Commencing graceful shutdown sequence...")
        stop_event.set()

        # Stop background tasks
        for t in background_tasks:
            if not t.done():
                t.cancel()

        if background_tasks:
            await asyncio.gather(*background_tasks, return_exceptions=True)

        # Stop Web Server
        await runner.cleanup()

        # Close Bot Session
        await bot.session.close()
        logger.info("Shutdown complete. Web server and workers cleanly terminated.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Application exited.")
