"""Admin Interactive PDF Upload & Broadcast Handler."""

from datetime import datetime, timezone
import logging
import uuid
from aiogram import Router, Bot, F
from aiogram.filters.callback_data import CallbackData
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config.settings import get_settings
from database.session import get_session
from database.models import ExamCategory, MaterialType
from database import crud
from bot.middlewares.auth import IsAdminFilter

logger = logging.getLogger(__name__)
admin_upload_router = Router(name="admin_upload_router")
settings = get_settings()


class AdminUploadCallback(CallbackData, prefix="aup"):
    step: str  # "cat", "sub", "save", "bcast", "cancel", "back"
    uid: str  # Short 8-char upload ID to strictly respect Telegram 64-byte callback limit
    category: str = ""
    subject: str = ""


# In-memory storage for pending admin uploads (upload_id -> dict)
_PENDING_UPLOADS = {}


def get_categories_keyboard(upload_id: str) -> InlineKeyboardMarkup:
    """Keyboard to select Exam Category for uploaded PDF."""
    buttons = [
        [
            InlineKeyboardButton(
                text="🇮🇳 UPSC",
                callback_data=AdminUploadCallback(step="cat", category="upsc", uid=upload_id).pack(),
            ),
            InlineKeyboardButton(
                text="🏛️ MPSC",
                callback_data=AdminUploadCallback(step="cat", category="mpsc", uid=upload_id).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="👮 पोलीस भरती",
                callback_data=AdminUploadCallback(step="cat", category="police", uid=upload_id).pack(),
            ),
            InlineKeyboardButton(
                text="📑 सरळ सेवा (Talathi/ZP)",
                callback_data=AdminUploadCallback(step="cat", category="saral", uid=upload_id).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="⚡ JEE (Main & Adv)",
                callback_data=AdminUploadCallback(step="cat", category="jee", uid=upload_id).pack(),
            ),
            InlineKeyboardButton(
                text="🩺 NEET UG",
                callback_data=AdminUploadCallback(step="cat", category="neet", uid=upload_id).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="🏫 10th & 12th Board",
                callback_data=AdminUploadCallback(step="cat", category="board", uid=upload_id).pack(),
            ),
            InlineKeyboardButton(
                text="📖 NCERT (6th-12th)",
                callback_data=AdminUploadCallback(step="cat", category="ncert", uid=upload_id).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="🏦 Banking",
                callback_data=AdminUploadCallback(step="cat", category="bank", uid=upload_id).pack(),
            ),
            InlineKeyboardButton(
                text="🎯 SSC (CGL/CHSL)",
                callback_data=AdminUploadCallback(step="cat", category="ssc", uid=upload_id).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="🌐 शासन निर्णय (GR)",
                callback_data=AdminUploadCallback(step="cat", category="gr", uid=upload_id).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="❌ रद्द करा (Cancel)",
                callback_data=AdminUploadCallback(step="cancel", uid=upload_id).pack(),
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_subjects_keyboard(category: str, upload_id: str) -> InlineKeyboardMarkup:
    """Keyboard to select Subject based on category."""
    subjects_map = {
        "upsc": ["Prelims GS", "CSAT", "Mains GS 1-4", "Essay", "10 Years PYQ"],
        "mpsc": ["राज्यशास्त्र", "इतिहास", "भूगोल", "अर्थशास्त्र", "विज्ञान", "चालू घडामोडी", "PYQ प्रश्नपत्रिका"],
        "police": ["अंकगणित", "बुद्धिमत्ता", "मराठी व्याकरण", "पोलीस कायदे", "सराव प्रश्नसंच"],
        "saral": ["तलाठी प्रश्नसंच", "सामान्य ज्ञान", "इंग्रजी व्याकरण", "आरोग्य तांत्रिक"],
        "jee": ["Physics Formulas", "Chemistry Notes", "Maths Tricks", "JEE PYQs"],
        "neet": ["Biology Notes", "Chemistry PYQ", "Physics PYQ", "Mock Tests"],
        "board": ["10th SSC Question Bank", "10th Solutions", "12th HSC Science", "12th Commerce"],
        "ncert": ["Class 6-8 Science", "Class 9-10 Maths", "Class 11-12 Physics", "Class 11-12 Bio"],
        "bank": ["Quant", "Reasoning", "Banking Awareness", "English"],
        "ssc": ["Quant", "Reasoning", "General Awareness", "English"],
        "gr": ["शासन निर्णय", "भरती परिपत्रक", "आरक्षण नियम"],
    }

    subjects = subjects_map.get(category, ["सामान्य अध्ययन", "सराव पेपर"])
    buttons = []
    
    row = []
    for s in subjects:
        row.append(
            InlineKeyboardButton(
                text=s,
                callback_data=AdminUploadCallback(
                    step="sub", category=category, subject=s[:15], uid=upload_id
                ).pack(),
            )
        )
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([
        InlineKeyboardButton(
            text="🔙 मागे (Back)",
            callback_data=AdminUploadCallback(step="back", uid=upload_id).pack(),
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_action_keyboard(category: str, subject: str, upload_id: str) -> InlineKeyboardMarkup:
    """Keyboard to confirm broadcast or save to library only."""
    buttons = [
        [
            InlineKeyboardButton(
                text="📢 मंजूर आणि मुख्य चॅनेलवर प्रसारित करा",
                callback_data=AdminUploadCallback(
                    step="bcast", category=category, subject=subject, uid=upload_id
                ).pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text="💾 फक्त बॉट लायब्ररीत जतन करा (Save Only)",
                callback_data=AdminUploadCallback(
                    step="save", category=category, subject=subject, uid=upload_id
                ).pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ रद्द करा (Cancel)",
                callback_data=AdminUploadCallback(step="cancel", uid=upload_id).pack(),
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==============================================================================
# Handlers
# ==============================================================================

@admin_upload_router.message(F.document, IsAdminFilter())
async def handle_admin_document_upload(message: Message) -> None:
    """Intercept documents sent by admin in private chat for instant cataloging."""
    doc = message.document
    file_id = doc.file_id
    file_name = doc.file_name or "अभ्यास साहित्य.pdf"
    file_size_mb = round((doc.file_size or 0) / (1024 * 1024), 2)
    upload_id = str(uuid.uuid4())[:8]

    # Store in memory
    _PENDING_UPLOADS[upload_id] = {
        "file_id": file_id,
        "file_name": file_name,
        "caption": message.caption or file_name,
        "size_mb": file_size_mb,
    }

    text = (
        f"📥 <b>नवीन अभ्यास साहित्य प्राप्त झाले (New Document)</b>\n\n"
        f"📄 <b>नाव:</b> <code>{file_name}</code>\n"
        f"📊 <b>आकार:</b> {file_size_mb} MB\n\n"
        f"कृपया या साहित्यासाठी <b>परीक्षा प्रवर्ग (Category)</b> निवडा:"
    )

    await message.reply(text=text, reply_markup=get_categories_keyboard(upload_id))


@admin_upload_router.callback_query(AdminUploadCallback.filter(), IsAdminFilter())
async def handle_admin_upload_callbacks(
    callback: CallbackQuery,
    callback_data: AdminUploadCallback,
    bot: Bot,
) -> None:
    """Handle interactive multi-step buttons for document ingestion."""
    step = callback_data.step
    upload_id = callback_data.uid

    if step == "cancel":
        _PENDING_UPLOADS.pop(upload_id, None)
        await callback.message.edit_text("❌ अपलोड प्रक्रिया रद्द करण्यात आली.")
        await callback.answer("रद्द केले.")
        return

    if step == "back":
        await callback.message.edit_text(
            "कृपया <b>परीक्षा प्रवर्ग (Category)</b> निवडा:",
            reply_markup=get_categories_keyboard(upload_id),
        )
        await callback.answer()
        return

    if step == "cat":
        cat = callback_data.category
        await callback.message.edit_text(
            f"निवडलेला प्रवर्ग: <b>{cat.upper()}</b>\n\nकृपया <b>विषय (Subject)</b> निवडा:",
            reply_markup=get_subjects_keyboard(cat, upload_id),
        )
        await callback.answer()
        return

    if step == "sub":
        cat = callback_data.category
        subj = callback_data.subject
        doc_info = _PENDING_UPLOADS.get(upload_id, {})
        file_name = doc_info.get("file_name", "Study Material.pdf")

        text = (
            f"📋 <b>साहित्य तपशील पडताळणी:</b>\n\n"
            f"📄 <b>नाव:</b> {file_name}\n"
            f"📚 <b>प्रवर्ग:</b> {cat.upper()}\n"
            f"📖 <b>विषय:</b> {subj}\n\n"
            f"कृपया पुढील क्रिया निवडा:"
        )
        await callback.message.edit_text(
            text=text,
            reply_markup=get_action_keyboard(cat, subj, upload_id),
        )
        await callback.answer()
        return

    if step in ("bcast", "save"):
        cat_str = callback_data.category
        subj = callback_data.subject
        doc_info = _PENDING_UPLOADS.pop(upload_id, {})
        file_id = doc_info.get("file_id")
        file_name = doc_info.get("file_name", "Study Material.pdf")

        if not file_id:
            await callback.message.edit_text("⚠️ त्रुटी: फाईल डेटा सापडला नाही. कृपया पुन्हा अपलोड करा.")
            await callback.answer("Error")
            return

        cat_enum_map = {
            "upsc": ExamCategory.UPSC,
            "mpsc": ExamCategory.MPSC,
            "police": ExamCategory.POLICE_BHARTI,
            "saral": ExamCategory.SARAL_SEVA,
            "jee": ExamCategory.JEE,
            "neet": ExamCategory.NEET,
            "board": ExamCategory.BOARD_10_12,
            "ncert": ExamCategory.NCERT,
            "bank": ExamCategory.BANKING,
            "ssc": ExamCategory.SSC,
            "gr": ExamCategory.GENERAL,
        }
        category_enum = cat_enum_map.get(cat_str, ExamCategory.GENERAL)

        # 1. Save to Database
        async with get_session() as session:
            await crud.create_study_material(
                session=session,
                title=file_name.replace(".pdf", "").replace("_", " "),
                exam_category=category_enum,
                subject=subj,
                material_type=MaterialType.SHORT_NOTES,
                file_path=file_name,
                year=datetime.now().year,
                telegram_file_id=file_id,
            )

        # 2. If Broadcast is requested, send to Main Channel
        if step == "bcast":
            bot_info = await bot.get_me()
            bot_username = bot_info.username or "StudyBot"

            channel_caption = (
                f"📚 <b>नवीन अभ्यास साहित्य उपलब्ध | New Study Material</b>\n\n"
                f"📌 <b>{file_name.replace('.pdf', '').replace('_', ' ')}</b>\n\n"
                f"📖 <b>विषय:</b> {subj}\n"
                f"🏛️ <b>प्रवर्ग:</b> #{category_enum.value}\n\n"
                f"#StudyNotes #CompetitiveExams #{category_enum.value}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 बॉट वरून सर्व मोफत साहित्य मिळवण्यासाठी: @{bot_username}"
            )

            try:
                await bot.send_document(
                    chat_id=settings.main_channel_id,
                    document=file_id,
                    caption=channel_caption,
                )
                await callback.message.edit_text(
                    f"✅ <b>यशस्वी!</b>\n\nसाहित्य डेटाबेसमध्ये जतन केले आणि <b>@{settings.main_channel_id}</b> वर प्रसारित केले!"
                )
            except Exception as e:
                logger.error(f"Broadcast error: {e}")
                await callback.message.edit_text(
                    f"✅ <b>डेटाबेसमध्ये जतन केले!</b>\n(प्रसारण करताना त्रुटी: {e})"
                )
        else:
            await callback.message.edit_text(
                "✅ <b>यशस्वी!</b>\n\nसाहित्य बॉटच्या लायब्ररीत जतन केले. विद्यार्थी आता `/search` आणि मेन्यूद्वारे हे डाऊनलोड करू शकतात."
            )

        await callback.answer("यशस्वीरित्या जोडले!")
