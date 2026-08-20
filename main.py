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

# ==============================================================================
# Lightweight AIOHTTP Web Health & Telegram Webhook Server
# ==============================================================================

async def handle_root(request: web.Request) -> web.Response:
    """Rich responsive HTML landing page for web visitors and search engines."""
    html_content = f"""<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{settings.brand_name} • MPSC / UPSC / POLICE BHARTI / JEE / NEET</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&family=Noto+Sans+Devanagari:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary: #2563eb;
            --accent: #f59e0b;
            --bg: #0f172a;
            --card-bg: rgba(30, 41, 59, 0.7);
            --text: #f8fafc;
            --text-muted: #94a3b8;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Poppins', 'Noto Sans Devanagari', sans-serif; }}
        body {{
            background: radial-gradient(circle at top center, #1e293b 0%, #0f172a 100%);
            color: var(--text);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .container {{
            max-width: 800px;
            width: 100%;
            background: var(--card-bg);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 24px;
            padding: 40px;
            text-align: center;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        }}
        .badge {{
            display: inline-block;
            background: rgba(37, 99, 235, 0.2);
            color: #60a5fa;
            border: 1px solid rgba(96, 165, 250, 0.3);
            padding: 6px 16px;
            border-radius: 999px;
            font-size: 0.85rem;
            font-weight: 600;
            margin-bottom: 20px;
            letter-spacing: 0.5px;
        }}
        h1 {{
            font-size: 2.2rem;
            font-weight: 800;
            background: linear-gradient(135deg, #ffffff 0%, #cbd5e1 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 12px;
        }}
        .subtitle {{
            color: var(--text-muted);
            font-size: 1.05rem;
            margin-bottom: 30px;
            line-height: 1.6;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 16px;
            margin-bottom: 35px;
        }}
        .stat-card {{
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 18px;
        }}
        .stat-number {{
            font-size: 1.8rem;
            font-weight: 700;
            color: var(--accent);
        }}
        .stat-label {{
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-top: 4px;
        }}
        .btn-group {{
            display: flex;
            flex-wrap: wrap;
            gap: 16px;
            justify-content: center;
        }}
        .btn {{
            display: inline-flex;
            align-items: center;
            gap: 10px;
            padding: 14px 28px;
            border-radius: 14px;
            font-size: 1rem;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.2s ease;
        }}
        .btn-primary {{
            background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
            color: #ffffff;
            box-shadow: 0 10px 25px -5px rgba(37, 99, 235, 0.4);
        }}
        .btn-primary:hover {{
            transform: translateY(-2px);
            box-shadow: 0 15px 30px -5px rgba(37, 99, 235, 0.6);
        }}
        .btn-secondary {{
            background: rgba(255, 255, 255, 0.08);
            color: #ffffff;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .btn-secondary:hover {{
            background: rgba(255, 255, 255, 0.15);
            transform: translateY(-2px);
        }}
        .footer {{
            margin-top: 35px;
            font-size: 0.85rem;
            color: #64748b;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="badge">🚀 LIVE TELEGRAM STUDY ENGINE</div>
        <h1>{settings.brand_name}</h1>
        <p class="subtitle">
            महाराष्ट्र व भारतातील सर्व स्पर्धा परीक्षांसाठी मोफत प्रमाणित अभ्यास साहित्य, 
            मागील प्रश्नपत्रिका (PYQ), पुस्तके आणि शासन निर्णय (GR).
        </p>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">569+</div>
                <div class="stat-label">प्रमाणित साहित्य (Materials)</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">10</div>
                <div class="stat-label">परीक्षा प्रवर्ग (Exams Covered)</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">100%</div>
                <div class="stat-label">मोफत व अधिकृत (Free & Verified)</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">24x7</div>
                <div class="stat-label">झटपट डाऊनलोड (Instant)</div>
            </div>
        </div>

        <div class="btn-group">
            <a href="https://t.me/SpardhaNotes_bot" class="btn btn-primary" target="_blank">
                🤖 टेलिग्राम बॉट उघडा (@SpardhaNotes_bot)
            </a>
            <a href="https://t.me/spardhanoteshub" class="btn btn-secondary" target="_blank">
                📢 मुख्य चॅनेल (@spardhanoteshub)
            </a>
        </div>

        <div class="footer">
            © 2026 {settings.brand_name} • Developed for Competitive Students • All Rights Reserved.
        </div>
    </div>
</body>
</html>"""
    return web.Response(text=html_content, content_type="text/html")


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
    """Create configured aiohttp web application with health, webhook, and catch-all routes."""
    app = web.Application()
    app["bot"] = bot
    app["dp"] = dp
    app["bot_mode"] = "webhook"

    app.router.add_get("/", handle_root)
    app.router.add_get("/health", handle_health)
    app.router.add_post("/webhook", handle_telegram_webhook)
    # Catch-all GET route for any unrecognized URL path
    app.router.add_get("/{tail:.*}", handle_root)
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
