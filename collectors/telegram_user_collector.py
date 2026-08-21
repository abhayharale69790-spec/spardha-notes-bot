"""Dedicated Telegram MTProto User-Account Collector.

Runs a separate MTProto user client with persistent session storage to:
1. Discover study material PDFs in approved Telegram channels.
2. Download physical byte streams.
3. Strictly validate %PDF- header, page count, and educational usefulness.
4. Deduplicate via binary SHA-256 hashes.
5. Classify Exam -> Subject -> Topic.
6. Watermark with HARALE DIGITAL STUDY POINT branding.
7. Upload via bot to obtain permanent telegram_file_id.
8. Index with full provenance (t.me/... message URL).
9. Integrate with Syllabus Coverage Engine.
"""

import asyncio
from datetime import datetime, timezone
import hashlib
import io
import logging
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import FSInputFile
from pypdf import PdfReader
from sqlalchemy import select
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeFilename, MessageMediaDocument

from config.settings import get_settings
from database import crud
from database.models import ChannelAuthStatus, ExamCategory, MaterialType, SourceType, StudyMaterial, TelegramChannelSource
from database.session import get_session
from services.coverage_engine import coverage_engine
from services.pdf_watermark import apply_harale_branding_to_pdf
from services.syllabus_registry import get_exam_syllabus
from workers.quality_worker import QualityWorker


logger = logging.getLogger(__name__)
settings = get_settings()

RAW_TELEGRAM_DOWNLOADS = Path("downloads/telegram_raw")
RAW_TELEGRAM_DOWNLOADS.mkdir(parents=True, exist_ok=True)


class TelegramUserCollector:
    """Autonomous Telegram MTProto User-Account Ingestion Engine."""

    def __init__(
        self,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        session_name: Optional[str] = None,
        session_string: Optional[str] = None,
    ):
        self.api_id = api_id or settings.telegram_api_id
        self.api_hash = api_hash or settings.telegram_api_hash
        self.session_name = session_name or settings.telegram_session_name
        self.session_string = session_string or settings.telegram_session_string

        self.client: Optional[TelegramClient] = None
        self.bot = Bot(token=settings.bot_token)
        self.staging_chat_id = settings.staging_channel_id or settings.main_channel_id or 8691719772
        self._is_running = False
        self._seen_hashes: Set[str] = set()

    async def initialize_client(self) -> bool:
        """Initialize Telethon MTProto client with persistent session."""
        if not self.api_id or not self.api_hash:
            logger.info("ℹ️ Telegram API ID / API Hash not configured in environment; collector ready for credential activation.")
            return False

        try:
            if self.session_string:
                session = StringSession(self.session_string)
            else:
                session = self.session_name

            self.client = TelegramClient(session, self.api_id, self.api_hash)
            await self.client.connect()

            if not await self.client.is_user_authorized():
                logger.warning("⚠️ MTProto User Client session requires login / authorization.")
                return False

            me = await self.client.get_me()
            logger.info(f"✅ Telegram MTProto Collector authorized as: {me.first_name} (@{me.username or me.id})")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Telegram MTProto client: {e}")
            return False

    def classify_telegram_content(
        self,
        caption: str,
        text_preview: str,
        filename: str,
        channel_category: ExamCategory,
    ) -> Tuple[ExamCategory, str, str, MaterialType, Optional[int]]:
        """Classify message text & filename into Exam -> Subject -> Topic -> MaterialType."""
        combined = f"{caption} {text_preview} {filename}".lower()

        # 1. Determine Exam Category
        exam_cat = channel_category
        if "mpsc" in combined or "राज्यसेवा" in combined:
            exam_cat = ExamCategory.MPSC
        elif "पोलीस" in combined or "police" in combined:
            exam_cat = ExamCategory.POLICE_BHARTI
        elif "तलाठी" in combined or "talathi" in combined or "saral seva" in combined:
            exam_cat = ExamCategory.SARAL_SEVA
        elif "upsc" in combined:
            exam_cat = ExamCategory.UPSC
        elif "jee" in combined:
            exam_cat = ExamCategory.JEE
        elif "neet" in combined:
            exam_cat = ExamCategory.NEET
        elif "ssc" in combined or "cgl" in combined:
            exam_cat = ExamCategory.SSC
        elif "banking" in combined or "ibps" in combined or "sbi" in combined:
            exam_cat = ExamCategory.BANKING
        elif "ncert" in combined:
            exam_cat = ExamCategory.NCERT
        elif "board" in combined or "hsc" in combined or "ssc 10th" in combined:
            exam_cat = ExamCategory.BOARD_10_12

        # 2. Extract Year
        year_match = re.search(r"\b(201[5-9]|202[0-6])\b", combined)
        year = int(year_match.group(1)) if year_match else 2024

        # 3. Determine MaterialType
        mtype = MaterialType.SHORT_NOTES
        if "pyq" in combined or "प्रश्नपत्रिका" in combined or "question paper" in combined or "answer key" in combined:
            mtype = MaterialType.PYQ
        elif "mock" in combined or "test" in combined or "सराव" in combined or "practice" in combined:
            mtype = MaterialType.TEST_PAPER
        elif "syllabus" in combined or "अभ्यासक्रम" in combined:
            mtype = MaterialType.SYLLABUS
        elif "gr" in combined or "शासन निर्णय" in combined or "परिपत्रक" in combined:
            mtype = MaterialType.GR
        elif "chalu ghadamodi" in combined or "current affairs" in combined or "चालू घडामोडी" in combined:
            mtype = MaterialType.CURRENT_AFFAIRS

        # 4. Map Subject & Topic using Syllabus Registry
        syllabus = get_exam_syllabus(exam_cat)
        subject_name = "General Studies"
        topic_name = "General Concepts"


        if syllabus:
            best_score = -1.0
            for subj in syllabus.subjects:
                for top in subj.topics:
                    score = sum(1 for kw in top.keywords if kw.lower() in combined)
                    for kw in subj.keywords:
                        if kw.lower() in combined:
                            score += 0.5
                    if score > best_score:
                        best_score = score
                        subject_name = subj.name
                        topic_name = top.name

        return exam_cat, subject_name, topic_name, mtype, year

    async def process_document_bytes(
        self,
        raw_pdf_bytes: bytes,
        original_filename: str,
        caption: str,
        channel_source: TelegramChannelSource,
        msg_id: int,
    ) -> Optional[StudyMaterial]:
        """Validate, brand, upload via bot, and index a physical PDF stream from Telegram."""
        # 1. Strict %PDF- Header Check
        if not raw_pdf_bytes.startswith(b"%PDF-"):
            logger.warning(f"🚫 Rejected non-PDF stream from Telegram msg #{msg_id} in {channel_source.title}")
            return None

        # 2. Minimum size check (must be at least 1 KB)
        if len(raw_pdf_bytes) < 1024:
            logger.warning(f"🚫 Rejected undersized document ({len(raw_pdf_bytes)} bytes) from Telegram msg #{msg_id}")
            return None

        # 3. Structural validation and text extraction
        try:
            reader = PdfReader(io.BytesIO(raw_pdf_bytes))
            page_count = len(reader.pages)
            if page_count < 1:
                logger.warning(f"🚫 Rejected 0-page document from Telegram msg #{msg_id}")
                return None

            text_chunks = []
            for idx in range(min(page_count, 10)):
                t = reader.pages[idx].extract_text()
                if t:
                    text_chunks.append(t)
            extracted_text = "\n".join(text_chunks)
        except Exception as e:
            logger.warning(f"🚫 Broken PDF file from Telegram msg #{msg_id}: {e}")
            return None

        # 4. Binary SHA-256 Deduplication
        content_hash = hashlib.sha256(raw_pdf_bytes).hexdigest()
        async with get_session() as session:
            existing = await crud.get_material_by_hash(session, content_hash)
            if existing:
                logger.info(f"ℹ️ Skipped duplicate document (SHA-256: {content_hash[:8]}...) from Telegram msg #{msg_id}")
                return None

        # 5. Clean Title Construction
        clean_name = Path(original_filename).stem.replace("_", " ") if original_filename else ""
        if len(clean_name) >= 15:
            doc_title = clean_name
        elif caption and len(caption.strip()) >= 15:
            doc_title = caption.split("\n")[0][:120].strip()
        else:
            doc_title = f"{channel_source.exam_category.value} {channel_source.title} Study PDF #{msg_id}"

        # 6. Educational Usefulness Check
        is_useful, reason = QualityWorker.check_educational_usefulness(
            title=doc_title,
            text=extracted_text,
            page_count=page_count,
        )
        if not is_useful:
            logger.info(f"🚫 Rejected non-educational Telegram document ({reason}): {doc_title}")
            return None

        # 7. Classification
        exam_cat, subject_name, topic_name, mtype, year = self.classify_telegram_content(
            caption=caption,
            text_preview=extracted_text[:1000],
            filename=original_filename,
            channel_category=channel_source.exam_category,
        )

        # 8. Save Physical File to Disk
        raw_fname = f"tg_{channel_source.channel_id}_{msg_id}_{content_hash[:8]}.pdf"
        raw_path = RAW_TELEGRAM_DOWNLOADS / raw_fname
        raw_path.write_bytes(raw_pdf_bytes)

        # 9. Watermark with HARALE DIGITAL STUDY POINT branding
        branded_path = apply_harale_branding_to_pdf(str(raw_path))

        # 10. Upload via Bot to obtain permanent telegram_file_id
        tg_file_id = None
        source_url = f"https://t.me/{channel_source.channel_username or channel_source.channel_id}/{msg_id}"
        for attempt in range(3):
            try:
                input_doc = FSInputFile(str(branded_path), filename=f"{subject_name}_{exam_cat.value}_{mtype.value}.pdf".replace(" ", "_"))
                sent_msg = await self.bot.send_document(
                    chat_id=self.staging_chat_id,
                    document=input_doc,
                    caption=(
                        f"📚 <b>{doc_title}</b>\n"
                        f"🏛️ #{exam_cat.value} • 📖 {subject_name}\n"
                        f"🔗 <i>Source: {source_url}</i>\n\n"
                        f"⚡ <i>{settings.brand_name}</i>"
                    ),
                )
                if sent_msg and sent_msg.document:
                    tg_file_id = sent_msg.document.file_id
                break
            except TelegramRetryAfter as tra:
                logger.info(f"Telegram flood limit: waiting {tra.retry_after + 1}s...")
                await asyncio.sleep(tra.retry_after + 1)
            except Exception as e:
                if attempt == 2:
                    logger.error(f"Failed to upload branded Telegram document to storage: {e}")
                await asyncio.sleep(2.0)

        # 11. Index in Database with Full Provenance
        async with get_session() as session:
            mat = await crud.create_study_material(
                session=session,
                title=doc_title,
                exam_category=exam_cat,
                subject=subject_name,
                material_type=mtype,
                file_path=str(Path(branded_path).resolve()),
                year=year,
                topic=topic_name,
                language="Marathi" if "मराठी" in extracted_text or "महाराष्ट्र" in extracted_text else "Bilingual",
                source_type=SourceType.AUTHORIZED if channel_source.authorization_status == ChannelAuthStatus.AUTHORIZED else SourceType.COMMUNITY,
                source_name=f"Telegram @{channel_source.channel_username or channel_source.title}",
                source_url=source_url,
                source_doc_id=str(msg_id),
                page_count=page_count,
                content_hash=content_hash,
                extracted_text=extracted_text[:3000],
                quality_score=95,
                status="VERIFIED",
                telegram_file_id=tg_file_id,
            )

            await crud.update_telegram_channel_scan_progress(
                session=session,
                channel_id=channel_source.channel_id,
                last_scanned_msg_id=msg_id,
                new_downloaded=1,
                new_verified=1,
            )

        logger.info(f"✅ Ingested Telegram Document #{mat.id}: '{doc_title}' ({page_count} pages, Tg Msg #{msg_id})")

        # 12. Trigger Coverage Engine Matrix Update
        await coverage_engine.compute_coverage_matrix(force_refresh=True)

        return mat

    async def scan_channel_messages(
        self,
        channel_source: TelegramChannelSource,
        limit: int = 50,
    ) -> int:
        """Backfill and scan messages from an authorized Telegram channel using MTProto."""
        if not self.client or not self.client.is_connected():
            return 0

        ingested_count = 0
        try:
            entity = channel_source.channel_username or channel_source.channel_id
            logger.info(f"📡 Scanning Telegram Channel '{channel_source.title}' (@{channel_source.channel_username})...")

            async for msg in self.client.iter_messages(entity, limit=limit, min_id=channel_source.last_scanned_msg_id):
                if not msg or not msg.media:
                    continue

                if isinstance(msg.media, MessageMediaDocument) and msg.document:
                    mime = getattr(msg.document, "mime_type", "")
                    fname = ""
                    for attr in msg.document.attributes:
                        if isinstance(attr, DocumentAttributeFilename):
                            fname = attr.file_name

                    if mime == "application/pdf" or fname.lower().endswith(".pdf"):
                        doc_size = getattr(msg.document, "size", 0)
                        if doc_size > 15 * 1024 * 1024:
                            logger.info(f"⏭️ Skipping oversized PDF ({doc_size / (1024*1024):.1f} MB) from msg #{msg.id}")
                            continue

                        logger.info(f"📥 Streaming PDF from msg #{msg.id} ({fname or 'document'}, {doc_size / 1024:.1f} KB)...")
                        safe_fname = re.sub(r'[^\w\.-]', '_', fname or 'document.pdf')
                        raw_target = RAW_TELEGRAM_DOWNLOADS / f"tg_{channel_source.channel_id}_{msg.id}_{safe_fname}"

                        try:
                            dl_result = await asyncio.wait_for(
                                self.client.download_media(msg, file=str(raw_target)),
                                timeout=30.0,
                            )

                            if dl_result and raw_target.exists():
                                raw_bytes = raw_target.read_bytes()
                                res = await self.process_document_bytes(
                                    raw_pdf_bytes=raw_bytes,
                                    original_filename=fname,
                                    caption=msg.text or "",
                                    channel_source=channel_source,
                                    msg_id=msg.id,
                                )
                                if res:
                                    ingested_count += 1
                                    await asyncio.sleep(1.0)
                        except asyncio.TimeoutError:
                            logger.warning(f"⚠️ Timeout downloading document from msg #{msg.id}, skipping.")
                        except Exception as e_dl:
                            logger.warning(f"⚠️ Error downloading msg #{msg.id}: {e_dl}")
                        finally:
                            if raw_target.exists():
                                try: raw_target.unlink()
                                except Exception: pass


            return ingested_count

        except Exception as e:
            logger.error(f"Error during Telegram channel scan for {channel_source.title}: {e}")
            return ingested_count

    async def start_live_monitoring(self, stop_event: Optional[asyncio.Event] = None) -> None:
        """Start real-time continuous events.NewMessage listener across all approved Telegram channels."""
        stop_event = stop_event or asyncio.Event()

        logger.info("🚀 Initializing Continuous Telegram MTProto Live Monitor...")
        is_ready = await self.initialize_client()
        if not is_ready:
            logger.warning("⚠️ MTProto User Client not authenticated. Live monitoring standby.")
            return

        from collectors.telegram_channel_registry import telegram_channel_registry

        async with get_session() as session:
            sources = await telegram_channel_registry.get_all_approved_sources(session)
            if not sources:
                sources = await telegram_channel_registry.initialize_defaults(session)

        channel_map: Dict[str, TelegramChannelSource] = {}
        chat_entities = []

        for s in sources:
            if not s.is_active:
                continue
            # Exclude frozen/historical-only archives from continuous NewMessage event polling
            if getattr(s, "monitoring_mode", "CONTINUOUS") == "HISTORICAL_ONLY":
                logger.info(f"⏳ Skipping live continuous event registration for HISTORICAL_ONLY archive: {s.title} (@{s.channel_username})")
                continue
            entity_key = s.channel_username or s.channel_id
            channel_map[str(s.channel_id)] = s
            if s.channel_username:
                channel_map[s.channel_username.lower()] = s
            chat_entities.append(entity_key)

        logger.info(f"📡 Subscribing live event listener to {len(chat_entities)} continuous-monitoring Telegram channels...")


        @self.client.on(events.NewMessage(chats=chat_entities))
        async def on_new_channel_message(event):
            try:
                msg = event.message
                if not msg or not msg.media:
                    return

                chat = await event.get_chat()
                chat_title = getattr(chat, "title", str(event.chat_id))
                chat_username = getattr(chat, "username", "").lower()
                logger.info(f"🔔 [LIVE NEW MESSAGE] Detected post in '{chat_title}' (Msg #{msg.id})")

                # Match source
                source = channel_map.get(str(event.chat_id)) or channel_map.get(chat_username)
                if not source:
                    # Fallback lookup
                    async with get_session() as session:
                        source = await crud.get_or_create_telegram_channel(
                            session=session,
                            channel_id=event.chat_id,
                            channel_username=chat_username,
                            title=chat_title,
                            exam_category=ExamCategory.GENERAL,
                            authorization_status=ChannelAuthStatus.AUTHORIZED,
                        )

                if isinstance(msg.media, MessageMediaDocument) and msg.document:
                    mime = getattr(msg.document, "mime_type", "")
                    fname = ""
                    for attr in msg.document.attributes:
                        if isinstance(attr, DocumentAttributeFilename):
                            fname = attr.file_name

                    if mime == "application/pdf" or fname.lower().endswith(".pdf"):
                        doc_size = getattr(msg.document, "size", 0)
                        if doc_size > 35 * 1024 * 1024:
                            logger.info(f"⏭️ Skipping oversized live PDF ({doc_size / (1024*1024):.1f} MB) from msg #{msg.id}")
                            return

                        logger.info(f"📥 [LIVE INGESTION] Streaming PDF from msg #{msg.id} ({fname or 'document'}, {doc_size / 1024:.1f} KB)...")
                        safe_fname = re.sub(r'[^\w\.-]', '_', fname or 'document.pdf')
                        raw_target = RAW_TELEGRAM_DOWNLOADS / f"tg_{source.channel_id}_{msg.id}_{safe_fname}"

                        dl_result = await asyncio.wait_for(
                            self.client.download_media(msg, file=str(raw_target)),
                            timeout=60.0,
                        )
                        if dl_result and raw_target.exists():
                            raw_bytes = raw_target.read_bytes()
                            res = await self.process_document_bytes(
                                raw_pdf_bytes=raw_bytes,
                                original_filename=fname,
                                caption=msg.text or "",
                                channel_source=source,
                                msg_id=msg.id,
                            )
                            if res:
                                logger.info(f"🎉 [LIVE HARVEST SUCCESS] Ingested '{res.title}' from '{chat_title}' (Msg #{msg.id})")
            except Exception as e:
                logger.error(f"Error handling live Telegram message event: {e}", exc_info=True)

        logger.info(f"✅ Telegram MTProto Live Event Listener active and running ({len(chat_entities)} channels subscribed).")

        # Keep running until stop event is triggered, with periodic heartbeat check
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=60.0)
            except asyncio.TimeoutError:
                pass


telegram_user_collector = TelegramUserCollector()

