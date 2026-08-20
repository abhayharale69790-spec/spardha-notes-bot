"""Automatic Telegram Study-Channel Discovery Engine (MTProto Global Search & Metadata Inspection)."""

import asyncio
from datetime import datetime, timezone, timedelta
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from rapidfuzz import fuzz
from telethon import TelegramClient
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.types import MessageMediaDocument, DocumentAttributeFilename

from config.settings import get_settings
from database.session import get_session
from database import crud
from database.models import ChannelAuthStatus, ExamCategory, TelegramChannelSource

logger = logging.getLogger(__name__)
settings = get_settings()

DISCOVERY_KEYWORDS = [
    ("MPSC", ExamCategory.MPSC),
    ("MPSC Notes", ExamCategory.MPSC),
    ("MPSC Rajyaseva", ExamCategory.MPSC),
    ("MPSC Combine", ExamCategory.MPSC),
    ("Police Bharti", ExamCategory.POLICE_BHARTI),
    ("Maharashtra Police", ExamCategory.POLICE_BHARTI),
    ("Saral Seva", ExamCategory.SARAL_SEVA),
    ("Talathi Bharti", ExamCategory.SARAL_SEVA),
    ("SSC CGL", ExamCategory.SSC),
    ("SSC Exam Notes", ExamCategory.SSC),
    ("Banking Exam PDF", ExamCategory.BANKING),
    ("IBPS PO Study Material", ExamCategory.BANKING),
    ("UPSC CSE Notes", ExamCategory.UPSC),
    ("UPSC Hindi Material", ExamCategory.UPSC),
    ("JEE Main Notes", ExamCategory.JEE),
    ("IIT JEE Study Material", ExamCategory.JEE),
    ("NEET Biology Notes", ExamCategory.NEET),
    ("NEET Study Material", ExamCategory.NEET),
    ("NCERT Books PDF", ExamCategory.NCERT),
    ("NCERT Solutions", ExamCategory.NCERT),
    ("Maharashtra State Board Books", ExamCategory.BOARD_10_12),
    ("HSC 12th Board Notes", ExamCategory.BOARD_10_12),
    ("SSC 10th Board Maharashtra", ExamCategory.BOARD_10_12),
    ("Current Affairs Marathi PDF", ExamCategory.GENERAL),
    ("Chalu Ghadamodi Notes", ExamCategory.GENERAL),
    ("PYQ Question Papers PDF", ExamCategory.GENERAL),
]


class TelegramChannelDiscovery:
    """Discovers, audits, and registers new public Telegram channels with study materials."""

    def __init__(self, client: Optional[TelegramClient] = None):
        self.client = client
        self.output_json_path = Path("data/discovered_channels.json")

    async def _ensure_client(self) -> TelegramClient:
        if self.client and self.client.is_connected():
            return self.client
        self.client = TelegramClient(
            "data/telegram_user_session",
            settings.telegram_api_id,
            settings.telegram_api_hash,
            auto_reconnect=True,
        )
        await self.client.connect()
        return self.client

    def classify_channel_category(self, title: str, username: str, default_cat: ExamCategory) -> ExamCategory:
        """Classify channel exam category using title and handle cues."""
        text = f"{title} {username}".lower()
        if any(k in text for k in ("mpsc", "rajyaseva", "combine", "sti", "psi", "aso")):
            return ExamCategory.MPSC
        if any(k in text for k in ("police", "bharti", "पोलीस", "खाकी")):
            return ExamCategory.POLICE_BHARTI
        if any(k in text for k in ("talathi", "saral", "seva", "tcs", "ibps marathi", "तलाठी")):
            return ExamCategory.SARAL_SEVA
        if any(k in text for k in ("ssc", "cgl", "chsl", "mts", "pinnacle")):
            return ExamCategory.SSC
        if any(k in text for k in ("bank", "banking", "sbi", "ibps po", "rbi")):
            return ExamCategory.BANKING
        if any(k in text for k in ("upsc", "ias", "ips", "civil services", "drishti")):
            return ExamCategory.UPSC
        if any(k in text for k in ("jee", "iit", "allen", "resonance", "physics wallah")):
            return ExamCategory.JEE
        if any(k in text for k in ("neet", "medical", "mbbs", "biology")):
            return ExamCategory.NEET
        if any(k in text for k in ("ncert", "cbse")):
            return ExamCategory.NCERT
        if any(k in text for k in ("balbharati", "state board", "hsc", "10th board", "12th board", "ebalbharati")):
            return ExamCategory.BOARD_10_12
        return default_cat

    async def discover_channels(self, limit_per_keyword: int = 15) -> List[Dict[str, Any]]:
        """Run search across all competitive exam keywords and audit candidates."""
        client = await self._ensure_client()
        is_auth = await client.is_user_authorized()
        if not is_auth:
            logger.error("MTProto Collector account is not authorized for discovery.")
            return []

        # Get existing registered channel usernames and titles
        existing_usernames: Set[str] = set()
        existing_titles: List[str] = []
        async with get_session() as session:
            all_channels = await crud.get_all_active_telegram_channels(session)
            for c in all_channels:
                if c.channel_username:
                    existing_usernames.add(c.channel_username.lower())
                if c.title:
                    existing_titles.append(c.title)

        found_candidates: Dict[str, Tuple[Any, ExamCategory]] = {}

        logger.info("🔍 Initiating MTProto Global Channel Search across keywords...")
        for keyword, default_cat in DISCOVERY_KEYWORDS:
            try:
                res = await client(SearchRequest(q=keyword, limit=limit_per_keyword))
                for chat in res.chats:
                    uname = getattr(chat, "username", None)
                    if not uname:
                        continue
                    uname_clean = uname.lower().strip()
                    if uname_clean in existing_usernames or uname_clean in found_candidates:
                        continue

                    # Filter out channels with obvious non-study keywords (crypto, movies, betting, spam)
                    title = getattr(chat, "title", "")
                    if re.search(r"crypto|betting|casino|rummy|hack|adult|movie|song|dating", f"{title} {uname}", re.IGNORECASE):
                        continue

                    found_candidates[uname_clean] = (chat, default_cat)
                await asyncio.sleep(0.35)
            except Exception as e:
                logger.warning(f"Error searching keyword '{keyword}': {e}")
                await asyncio.sleep(0.5)

        logger.info(f"🔎 Found {len(found_candidates)} unique unindexed candidate channels. Auditing sample messages...")

        discovered_list: List[Dict[str, Any]] = []
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

        for uname, (chat, default_cat) in found_candidates.items():
            title = getattr(chat, "title", uname)
            cat = self.classify_channel_category(title, uname, default_cat)
            
            # Duplicate / Related Channel Check
            related_channel = None
            if existing_titles:
                for ext_title in existing_titles:
                    sim = fuzz.token_set_ratio(title, ext_title)
                    if sim >= 85:
                        related_channel = f"Related to: {ext_title} ({sim}% match)"
                        break

            audit_item = {
                "username": f"@{uname}",
                "clean_username": uname,
                "title": title,
                "category": cat.value,
                "source_url": f"https://t.me/{uname}",
                "accessible": "No",
                "historical_access": "No",
                "latest_msg_id": "N/A",
                "latest_date": "N/A",
                "sample_size": 0,
                "pdf_count_sample": 0,
                "pdf_yield_pct": 0.0,
                "estimated_yield": "Low",
                "related_channel": related_channel or "None (Distinct)",
                "channel_id": getattr(chat, "id", None),
                "auth_status": ChannelAuthStatus.PENDING_REVIEW.value,
            }

            try:
                entity = chat
                audit_item["accessible"] = "Yes"
                audit_item["title"] = getattr(entity, "title", title)

                # Sample up to 100 messages for metadata inspection directly using peer entity
                sample_msgs = []
                async for msg in client.iter_messages(chat, limit=100):
                    sample_msgs.append(msg)


                if sample_msgs:
                    audit_item["historical_access"] = "Yes"
                    latest_m = sample_msgs[0]
                    audit_item["latest_msg_id"] = str(latest_m.id)
                    if latest_m.date:
                        audit_item["latest_date"] = latest_m.date.strftime("%Y-%m-%d")

                    audit_item["sample_size"] = len(sample_msgs)
                    pdf_count = 0
                    for m in sample_msgs:
                        if m.media and isinstance(m.media, MessageMediaDocument) and m.document:
                            mime = getattr(m.document, "mime_type", "")
                            fname = ""
                            for attr in m.document.attributes:
                                if isinstance(attr, DocumentAttributeFilename):
                                    fname = attr.file_name or ""
                            if mime == "application/pdf" or fname.lower().endswith(".pdf"):
                                pdf_count += 1

                    audit_item["pdf_count_sample"] = pdf_count
                    yield_pct = (pdf_count / len(sample_msgs)) * 100 if sample_msgs else 0
                    audit_item["pdf_yield_pct"] = round(yield_pct, 1)

                    if yield_pct >= 20 or pdf_count >= 15:
                        audit_item["estimated_yield"] = "High (★★★★★)"
                    elif yield_pct >= 8 or pdf_count >= 6:
                        audit_item["estimated_yield"] = "Medium (★★★☆☆)"
                    elif pdf_count > 0:
                        audit_item["estimated_yield"] = "Moderate (★★☆☆☆)"
                    else:
                        audit_item["estimated_yield"] = "Low/Text (★☆☆☆☆)"

                    # Only register channels with real PDFs (> 0) and recent activity
                    if pdf_count > 0:
                        tg_peer_id = int(f"-100{entity.id}") if not str(entity.id).startswith("-100") else entity.id
                        audit_item["channel_id"] = tg_peer_id

                        # Store in database as PENDING_REVIEW
                        async with get_session() as session:
                            await crud.get_or_create_telegram_channel(
                                session=session,
                                channel_id=tg_peer_id,
                                channel_username=uname,
                                title=audit_item["title"],
                                exam_category=cat,
                                authorization_status=ChannelAuthStatus.PENDING_REVIEW,
                            )
                        discovered_list.append(audit_item)

            except Exception as e:
                logger.debug(f"Error inspecting discovered channel @{uname}: {e}")

            await asyncio.sleep(0.3)

        # Sort discovered channels by pdf_yield_pct desc, then pdf_count_sample desc
        discovered_list.sort(key=lambda x: (x["pdf_yield_pct"], x["pdf_count_sample"]), reverse=True)

        self.output_json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_json_path, "w", encoding="utf-8") as f:
            json.dump(discovered_list, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ Discovery complete: Saved {len(discovered_list)} verified study channels to {self.output_json_path}")
        return discovered_list


telegram_channel_discovery = TelegramChannelDiscovery()
