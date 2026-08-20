"""Production Multi-Task Asynchronous Application Entry Point (Webhook & Polling Dual-Mode)."""

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
from aiogram.types import Update
import httpx
from sqlalchemy import select, func
from config.settings import get_settings
from database.session import init_db, get_session
from database.models import StudyMaterial, ExamCategory, MaterialType
from database import crud
from bot.bot_instance import setup_bot_and_dispatcher
from scraper.portal_watcher import ScraperOrchestrator
from scraper.staging_sender import StagingSender
from workers.backup_worker import DatabaseBackupWorker
from scripts.bulk_seed_materials import BULK_MATERIALS

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
# Automatic Initial Catalog Seeder (Runs automatically on cloud container boot)
# ==============================================================================

async def auto_seed_catalog_if_empty() -> None:
    """Ensure database is automatically pre-populated with study materials on boot."""
    try:
        from scripts.initial_seed import seed_pre_launch_catalog
        await seed_pre_launch_catalog()
    except Exception as e:
        logger.error(f"Auto-seed error on startup: {e}", exc_info=True)



# ==============================================================================
# Lightweight AIOHTTP Web Health & Telegram Webhook Server
# ==============================================================================

async def handle_root(request: web.Request) -> web.Response:
    """Root landing endpoint for cloud load balancers and uptime monitors."""
    return web.json_response(
        {
            "status": "online",
            "service": "Telegram Study Platform & Document Distribution Engine",
            "bot": "@SpardhaNotes_bot",
            "version": "2.2.0",
            "mode": request.app.get("bot_mode", "webhook"),
            "uptime_utc": datetime.now(timezone.utc).isoformat(),
        }
    )


async def handle_health(request: web.Request) -> web.Response:
    """Health check probe endpoint returning 200 OK for Render / Koyeb."""
    return web.json_response(
        {
            "status": "healthy",
            "bot_active": True,
            "mode": request.app.get("bot_mode", "webhook"),
            "scraper_active": True,
            "backup_active": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


async def handle_telegram_webhook(request: web.Request) -> web.Response:
    """Process incoming Telegram updates pushed directly to the webhook endpoint."""
    bot: Bot = request.app["bot"]
    dp: Dispatcher = request.app["dp"]
    try:
        data = await request.json()
        update = Update.model_validate(data, context={"bot": bot})
        await dp.feed_update(bot, update)
        return web.Response(text="OK", status=200)
    except Exception as e:
        logger.error(f"Webhook update processing error: {e}", exc_info=True)
        return web.Response(text="OK", status=200)


def create_web_app(bot: Bot, dp: Dispatcher) -> web.Application:
    """Create configured aiohttp web application with health and webhook routes."""
    app = web.Application()
    app["bot"] = bot
    app["dp"] = dp
    app["bot_mode"] = "webhook"

    app.router.add_get("/", handle_root)
    app.router.add_get("/health", handle_health)
    app.router.add_post("/webhook", handle_telegram_webhook)
    return app


async def start_web_server(app: web.Application, port: int) -> tuple[web.AppRunner, web.TCPSite]:
    """Start asynchronous web server bound to 0.0.0.0:PORT."""
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Web Server listening on http://0.0.0.0:{port} (Webhook + Health Probe Ready)")
    return runner, site


# ==============================================================================
# Cloud Keep-Alive Heartbeat (Prevents Free Tier Sleep)
# ==============================================================================

async def run_self_ping_heartbeat(stop_event: asyncio.Event, port: int) -> None:
    """Periodic task pinging self endpoint to prevent cloud sleep states."""
    render_url = os.getenv("RENDER_EXTERNAL_URL", f"http://localhost:{port}").rstrip("/")
    ping_url = f"{render_url}/health"
    logger.info(f"Keep-alive heartbeat configured for: {ping_url}")

    # Wait 60s before initial ping
    await asyncio.sleep(60)

    async with httpx.AsyncClient(timeout=10.0) as client:
        while not stop_event.is_set():
            try:
                r = await client.get(ping_url)
                logger.info(f"Keep-alive heartbeat ping ({ping_url}) -> Status: {r.status_code}")
            except Exception as e:
                logger.debug(f"Keep-alive heartbeat failed: {e}")

            try:
                # Ping every 8 minutes (Render sleeps at 15 mins)
                await asyncio.wait_for(stop_event.wait(), timeout=480)
            except asyncio.TimeoutError:
                pass


# ==============================================================================
# Background Scraper Scheduler
# ==============================================================================

async def run_scraper_scheduler(bot: Bot, stop_event: asyncio.Event) -> None:
    """Periodic background task that triggers portal scraping at configured intervals."""
    orchestrator = ScraperOrchestrator()
    staging_sender = StagingSender(bot=bot)

    interval_seconds = settings.scrape_interval_minutes * 60
    logger.info(f"Scraper scheduler active (Interval: {settings.scrape_interval_minutes}m).")

    # Initial boot delay
    await asyncio.sleep(10)

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
    """Bootstrap web server, database, webhook registration, and workers."""
    logger.info("Starting Telegram Study Platform & Document Distribution Engine (v2.2 Production)...")

    # 1. Configure Telegram Bot and Dispatcher
    bot, dp = setup_bot_and_dispatcher()

    # 2. Start Web Server with Webhook Endpoint
    app = create_web_app(bot, dp)
    port = int(os.getenv("PORT", 10000))
    runner, site = await start_web_server(app, port)

    # 3. Initialize Database Schema & Auto-Seed Default Catalog
    try:
        await init_db()
        await auto_seed_catalog_if_empty()
    except Exception as db_err:
        logger.error(f"Database initialization error: {db_err}")

    # 4. Determine Deployment Mode (Webhook vs Polling)
    render_external_url = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    if not render_external_url and os.getenv("RENDER"):
        render_external_url = "https://spardha-notes-bot.onrender.com"

    # 5. Setup Graceful Shutdown Coordination
    stop_event = asyncio.Event()
    background_tasks: List[asyncio.Task] = []

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: stop_event.set())
        except (NotImplementedError, RuntimeError):
            pass

    try:
        # Launch Heartbeat Worker
        heartbeat_task = asyncio.create_task(
            run_self_ping_heartbeat(stop_event=stop_event, port=port),
            name="heartbeat_worker",
        )
        background_tasks.append(heartbeat_task)

        # Launch Scraper Background Worker
        scraper_task = asyncio.create_task(
            run_scraper_scheduler(bot=bot, stop_event=stop_event),
            name="scraper_scheduler_worker",
        )
        background_tasks.append(scraper_task)

        # Launch Disaster Recovery Backup Worker
        backup_worker = DatabaseBackupWorker(bot=bot)
        backup_task = asyncio.create_task(
            backup_worker.run_backup_scheduler(stop_event=stop_event),
            name="db_backup_worker",
        )
        background_tasks.append(backup_task)

        if render_external_url or os.getenv("WEBHOOK_URL"):
            webhook_base = render_external_url or os.getenv("WEBHOOK_URL", "").rstrip("/")
            webhook_url = f"{webhook_base}/webhook"
            logger.info(f"Configuring Telegram Webhook: {webhook_url}")
            await bot.set_webhook(
                url=webhook_url,
                drop_pending_updates=False,
                allowed_updates=dp.resolve_used_update_types(),
            )
            logger.info("Telegram Webhook successfully set! Listening for incoming updates...")
            # Keep running until stop_event is set
            await stop_event.wait()
        else:
            logger.info("No WEBHOOK_URL / RENDER_EXTERNAL_URL detected. Falling back to Long Polling mode...")
            await bot.delete_webhook(drop_pending_updates=False)
            app["bot_mode"] = "polling"
            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
            )

    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Shutdown signal received.")
    finally:
        logger.info("Commencing graceful shutdown sequence...")
        stop_event.set()

        for t in background_tasks:
            if not t.done():
                t.cancel()

        if background_tasks:
            await asyncio.gather(*background_tasks, return_exceptions=True)

        await runner.cleanup()
        await bot.session.close()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Application exited.")
