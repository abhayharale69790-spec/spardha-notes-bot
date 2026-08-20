"""Interactive PDF Ingestion & Study Material Upload Engine for Admins & Students."""

from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import uuid
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from config.settings import get_settings
from database.session import get_session
from database.models import ExamCategory, MaterialType
from database import crud
from services.pdf_watermark import apply_harale_branding_to_pdf

logger = logging.getLogger(__name__)
admin_upload_router = Router(name="admin_upload_router")
settings = get_settings()


@admin_upload_router.message(Command("upload", "contribute", "add"))
async def handle_upload_command(message: Message) -> None:
    """Provide interactive guide for uploading study material PDFs."""
    user_id = message.from_user.id if message.from_user else 0
    is_admin = settings.is_admin(user_id)

    if is_admin:
        text = (
            "📤 <b>अभ्यास साहित्य अपलोड मोड (Admin Upload Mode):</b>\n\n"
            "कृपया मला थेट <b>PDF फाईल</b> पाठवा (Document स्वरूपात).\n\n"
            "बॉट आपोआप खालील प्रक्रिया पूर्ण करेल:\n"
            "1️⃣ <b>'HARALE DIGITAL STUDY POINT'</b> वॉटरमार्क जोडेल.\n"
            "2️⃣ Telegram <code>file_id</code> कॅश करेल.\n"
            "3️⃣ परीक्षा प्रवर्ग व विषय निवडून डेटाबेसमध्ये नोंद करेल.\n"
            "4️⃣ मुख्य चॅनेलवर (@spardhanoteshub) थेट ब्रॉडकास्ट करण्याचा पर्याय देईल.\n\n"
            "💡 <i>आताच कोणतीही PDF फाईल या चॅटमध्ये पाठवा.</i>"
        )
    else:
        text = (
            "📥 <b>अभ्यास साहित्य पाठवा (Community Study Hub):</b>\n\n"
            "विद्यार्थी मित्रांनो! आपल्याकडील दर्जेदार हस्तलिखित नोट्स, प्रश्नपत्रिका किंवा सराव पेपर्स "
            "आपण इतर विद्यार्थ्यांसाठी शेअर करू शकता.\n\n"
            "📌 <b>कसे पाठवावे:</b>\n"
            "फक्त कोणतीही <b>PDF फाईल</b> थेट या चॅटमध्ये पाठवा. त्यानंतर विषय निवडा. "
            "प्रशासकीय तपासणीनंतर ती मुख्य चॅनेलवर सर्वांसाठी उपलब्ध होईल.\n\n"
            "💡 <i>आताच आपली PDF फाईल पाठवा.</i>"
        )

    await message.reply(text)


class AdminUploadCallback(CallbackData, prefix="aup"):
    step: str  # "cat", "sub", "save", "bcast", "cancel", "back"
    uid: str  # Short 8-char upload ID to strictly respect Telegram 64-byte callback limit
    category: str = ""
    subject: str = ""


# In-memory storage for pending uploads (upload_id -> dict)
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


def get_action_keyboard(category: str, subject: str, upload_id: str, is_admin: bool = True) -> InlineKeyboardMarkup:
    """Keyboard to confirm broadcast or submit to staging queue."""
    if is_admin:
        buttons = [
            [
                InlineKeyboardButton(
                    text="📢 ब्रॉडकास्ट व जतन करा (Broadcast)",
                    callback_data=AdminUploadCallback(
                        step="bcast", category=category, subject=subject, uid=upload_id
                    ).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="💾 केवळ लायब्ररीत जतन करा (Save Only)",
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
    else:
        buttons = [
            [
                InlineKeyboardButton(
                    text="📤 तपासणीसाठी पाठवा (Submit for Review)",
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
# Document Upload Handler
# ==============================================================================

@admin_upload_router.message(F.document)
async def handle_document_upload(message: Message) -> None:
    """Intercept documents sent in chat for cataloging & watermarking."""
    doc = message.document
    file_id = doc.file_id
    file_name = doc.file_name or "अभ्यास साहित्य.pdf"
    file_size_mb = round((doc.file_size or 0) / (1024 * 1024), 2)
    upload_id = str(uuid.uuid4())[:8]
    user_id = message.from_user.id if message.from_user else 0
    is_admin = settings.is_admin(user_id)

    # Store in memory
    _PENDING_UPLOADS[upload_id] = {
        "file_id": file_id,
        "file_name": file_name,
        "caption": message.caption or file_name,
        "size_mb": file_size_mb,
        "user_id": user_id,
        "user_name": message.from_user.username or message.from_user.full_name or "User",
        "is_admin": is_admin,
    }

    role_badge = "👑 <b>प्रशासक अपलोड (Admin Mode)</b>" if is_admin else "🎓 <b>विद्यार्थी योगदान (Community Upload)</b>"

    text = (
        f"📥 <b>नवीन अभ्यास साहित्य प्राप्त झाले!</b>\n\n"
        f"{role_badge}\n"
        f"📄 <b>नाव:</b> <code>{file_name}</code>\n"
        f"📊 <b>आकार:</b> {file_size_mb} MB\n"
        f"🏷️ <b>ब्रँडिंग:</b> HARALE DIGITAL STUDY POINT (Auto-Watermark)\n\n"
        f"कृपया या साहित्यासाठी <b>परीक्षा प्रवर्ग (Category)</b> निवडा:"
    )

    await message.reply(text=text, reply_markup=get_categories_keyboard(upload_id))


@admin_upload_router.callback_query(AdminUploadCallback.filter())
async def handle_upload_callbacks(
    callback: CallbackQuery,
    callback_data: AdminUploadCallback,
    bot: Bot,
) -> None:
    """Handle interactive multi-step buttons for document ingestion & watermarking."""
    step = callback_data.step
    upload_id = callback_data.uid
    user_id = callback.from_user.id if callback.from_user else 0
    is_admin = settings.is_admin(user_id)

    if step == "cancel":
        _PENDING_UPLOADS.pop(upload_id, None)
        await callback.message.edit_text("❌ प्रक्रिया रद्द करण्यात आली.")
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
            reply_markup=get_action_keyboard(cat, subj, upload_id, is_admin=is_admin),
        )
        await callback.answer()
        return

    if step in ("bcast", "save"):
        cat_str = callback_data.category
        subj = callback_data.subject
        doc_info = _PENDING_UPLOADS.pop(upload_id, {})
        file_id = doc_info.get("file_id")
        file_name = doc_info.get("file_name", "Study Material.pdf")
        uploader_name = doc_info.get("user_name", "User")
        doc_is_admin = doc_info.get("is_admin", is_admin)

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

        # 1. Apply HARALE DIGITAL STUDY POINT Auto-Branding & Watermarking
        final_file_id = file_id
        if settings.watermark_enabled:
            try:
                await callback.message.edit_text("🎨 <b>'HARALE DIGITAL STUDY POINT' वॉटरमार्क जोडत आहे...</b>")
                temp_in = Path("downloads") / f"temp_in_{upload_id}.pdf"
                temp_out = Path("downloads") / f"temp_branded_{upload_id}.pdf"
                temp_in.parent.mkdir(parents=True, exist_ok=True)

                file_info = await bot.get_file(file_id)
                if file_info.file_path:
                    await bot.download_file(file_info.file_path, destination=temp_in)
                    branded_path = apply_harale_branding_to_pdf(
                        input_pdf_path=str(temp_in),
                        output_pdf_path=str(temp_out),
                        brand_name=settings.brand_name,
                        channel=settings.brand_channel,
                        bot_username=settings.brand_bot,
                    )
                    if os.path.exists(branded_path):
                        branded_input = FSInputFile(branded_path, filename=f"[HDSP] {file_name}")
                        sent_doc = await bot.send_document(
                            chat_id=settings.staging_channel_id,
                            document=branded_input,
                            caption=f"🏷️ [HARALE DIGITAL STUDY POINT Branded]\n📄 {file_name}\n👤 Uploader: @{uploader_name}",
                        )
                        if sent_doc.document:
                            final_file_id = sent_doc.document.file_id

                    # Clean up temp files
                    for p in (temp_in, temp_out):
                        if p.exists():
                            try:
                                p.unlink()
                            except Exception:
                                pass
            except Exception as wm_err:
                logger.error(f"Watermarking error during upload: {wm_err}", exc_info=True)
                final_file_id = file_id

        # Case A: Admin Flow (Direct DB save + Optional Broadcast)
        if doc_is_admin:
            async with get_session() as session:
                await crud.create_study_material(
                    session=session,
                    title=file_name.replace(".pdf", "").replace("_", " "),
                    exam_category=category_enum,
                    subject=subj,
                    material_type=MaterialType.SHORT_NOTES,
                    file_path=file_name,
                    year=datetime.now().year,
                    telegram_file_id=final_file_id,
                )

            if step == "bcast":
                bot_info = await bot.get_me()
                bot_username = bot_info.username or "StudyBot"

                channel_caption = (
                    f"📚 <b>{settings.brand_name} | नवीन अभ्यास साहित्य</b>\n\n"
                    f"📌 <b>{file_name.replace('.pdf', '').replace('_', ' ')}</b>\n\n"
                    f"📖 <b>विषय:</b> {subj}\n"
                    f"🏛️ <b>प्रवर्ग:</b> #{category_enum.value}\n\n"
                    f"🏷️ <i>{settings.brand_tagline}</i>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"🤖 बॉट वरून सर्व मोफत साहित्य मिळवण्यासाठी: @{bot_username}\n"
                    f"📢 मुख्य चॅनेल: {settings.brand_channel}"
                )

                try:
                    await bot.send_document(
                        chat_id=settings.main_channel_id,
                        document=final_file_id,
                        caption=channel_caption,
                    )
                    await callback.message.edit_text(
                        f"✅ <b>यशस्वी!</b>\n\n<b>'{settings.brand_name}'</b> वॉटरमार्कसह साहित्य जतन केले आणि <b>{settings.brand_channel}</b> वर प्रसारित केले!"
                    )
                except Exception as e:
                    logger.error(f"Broadcast error: {e}")
                    await callback.message.edit_text(
                        f"✅ <b>डेटाबेसमध्ये जतन केले!</b>\n(प्रसारण करताना त्रुटी: {e})"
                    )
            else:
                await callback.message.edit_text(
                    f"✅ <b>यशस्वी!</b>\n\n<b>'{settings.brand_name}'</b> वॉटरमार्कसह साहित्य बॉटच्या लायब्ररीत जतन केले. विद्यार्थी आता `/search` आणि मेन्यूद्वारे हे डाऊनलोड करू शकतात."
                )

        # Case B: Student Community Contribution Flow (Queue in Staging for Approval)
        else:
            async with get_session() as session:
                await crud.create_staging_item(
                    session=session,
                    title=file_name.replace(".pdf", "").replace("_", " "),
                    source_url=f"Telegram User: @{uploader_name}",
                    pdf_url=final_file_id,
                    extracted_summary=f"👤 विद्यार्थी योगदान (Contributed by: @{uploader_name})\nविषय: {subj} | प्रवर्ग: {category_enum.value}",
                    exam_category=category_enum,
                    subject=subj,
                    material_type=MaterialType.SHORT_NOTES,
                    year=datetime.now().year,
                )

            await callback.message.edit_text(
                f"✅ <b>धन्यवाद विद्यार्थी मित्रांनो! 🙏</b>\n\n"
                f"📄 <b>{file_name}</b> हे साहित्य तपासणीसाठी प्रशासकांकडे पाठवले आहे. "
                f"मंजुरीनंतर ते <b>{settings.brand_name}</b> च्या मुख्य चॅनेलवर प्रकाशित केले जाईल!"
            )

        await callback.answer("यशस्वीरित्या प्रक्रिया पूर्ण!")
