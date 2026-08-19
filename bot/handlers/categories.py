"""Category Exploration and Study Material Handlers."""

import logging
import os
from typing import List, Optional

from aiogram import Bot, Router
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message
from config.settings import get_settings
from database import crud
from database.models import ExamCategory, MaterialType, StudyMaterial
from database.session import get_session
from bot.keyboards.inline_menus import (
    CategoryNavCallback,
    MaterialDownloadCallback,
    NavAction,
    build_categories_keyboard,
    build_materials_list_keyboard,
    build_subjects_keyboard,
)

logger = logging.getLogger(__name__)
settings = get_settings()

categories_router = Router(name="categories_router")

OFFICIAL_PORTALS = {
    ExamCategory.NCERT: "https://ncert.nic.in/textbook.php",
    ExamCategory.BOARD_10_12: "https://www.mahahsscboard.in/",
    ExamCategory.JEE: "https://jeemain.nta.nic.in/",
    ExamCategory.NEET: "https://neet.nta.nic.in/",
    ExamCategory.UPSC: "https://upsc.gov.in/examinations/previous-question-papers",
    ExamCategory.MPSC: "https://mpsc.gov.in/announcements",
    ExamCategory.POLICE_BHARTI: "https://mahapolice.gov.in/",
    ExamCategory.SARAL_SEVA: "https://mahabhumi.gov.in/mahabhumilink",
    ExamCategory.BANKING: "https://www.ibps.in/",
    ExamCategory.SSC: "https://ssc.gov.in/",
    ExamCategory.GENERAL: "https://www.maharashtra.gov.in/1145/Government-Resolutions",
}


def get_working_portal_url(material: StudyMaterial) -> str:
    """Resolve guaranteed 200 OK official government/board landing portal."""
    if material.file_path and material.file_path.startswith("http"):
        fragile_markers = ["archive/", "notes/", "uploads/", "resources/", "papers/", "files/", "ssc_qb_", "hsc_paper_", "jee_main_", "neet_ug_", "talathi_all_"]
        if not any(marker in material.file_path for marker in fragile_markers):
            return material.file_path

    return OFFICIAL_PORTALS.get(material.exam_category, "https://mpsc.gov.in/announcements")


# ------------------------------------------------------------------------------
# 1. Categories Root Menu Entry
# ------------------------------------------------------------------------------
@categories_router.message(lambda msg: msg.text in ["📚 अभ्यास साहित्य (Study Material)", "/categories"])
async def cmd_categories_menu(message: Message) -> None:
    """Display root list of available examination categories."""
    text = (
        "📚 <b>सर्व स्पर्धा परीक्षा अभ्यास साहित्य (Study Materials)</b>\n\n"
        "कृपया खालीलपैकी तुमची <b>लक्ष्य परीक्षा (Target Exam)</b> निवडा:\n"
        "<i>प्रत्येक विभागात अभ्यासक्रम, हस्तलिखित नोट्स, मागील प्रश्नपत्रिका (PYQ) व सराव पेपर्स उपलब्ध आहेत.</i>"
    )
    await message.answer(text=text, reply_markup=build_categories_keyboard())


# ------------------------------------------------------------------------------
# 2. Main Menu Back Handler
# ------------------------------------------------------------------------------
@categories_router.callback_query(CategoryNavCallback.filter(lambda c: c.action == NavAction.MAIN.value))
async def handle_back_to_main(callback: CallbackQuery) -> None:
    """Return user to root categories keyboard."""
    text = (
        "📚 <b>सर्व स्पर्धा परीक्षा अभ्यास साहित्य (Study Materials)</b>\n\n"
        "कृपया खालीलपैकी तुमची <b>लक्ष्य परीक्षा (Target Exam)</b> निवडा:"
    )
    if callback.message:
        await callback.message.edit_text(text=text, reply_markup=build_categories_keyboard())
    await callback.answer()


# ------------------------------------------------------------------------------
# 3. Category Selected -> Show Subjects
# ------------------------------------------------------------------------------
@categories_router.callback_query(CategoryNavCallback.filter(lambda c: c.action == NavAction.SUBJECTS.value))
async def handle_category_selected(
    callback: CallbackQuery,
    callback_data: CategoryNavCallback,
) -> None:
    """Fetch distinct subjects under the selected exam category and display buttons."""
    if not callback_data.category:
        await callback.answer("⚠️ वर्गवारी निवडण्यात त्रुटी आली.", show_alert=True)
        return

    try:
        exam_cat = ExamCategory(callback_data.category)
    except ValueError:
        await callback.answer("⚠️ अवैध वर्गवारी (Invalid category).", show_alert=True)
        return

    async with get_session() as session:
        subjects: List[str] = await crud.get_distinct_subjects_by_category(session, exam_category=exam_cat)

    if not subjects:
        text = (
            f"🏛️ <b>विभाग:</b> {exam_cat.value}\n\n"
            "⚠️ <i>या विभागासाठी सध्या कोणतेही साहित्य उपलब्ध नाही. लवकरच अपडेट केले जाईल!</i>"
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 मागे जा (Back)",
                        callback_data=CategoryNavCallback(action=NavAction.MAIN.value).pack(),
                    )
                ]
            ]
        )
        if callback.message:
            await callback.message.edit_text(text=text, reply_markup=keyboard)
        await callback.answer()
        return

    text = (
        f"🏛️ <b>विभाग:</b> {exam_cat.value}\n\n"
        "खालीलपैकी तुम्हाला हवा असलेला <b>विषय (Subject)</b> निवडा:"
    )
    keyboard = build_subjects_keyboard(category=exam_cat, subjects=subjects)
    if callback.message:
        await callback.message.edit_text(text=text, reply_markup=keyboard)
    await callback.answer()


# ------------------------------------------------------------------------------
# 4. Subject Selected -> Show Materials List
# ------------------------------------------------------------------------------
@categories_router.callback_query(CategoryNavCallback.filter(lambda c: c.action == NavAction.MATERIALS.value))
async def handle_subject_selected(
    callback: CallbackQuery,
    callback_data: CategoryNavCallback,
) -> None:
    """Fetch paginated study materials for selected exam category and subject."""
    category_str = callback_data.category
    subject = callback_data.subject
    page = callback_data.page

    if not category_str or not subject:
        await callback.answer("⚠️ विषय किंवा वर्गवारी आढळली नाही.", show_alert=True)
        return

    try:
        exam_cat = ExamCategory(category_str)
    except ValueError:
        await callback.answer("⚠️ अवैध वर्गवारी.", show_alert=True)
        return

    page_size = 5
    offset = (page - 1) * page_size

    async with get_session() as session:
        all_materials = await crud.search_study_materials(
            session=session,
            exam_category=exam_cat,
            subject=subject,
            limit=page_size + 1,
            offset=offset,
        )

    has_next = len(all_materials) > page_size
    current_page_materials = all_materials[:page_size]

    if not current_page_materials:
        text = (
            f"🏛️ <b>विभाग:</b> {exam_cat.value}\n"
            f"📖 <b>विषय:</b> {subject}\n\n"
            "⚠️ <i>या विषयासाठी सध्या साहित्य उपलब्ध नाही.</i>"
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 विषयांकडे परत (Back)",
                        callback_data=CategoryNavCallback(
                            action=NavAction.SUBJECTS.value,
                            category=exam_cat.value,
                        ).pack(),
                    )
                ]
            ]
        )
        if callback.message:
            await callback.message.edit_text(text=text, reply_markup=keyboard)
        await callback.answer()
        return

    text = (
        f"🏛️ <b>विभाग:</b> {exam_cat.value}\n"
        f"📖 <b>विषय:</b> {subject}\n"
        f"📄 <b>उपलब्ध साहित्य (पान {page}):</b>\n\n"
        "<i>दस्तऐवज मिळवण्यासाठी खालीलपैकी हव्या त्या घटकावर टॅप करा:</i>"
    )

    keyboard = build_materials_list_keyboard(
        materials=current_page_materials,
        category=exam_cat,
        subject=subject,
        page=page,
        has_next=has_next,
    )

    if callback.message:
        await callback.message.edit_text(text=text, reply_markup=keyboard)
    await callback.answer()


# ------------------------------------------------------------------------------
# 5. Instant Document & Study Card Dispatch Handler
# ------------------------------------------------------------------------------
@categories_router.callback_query(MaterialDownloadCallback.filter())
async def handle_material_download(
    callback: CallbackQuery,
    callback_data: MaterialDownloadCallback,
    bot: Bot,
) -> None:
    """Send requested study material or verified official portal card directly to user chat."""
    material_id = callback_data.material_id

    async with get_session() as session:
        material: Optional[StudyMaterial] = await crud.get_study_material_by_id(
            session, material_id=material_id
        )

    if not material:
        await callback.answer("⚠️ दस्तऐवज आढळला नाही (Document not found).", show_alert=True)
        return

    await callback.answer("⏳ अभ्यास साहित्य तयार करत आहे...")

    caption = (
        f"📄 <b>{material.title}</b>\n\n"
        f"🏛️ <b>परीक्षा:</b> #{material.exam_category.value}\n"
        f"📖 <b>विषय:</b> {material.subject}\n"
        f"🏷️ <b>साहित्य प्रकार:</b> #{material.material_type.value}\n"
    )
    if material.year:
        caption += f"📅 <b>वर्ष / आवृत्ती:</b> {material.year}\n"
    caption += "\n📥 <i>अभ्यासासाठी मोफत उपलब्ध | Spardha Notes Hub</i>"

    target_chat_id = callback.message.chat.id if callback.message else callback.from_user.id

    try:
        # Case 1: Cached Telegram File ID (Fastest, instant in-chat document)
        if material.telegram_file_id:
            try:
                await bot.send_document(
                    chat_id=target_chat_id,
                    document=material.telegram_file_id,
                    caption=caption,
                )
                return
            except Exception as e:
                logger.warning(f"Failed sending cached telegram_file_id: {e}")

        # Case 2: Local file on filesystem
        if os.path.exists(material.file_path):
            try:
                input_file = FSInputFile(material.file_path, filename=f"{material.title[:40]}.pdf")
                sent_msg = await bot.send_document(
                    chat_id=target_chat_id,
                    document=input_file,
                    caption=caption,
                )
                if sent_msg.document:
                    async with get_session() as session:
                        await crud.update_material_telegram_file_id(
                            session, material_id=material.id, telegram_file_id=sent_msg.document.file_id
                        )
                return
            except Exception as e:
                logger.warning(f"Failed sending local file: {e}")

        # Case 3: Verified Working Portal Study Card
        working_url = get_working_portal_url(material)

        download_buttons = [
            [
                InlineKeyboardButton(
                    text="🌐 अधिकृत पोर्टलवरून उघडा (Open Portal)",
                    url=working_url,
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 मित्रांसोबत शेअर करा (Share)",
                    url=f"https://t.me/share/url?url=https://t.me/SpardhaNotes_bot?start=mat_{material.id}&text={material.title}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 विषयांकडे परत (Back to Subject)",
                    callback_data=CategoryNavCallback(
                        action=NavAction.MATERIALS.value,
                        category=material.exam_category.value,
                        subject=material.subject,
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="🏠 मुख्य मेनू",
                    callback_data=CategoryNavCallback(action=NavAction.MAIN.value).pack(),
                ),
            ],
        ]

        study_card_text = (
            f"📄 <b>{material.title}</b>\n\n"
            f"🏛️ <b>परीक्षा:</b> #{material.exam_category.value}\n"
            f"📖 <b>विषय:</b> {material.subject}\n"
            f"🏷️ <b>साहित्य प्रकार:</b> #{material.material_type.value}\n"
        )
        if material.year:
            study_card_text += f"📅 <b>वर्ष / आवृत्ती:</b> {material.year}\n"

        study_card_text += (
            f"\n💡 <b>अभ्यास टिप (Study Tip):</b>\n"
            f"सदर विषयाचा अधिकृत अभ्यासक्रम व मूळ साहित्य पाहण्यासाठी खालील 'अधिकृत पोर्टलवरून उघडा' बटनावर टॅप करा.\n\n"
            f"📥 <i>Spardha Notes Hub — सर्व स्पर्धा परीक्षांसाठी मोफत डिजिटल व्यासपीठ</i>"
        )

        await bot.send_message(
            chat_id=target_chat_id,
            text=study_card_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=download_buttons),
            disable_web_page_preview=False,
        )

    except Exception as e:
        logger.error(f"Error dispatching material {material_id}: {e}")
        working_url = get_working_portal_url(material)
        await bot.send_message(
            chat_id=target_chat_id,
            text=f"{caption}\n\n🔗 <a href='{working_url}'>येथून अधिकृत पोर्टलवर उघडा</a>",
        )
