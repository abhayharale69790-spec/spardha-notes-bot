"""Staging Channel Dispatcher - Formats and posts drafts for admin moderation."""

import logging
import os
from typing import Optional, Union
from aiogram import Bot
from aiogram.types import URLInputFile, FSInputFile, Message
from bot.keyboards.inline_menus import get_staging_action_keyboard
from config.settings import get_settings
from database.models import StagingQueue

logger = logging.getLogger(__name__)
settings = get_settings()


class StagingSender:
    """Handles dispatching scraped draft items into the private Admin Staging Channel."""

    def __init__(self, bot: Bot, staging_channel_id: Optional[Union[int, str]] = None) -> None:
        self.bot = bot
        self.staging_channel_id = staging_channel_id or settings.staging_channel_id

    async def post_draft_to_staging(self, item: StagingQueue) -> Optional[int]:
        """Post a new scraped document and bilingual draft summary to Staging Channel with approval buttons."""
        cat_str = item.exam_category.value if hasattr(item.exam_category, "value") else str(item.exam_category)
        type_str = item.material_type.value if hasattr(item.material_type, "value") else str(item.material_type)

        draft_caption = (
            f"📥 <b>[नवीन मसुदा / New Staging Notice]</b>\n"
            f"🆔 <b>Draft ID:</b> #{item.id}\n\n"
            f"📌 <b>{item.title}</b>\n"
            f"🏛️ <b>Category:</b> {cat_str} | 🏷️ <b>Type:</b> {type_str}\n\n"
            f"📝 <b>स्वयंचलित सारांश (Extracted Summary):</b>\n"
            f"{item.extracted_summary}\n\n"
            f"🔗 <a href='{item.source_url}'>मूळ स्रोत लिंक (Original Portal)</a>\n\n"
            f"👇 <i>प्रशासकांनी खालील बटण वापरून निर्णय घ्यावा:</i>"
        )

        keyboard = get_staging_action_keyboard(staging_id=item.id)

        try:
            # Attempt to send as document attachment if URL is valid
            if item.pdf_url.startswith("http://") or item.pdf_url.startswith("https://"):
                doc_file = URLInputFile(item.pdf_url, filename=f"Draft_{item.id}_{item.title[:30]}.pdf")
                sent_msg: Message = await self.bot.send_document(
                    chat_id=self.staging_channel_id,
                    document=doc_file,
                    caption=draft_caption,
                    reply_markup=keyboard,
                )
                return sent_msg.message_id
            elif os.path.exists(item.pdf_url):
                doc_file = FSInputFile(item.pdf_url, filename=f"Draft_{item.id}_{item.title[:30]}.pdf")
                sent_msg: Message = await self.bot.send_document(
                    chat_id=self.staging_channel_id,
                    document=doc_file,
                    caption=draft_caption,
                    reply_markup=keyboard,
                )
                return sent_msg.message_id
            else:
                # Text-only fallback with action keyboard
                sent_msg = await self.bot.send_message(
                    chat_id=self.staging_channel_id,
                    text=f"{draft_caption}\n\n📥 <b>PDF Link:</b> {item.pdf_url}",
                    reply_markup=keyboard,
                    disable_web_page_preview=False,
                )
                return sent_msg.message_id

        except Exception as e:
            logger.error(f"Error posting draft {item.id} to staging channel: {e}")
            try:
                # Direct message fallback
                fallback_msg = await self.bot.send_message(
                    chat_id=self.staging_channel_id,
                    text=f"⚠️ [PDF लोड अयशस्वी]\n\n{draft_caption}\n\n📥 <b>Direct Link:</b> {item.pdf_url}",
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )
                return fallback_msg.message_id
            except Exception as fb_err:
                logger.error(f"Fatal staging sender fallback error: {fb_err}")
                return None
