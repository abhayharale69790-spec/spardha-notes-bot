"""Automated Disaster Recovery Backup Worker - Exports and uploads DB dumps to Telegram."""

import asyncio
from datetime import datetime, timezone
import gzip
import hashlib
import logging
import os
from pathlib import Path
import shutil
import sqlite3
from typing import Optional

from aiogram import Bot
from aiogram.types import FSInputFile
from config.settings import get_settings
from database.session import get_session
from database.models import StudyMaterial, StagingQueue
from sqlalchemy import select, func

logger = logging.getLogger(__name__)
settings = get_settings()


class DatabaseBackupWorker:
    """Scheduled worker for daily automated database exports and Telegram channel uploads."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.backup_dir = settings.backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    async def create_backup_archive(self) -> Optional[Path]:
        """Create a compressed database dump archive."""
        db_url = settings.get_effective_db_url()
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        # ----------------------------------------------------------------------
        # Case A: SQLite Database Snapshot
        # ----------------------------------------------------------------------
        if db_url.startswith("sqlite+aiosqlite:///"):
            db_path = db_url.replace("sqlite+aiosqlite:///", "")
            if not os.path.exists(db_path):
                logger.warning(f"SQLite file {db_path} not found for backup.")
                return None

            archive_path = self.backup_dir / f"studybot_backup_{timestamp_str}.sqlite.gz"
            try:
                # Use SQLite online backup to ensure clean consistency without locks
                temp_db_copy = self.backup_dir / f"temp_{timestamp_str}.db"
                src_conn = sqlite3.connect(db_path)
                dst_conn = sqlite3.connect(str(temp_db_copy))
                src_conn.backup(dst_conn)
                src_conn.close()
                dst_conn.close()

                # GZIP compress
                with open(temp_db_copy, "rb") as f_in:
                    with gzip.open(archive_path, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)

                # Remove uncompressed temp copy
                if temp_db_copy.exists():
                    temp_db_copy.unlink()

                logger.info(f"SQLite backup created: {archive_path}")
                return archive_path
            except Exception as e:
                logger.error(f"Error creating SQLite backup archive: {e}")
                return None

        # ----------------------------------------------------------------------
        # Case B: PostgreSQL Data Export (Generic SQL Dump)
        # ----------------------------------------------------------------------
        archive_path = self.backup_dir / f"studybot_pg_export_{timestamp_str}.sql.gz"
        try:
            sql_statements = []
            sql_statements.append(f"-- Study Platform Database Backup: {timestamp_str} UTC\n")

            async with get_session() as session:
                # Export StudyMaterials
                res_mat = await session.execute(select(StudyMaterial))
                materials = res_mat.scalars().all()
                sql_statements.append(f"-- Study Materials: {len(materials)} records\n")
                for m in materials:
                    year_val = m.year if m.year is not None else "NULL"
                    file_id_val = f"'{m.telegram_file_id}'" if m.telegram_file_id else "NULL"
                    clean_title = m.title.replace("'", "''")
                    clean_subj = m.subject.replace("'", "''")
                    clean_path = m.file_path.replace("'", "''")
                    sql_statements.append(
                        f"INSERT INTO study_materials (id, title, exam_category, subject, material_type, year, file_path, telegram_file_id) "
                        f"VALUES ({m.id}, '{clean_title}', '{m.exam_category.value}', '{clean_subj}', '{m.material_type.value}', {year_val}, '{clean_path}', {file_id_val}) "
                        f"ON CONFLICT (id) DO NOTHING;\n"
                    )

                # Export StagingQueue
                res_stg = await session.execute(select(StagingQueue))
                staging_items = res_stg.scalars().all()
                sql_statements.append(f"\n-- Staging Queue: {len(staging_items)} records\n")
                for s in staging_items:
                    clean_st_title = s.title.replace("'", "''")
                    clean_src = s.source_url.replace("'", "''")
                    clean_pdf = s.pdf_url.replace("'", "''")
                    clean_sum = s.extracted_summary.replace("'", "''")
                    stg_msg_val = s.staging_message_id if s.staging_message_id is not None else "NULL"
                    sql_statements.append(
                        f"INSERT INTO staging_queue (id, title, source_url, pdf_url, extracted_summary, exam_category, subject, material_type, status, staging_message_id) "
                        f"VALUES ({s.id}, '{clean_st_title}', '{clean_src}', '{clean_pdf}', '{clean_sum}', '{s.exam_category.value}', '{s.subject}', '{s.material_type.value}', '{s.status.value}', {stg_msg_val}) "
                        f"ON CONFLICT (source_url) DO NOTHING;\n"
                    )

            dump_bytes = "".join(sql_statements).encode("utf-8")
            with gzip.open(archive_path, "wb") as f_out:
                f_out.write(dump_bytes)

            logger.info(f"PostgreSQL SQL backup created: {archive_path}")
            return archive_path

        except Exception as e:
            logger.error(f"Error creating PostgreSQL database export: {e}")
            return None

    def _compute_sha256(self, file_path: Path) -> str:
        """Compute SHA-256 hash of backup file for integrity verification."""
        sha = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                sha.update(chunk)
        return sha.hexdigest()

    async def execute_backup_and_upload(self) -> bool:
        """Generate backup archive and upload directly to private backup channel."""
        logger.info("Starting automated disaster recovery backup routine...")

        archive_path = await self.create_backup_archive()
        if not archive_path or not archive_path.exists():
            logger.error("Backup creation failed. Skipping Telegram upload.")
            return False

        file_size_kb = round(archive_path.stat().st_size / 1024, 2)
        sha256_hash = self._compute_sha256(archive_path)
        timestamp_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Query metrics for the caption
        material_count = 0
        staging_count = 0
        try:
            async with get_session() as session:
                mat_res = await session.execute(select(func.count(StudyMaterial.id)))
                material_count = mat_res.scalar() or 0
                stg_res = await session.execute(select(func.count(StagingQueue.id)))
                staging_count = stg_res.scalar() or 0
        except Exception:
            pass

        caption = (
            f"📦 <b>[Disaster Recovery Backup Archive]</b>\n"
            f"📅 <b>Timestamp:</b> <code>{timestamp_now}</code>\n"
            f"📊 <b>Study Materials:</b> {material_count} | <b>Staging Drafts:</b> {staging_count}\n"
            f"💾 <b>Archive Size:</b> {file_size_kb} KB\n"
            f"🔒 <b>SHA-256:</b> <code>{sha256_hash[:16]}...{sha256_hash[-8:]}</code>\n\n"
            f"🤖 <i>Automated Daily Backup Engine | Oracle Ubuntu Node</i>"
        )

        try:
            doc_file = FSInputFile(archive_path, filename=archive_path.name)
            await self.bot.send_document(
                chat_id=settings.backup_channel_id,
                document=doc_file,
                caption=caption,
            )
            logger.info(f"Database backup uploaded successfully to {settings.backup_channel_id}")
            self._cleanup_old_backups(keep_days=7)
            return True
        except Exception as upload_err:
            logger.error(f"Failed to upload backup to Telegram channel: {upload_err}")
            return False

    def _cleanup_old_backups(self, keep_days: int = 7) -> None:
        """Purge backup archives older than keep_days to manage disk space."""
        try:
            now = time_now = datetime.now(timezone.utc).timestamp()
            cutoff = time_now - (keep_days * 86400)
            for f in self.backup_dir.glob("*.gz"):
                if f.stat().st_mtime < cutoff:
                    f.unlink()
                    logger.info(f"Purged expired backup archive: {f.name}")
        except Exception as e:
            logger.warning(f"Error during backup cleanup: {e}")

    async def run_backup_scheduler(self, stop_event: asyncio.Event) -> None:
        """Run daily automated backup loop."""
        interval_sec = settings.backup_interval_hours * 3600
        logger.info(f"Backup scheduler running (Interval: {settings.backup_interval_hours} hours).")

        # Initial backup delay
        await asyncio.sleep(60)

        while not stop_event.is_set():
            try:
                await self.execute_backup_and_upload()
            except Exception as e:
                logger.error(f"Backup scheduler error: {e}", exc_info=True)

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_sec)
            except asyncio.TimeoutError:
                pass
