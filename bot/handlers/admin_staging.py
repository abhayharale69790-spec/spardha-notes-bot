"""Admin Moderation and Approval Handlers with Rate-Limited Broadcasting."""

from datetime import datetime, timezone
import os
from aiogram import Router, Bot
from aiogram.types import CallbackQuery, URLInputFile, FSInputFile
from config.settings import get_settings
from database.session import get_session
from database.models import StagingStatus, ExamCategory, MaterialType, StagingQueue
from database import crud
from bot.keyboards.inline_menus import StagingApprovalCallback
from bot.middlewares.auth import IsAdminFilter

admin_staging_router = Router(name="admin_staging_router")
settings = get_settings()


@admin_staging_router.callback_query(StagingApprovalCallback.filter(), IsAdminFilter())
async def handle_staging_action(
    callback: CallbackQuery,
    callback_data: StagingApprovalCallback,
    bot: Bot,
) -> None:
    """Handle admin approval or rejection of scraped notices in Staging Channel."""
    user_id = callback.from_user.id
    user_name = callback.from_user.username or callback.from_user.full_name or str(user_id)

    staging_id = callback_data.staging_id
    action = callback_data.action.lower()

    async with get_session() as session:
        item: StagingQueue = await crud.get_staging_item_by_id(session, item_id=staging_id)

    if not item:
        await callback.answer("⚠️ हा मसुदा आढळला नाही (Staging item not found).", show_alert=True)
        return

    if item.status != StagingStatus.PENDING:
        await callback.answer(
            f"ℹ️ हा मसुदा आधीच प्रक्रिया केला गेला आहे (Status: {item.status.value}).",
            show_alert=True,
        )
        return

    # --------------------------------------------------------------------------
    # 1. Handle Rejection / Discard
    # --------------------------------------------------------------------------
    if action == "discard":
        async with get_session() as session:
            await crud.update_staging_status(
                session, item_id=staging_id, status=StagingStatus.REJECTED
            )

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        discard_text = (
            f"{callback.message.text or callback.message.caption or ''}\n\n"
            f"❌ <b>मसुदा नाकारला (Discarded)</b>\n"
            f"👤 Administrator: @{user_name}\n"
            f"⏰ Time: {now_str}"
        )

        if callback.message:
            if callback.message.caption:
                await callback.message.edit_caption(caption=discard_text, reply_markup=None)
            elif callback.message.text:
                await callback.message.edit_text(text=discard_text, reply_markup=None)

        await callback.answer("❌ मसुदा नाकारण्यात आला (Draft discarded).")
        return

    # --------------------------------------------------------------------------
    # 2. Handle Approval & Broadcast to Main Channel
    # --------------------------------------------------------------------------
    if action == "approve":
        await callback.answer("⏳ मुख्य चॅनेलवर प्रसारित करत आहे...")

        cat_tag = f"#{item.exam_category.value}"
        type_tag = f"#{item.material_type.value}"
        bot_info = await bot.get_me()
        bot_username = bot_info.username or "StudyBot"

        broadcast_caption = (
            f"📢 <b>नवीन अधिकृत अपडेट | Official Update</b>\n\n"
            f"📌 <b>{item.title}</b>\n\n"
            f"{item.extracted_summary}\n\n"
            f"🔗 <a href='{item.source_url}'>मूळ स्रोत / अधिकृत पोर्टल (Official Source)</a>\n\n"
            f"{cat_tag} {type_tag} #MPSC #PoliceBharti #ExamAlert\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 अधिक अभ्यास साहित्यासाठी: @{bot_username}"
        )

        telegram_file_id = None

        try:
            # Broadcast PDF / Document to Main Channel
            if item.pdf_url.startswith("http://") or item.pdf_url.startswith("https://"):
                doc_file = URLInputFile(item.pdf_url, filename=f"{item.title[:45]}.pdf")
                sent_broadcast = await bot.send_document(
                    chat_id=settings.main_channel_id,
                    document=doc_file,
                    caption=broadcast_caption,
                )
                if sent_broadcast.document:
                    telegram_file_id = sent_broadcast.document.file_id
            elif os.path.exists(item.pdf_url):
                doc_file = FSInputFile(item.pdf_url, filename=f"{item.title[:45]}.pdf")
                sent_broadcast = await bot.send_document(
                    chat_id=settings.main_channel_id,
                    document=doc_file,
                    caption=broadcast_caption,
                )
                if sent_broadcast.document:
                    telegram_file_id = sent_broadcast.document.file_id
            else:
                await bot.send_message(
                    chat_id=settings.main_channel_id,
                    text=broadcast_caption,
                    disable_web_page_preview=False,
                )

        except Exception as e:
            await bot.send_message(
                chat_id=settings.main_channel_id,
                text=f"{broadcast_caption}\n\n📥 <i>डाउनलोड करा: {item.pdf_url}</i>",
                disable_web_page_preview=False,
            )

        # Update Database: Save to StudyMaterial and update StagingQueue
        async with get_session() as session:
            await crud.create_study_material(
                session=session,
                title=item.title,
                exam_category=item.exam_category,
                subject=item.subject,
                material_type=item.material_type,
                file_path=item.pdf_url,
                year=item.year or datetime.now().year,
                telegram_file_id=telegram_file_id,
            )
            await crud.update_staging_status(
                session=session,
                item_id=staging_id,
                status=StagingStatus.APPROVED,
            )

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        approved_text = (
            f"{callback.message.text or callback.message.caption or ''}\n\n"
            f"✅ <b>मंजूर आणि प्रसारित (Approved & Broadcasted)</b>\n"
            f"👤 Approved by: @{user_name}\n"
            f"⏰ Time: {now_str}"
        )

        if callback.message:
            if callback.message.caption:
                await callback.message.edit_caption(caption=approved_text, reply_markup=None)
            elif callback.message.text:
                await callback.message.edit_text(text=approved_text, reply_markup=None)

        await callback.answer("✅ यशस्वीरित्या मंजूर आणि प्रसारित केले!")
