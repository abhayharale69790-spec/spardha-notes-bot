"""Detached Resumable Production Mass Backfill Daemon Worker.

Runs independently as a background process with persistent checkpointing,
heartbeat telemetry, rate limiting, and exponential recovery.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import signal
import sys
from typing import Any, Dict, List, Optional
import uuid

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.types import MessageMediaDocument, DocumentAttributeFilename

from config.settings import get_settings
from database.session import init_db, get_session
from database import crud
from database.models import (
    BackfillJob,
    BackfillJobStatus,
    BackfillChannelTask,
    BackfillTaskStatus,
    ChannelAuthStatus,
    TelegramChannelSource,
    StudyMaterial,
)
from collectors.telegram_user_collector import telegram_user_collector
from collectors.telegram_channel_registry import telegram_channel_registry
from services.coverage_engine import coverage_engine

PID_FILE = Path("data/backfill_worker.pid")
STOP_FILE = Path("data/backfill_worker.stop")
STATUS_FILE = Path("data/backfill_status.json")
LOG_FILE = Path("data/backfill_daemon.log")

# Setup logging to both console and data/backfill_daemon.log
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Worker %(process)d] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
    ],
)
logger = logging.getLogger("backfill_daemon")
settings = get_settings()


class BackfillDaemon:
    """Enterprise-grade, detached, resumable mass backfill worker."""

    def __init__(self, per_channel_limit: int = 50, rate_delay: float = 1.5):
        self.per_channel_limit = per_channel_limit
        self.rate_delay = rate_delay
        self.stop_requested = False
        self.current_job: Optional[BackfillJob] = None
        self.current_task: Optional[BackfillChannelTask] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

    def _setup_signals(self):
        """Register graceful shutdown signals."""
        def handle_signal(sig, frame):
            logger.info(f"🛑 Received signal {sig}. Initiating graceful shutdown...")
            self.stop_requested = True

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

    def _write_pid(self):
        """Write current worker PID."""
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
        if STOP_FILE.exists():
            try: STOP_FILE.unlink()
            except Exception: pass

    def _cleanup_pid(self):
        """Remove PID file on termination."""
        if PID_FILE.exists():
            try: PID_FILE.unlink()
            except Exception: pass

    def _save_status_telemetry(self, current_channel_name: str = "", current_msg_id: int = 0):
        """Write real-time status snapshot to data/backfill_status.json."""
        if not self.current_job:
            return
        telemetry = {
            "job_id": self.current_job.id,
            "job_uuid": self.current_job.job_uuid,
            "status": self.current_job.status.value,
            "worker_pid": os.getpid(),
            "total_channels": self.current_job.total_channels,
            "completed_channels": self.current_job.completed_channels,
            "total_scanned": self.current_job.total_scanned,
            "total_ingested": self.current_job.total_ingested,
            "total_errors": self.current_job.total_errors,
            "current_channel": current_channel_name,
            "current_msg_id": current_msg_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        STATUS_FILE.write_text(json.dumps(telemetry, indent=2), encoding="utf-8")

    async def _heartbeat_loop(self):
        """Background task updating DB heartbeat every 5 seconds."""
        while not self.stop_requested:
            try:
                if self.current_job:
                    async with get_session() as session:
                        await crud.update_backfill_job_heartbeat(session, self.current_job.id)
                self._save_status_telemetry(
                    current_channel_name=self.current_task.title if self.current_task else "",
                    current_msg_id=self.current_task.last_successful_msg_id if self.current_task else 0,
                )
            except Exception as e_hb:
                logger.debug(f"Heartbeat update failed: {e_hb}")
            await asyncio.sleep(5.0)

    async def get_or_create_job(self) -> BackfillJob:
        """Find active/paused job or initialize a new mass backfill job with all authorized channels."""
        async with get_session() as session:
            existing_job = await crud.get_active_backfill_job(session)
            if existing_job:
                logger.info(f"🔄 Resuming existing Backfill Job #{existing_job.id} (UUID: {existing_job.job_uuid}) in state {existing_job.status.value}")
                await crud.update_backfill_job_status(
                    session,
                    existing_job.id,
                    BackfillJobStatus.RUNNING,
                    worker_pid=os.getpid(),
                )
                return existing_job

            # Query all active authorized channels
            sources = await telegram_channel_registry.get_all_approved_sources(session)
            if not sources:
                sources = await telegram_channel_registry.initialize_defaults(session)

            active_channels = [
                s for s in sources
                if s.is_active and s.authorization_status == ChannelAuthStatus.AUTHORIZED
            ]

            job_uuid = f"bf_{uuid.uuid4().hex[:12]}"
            logger.info(f"✨ Creating new Backfill Job '{job_uuid}' with {len(active_channels)} channels...")

            config = json.dumps({"per_channel_limit": self.per_channel_limit, "rate_delay": self.rate_delay})
            job = await crud.create_backfill_job(
                session=session,
                job_uuid=job_uuid,
                total_channels=len(active_channels),
                config_json=config,
                worker_pid=os.getpid(),
            )

            await crud.create_backfill_channel_tasks(
                session=session,
                job_id=job.id,
                channels=active_channels,
            )

            return job

    async def process_channel_task(self, task: BackfillChannelTask) -> int:
        """Process messages for a single channel with exact checkpointing and error recovery."""
        self.current_task = task
        channel_name = f"@{task.channel_username}" if task.channel_username else f"ID {task.channel_id}"
        logger.info(f"▶️ Processing Channel Task #{task.id}: {channel_name} ('{task.title}') from msg #{task.last_successful_msg_id}...")

        # Find or create corresponding TelegramChannelSource
        async with get_session() as session:
            source = await crud.get_telegram_channel_by_id(session, task.channel_id)
            if not source:
                source = await crud.get_or_create_telegram_channel(
                    session=session,
                    channel_id=task.channel_id,
                    channel_username=task.channel_username,
                    title=task.title,
                    exam_category=task.exam_category,
                    authorization_status=ChannelAuthStatus.AUTHORIZED,
                )

        # Verify explicit redistribution authorization
        if not getattr(source, "redistribution_authorized", True) or source.authorization_status != ChannelAuthStatus.AUTHORIZED:
            logger.warning(f"🚫 Skipping channel {channel_name}: Redistribution not authorized.")
            async with get_session() as session:
                await crud.fail_backfill_task(session, task.id, "Redistribution not authorized")
            return 0

        client = telegram_user_collector.client
        if not client or not client.is_connected():
            return 0


        entity = task.channel_username or task.channel_id
        ingested_in_task = 0
        scanned_in_task = 0
        last_msg_id = task.last_successful_msg_id

        try:
            # Query messages with min_id=task.last_successful_msg_id
            async for msg in client.iter_messages(entity, limit=self.per_channel_limit, min_id=task.last_successful_msg_id):
                if self.stop_requested or STOP_FILE.exists():
                    logger.info("⏸️ Stop signal detected. Pausing channel task...")
                    break

                if not msg:
                    continue

                scanned_in_task += 1
                last_msg_id = max(last_msg_id, msg.id)

                if msg.media and isinstance(msg.media, MessageMediaDocument) and msg.document:
                    mime = getattr(msg.document, "mime_type", "")
                    fname = ""
                    for attr in msg.document.attributes:
                        if isinstance(attr, DocumentAttributeFilename):
                            fname = attr.file_name or ""

                    if mime == "application/pdf" or fname.lower().endswith(".pdf"):
                        doc_size = getattr(msg.document, "size", 0)
                        if doc_size > 15 * 1024 * 1024:
                            logger.info(f"⏭️ Skipping oversized PDF ({doc_size / (1024*1024):.1f} MB) in msg #{msg.id}")
                            continue

                        logger.info(f"📥 Streaming PDF from msg #{msg.id} ({fname or 'document'}, {doc_size / 1024:.1f} KB)...")
                        safe_fname = re.sub(r'[^\w\.-]', '_', fname or 'document.pdf')
                        raw_target = Path("downloads/raw_telegram") / f"tg_{task.channel_id}_{msg.id}_{safe_fname}"
                        raw_target.parent.mkdir(parents=True, exist_ok=True)

                        try:
                            dl_result = await asyncio.wait_for(
                                client.download_media(msg, file=str(raw_target)),
                                timeout=30.0,
                            )
                            if dl_result and raw_target.exists():
                                raw_bytes = raw_target.read_bytes()
                                res = await telegram_user_collector.process_document_bytes(
                                    raw_pdf_bytes=raw_bytes,
                                    original_filename=fname,
                                    caption=msg.text or "",
                                    channel_source=source,
                                    msg_id=msg.id,
                                )
                                if res:
                                    ingested_in_task += 1
                                    # Update checkpoint in DB
                                    async with get_session() as session:
                                        await crud.update_backfill_task_progress(
                                            session=session,
                                            task_id=task.id,
                                            last_successful_msg_id=msg.id,
                                            scanned_delta=1,
                                            ingested_delta=1,
                                        )
                                        await crud.update_backfill_job_heartbeat(
                                            session=session,
                                            job_id=self.current_job.id,
                                            scanned_delta=1,
                                            ingested_delta=1,
                                        )
                                    await asyncio.sleep(self.rate_delay)
                        except asyncio.TimeoutError:
                            logger.warning(f"⚠️ Timeout downloading doc msg #{msg.id}, moving to next.")
                        except FloodWaitError as fwe:
                            logger.warning(f"⏳ Telegram FloodWait: sleeping {fwe.seconds + 2}s...")
                            await asyncio.sleep(fwe.seconds + 2)
                        except Exception as e_proc:
                            logger.warning(f"⚠️ Error processing msg #{msg.id}: {e_proc}")
                        finally:
                            if raw_target.exists():
                                try: raw_target.unlink()
                                except Exception: pass

                # Periodic checkpoint update even if no PDF in message
                if scanned_in_task % 10 == 0:
                    async with get_session() as session:
                        await crud.update_backfill_task_progress(
                            session=session,
                            task_id=task.id,
                            last_successful_msg_id=last_msg_id,
                            scanned_delta=10,
                            ingested_delta=0,
                        )

            # Mark task completion
            if not self.stop_requested and not STOP_FILE.exists():
                async with get_session() as session:
                    await crud.complete_backfill_task(
                        session=session,
                        task_id=task.id,
                        scanned_total=scanned_in_task,
                        ingested_total=ingested_in_task,
                    )
                logger.info(f"✅ Completed Channel Task #{task.id} ({channel_name}): +{ingested_in_task} PDFs ingested.")
            else:
                async with get_session() as session:
                    await crud.update_backfill_task_progress(
                        session=session,
                        task_id=task.id,
                        last_successful_msg_id=last_msg_id,
                    )

            return ingested_in_task

        except FloodWaitError as fwe:
            logger.warning(f"⏳ FloodWaitError during channel scan: {fwe.seconds}s required.")
            if fwe.seconds > 300:
                self.stop_requested = True
                async with get_session() as session:
                    await crud.update_backfill_job_status(
                        session,
                        self.current_job.id,
                        BackfillJobStatus.PAUSED,
                        error_message=f"Paused due to Telegram FloodWait: {fwe.seconds}s",
                    )
            else:
                await asyncio.sleep(fwe.seconds + 2)
            return ingested_in_task

        except Exception as e_task:
            logger.error(f"❌ Error in channel task #{task.id}: {e_task}", exc_info=True)
            async with get_session() as session:
                await crud.fail_backfill_task(session, task.id, str(e_task)[:200])
                await crud.update_backfill_job_heartbeat(session, self.current_job.id, errors_delta=1)
            return ingested_in_task

    async def run(self):
        """Main daemon execution loop."""
        self._setup_signals()
        self._write_pid()
        await init_db()

        logger.info(f"🚀 Starting Mass Backfill Daemon (PID: {os.getpid()})...")

        # Initialize MTProto collector
        is_ready = await telegram_user_collector.initialize_client()
        if not is_ready:
            logger.error("❌ MTProto Collector Client not authenticated. Daemon exiting.")
            self._cleanup_pid()
            return

        self.current_job = await self.get_or_create_job()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        try:
            while not self.stop_requested and not STOP_FILE.exists():
                # Fetch next pending task
                async with get_session() as session:
                    task = await crud.get_next_pending_backfill_task(session, self.current_job.id)

                if not task:
                    logger.info(f"🎉 All {self.current_job.total_channels} channels completed for Job #{self.current_job.id}!")
                    async with get_session() as session:
                        await crud.update_backfill_job_status(
                            session,
                            self.current_job.id,
                            BackfillJobStatus.COMPLETED,
                        )
                    break

                # Process channel task
                await self.process_channel_task(task)
                await asyncio.sleep(2.0)

            if self.stop_requested or STOP_FILE.exists():
                logger.info("🛑 Backfill Daemon paused/stopped by signal or control flag.")
                async with get_session() as session:
                    await crud.update_backfill_job_status(
                        session,
                        self.current_job.id,
                        BackfillJobStatus.PAUSED,
                    )

        except Exception as e_main:
            logger.critical(f"💥 Fatal daemon error: {e_main}", exc_info=True)
            if self.current_job:
                async with get_session() as session:
                    await crud.update_backfill_job_status(
                        session,
                        self.current_job.id,
                        BackfillJobStatus.FAILED,
                        error_message=str(e_main)[:200],
                    )
        finally:
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
            self._save_status_telemetry()
            self._cleanup_pid()
            if telegram_user_collector.client:
                await telegram_user_collector.client.disconnect()
            await telegram_user_collector.bot.session.close()
            logger.info("🏁 Backfill Daemon shut down cleanly.")


if __name__ == "__main__":
    daemon = BackfillDaemon(per_channel_limit=50, rate_delay=1.5)
    asyncio.run(daemon.run())
