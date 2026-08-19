"""Hierarchical Drill-Down Handlers (Exam -> Subject -> Year / Type -> Materials)."""

import os
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, FSInputFile, URLInputFile
from database.session import get_session
from database.models import ExamCategory, MaterialType, StudyMaterial
from database import crud
from bot.keyboards.inline_menus import (
    NavAction,
    CategoryNavCallback,
    MaterialDownloadCallback,
    CATEGORY_LABELS,
    MATERIAL_TYPE_LABELS,
    get_categories_keyboard,
    get_subjects_keyboard,
    get_years_or_materials_keyboard,
    get_materials_list_keyboard,
)

categories_router = Router(name="categories_router")
PAGE_SIZE = 8


# ------------------------------------------------------------------------------
# 1. Category Selection
# ------------------------------------------------------------------------------
@categories_router.callback_query(CategoryNavCallback.filter(F.action == NavAction.EXAMS.value))
async def handle_nav_exams_list(callback: CallbackQuery) -> None:
    """Show list of exam categories (MPSC, Police Bharti, Banking, etc.)."""
    text = "📚 <b>आपली परीक्षा निवडा (Select Your Exam):</b>\nकृपया खालीलपैकी एका परीक्षेची निवड करा:"
    if callback.message:
        await callback.message.edit_text(text=text, reply_markup=get_categories_keyboard())
    await callback.answer()


# ------------------------------------------------------------------------------
# 2. Subject Selection
# ------------------------------------------------------------------------------
@categories_router.callback_query(CategoryNavCallback.filter(F.action == NavAction.SELECT_CAT.value))
async def handle_nav_select_category(callback: CallbackQuery, callback_data: CategoryNavCallback) -> None:
    """Show subjects available for the selected exam category."""
    cat_val = callback_data.category or ExamCategory.GENERAL.value
    cat_label = CATEGORY_LABELS.get(cat_val, cat_val)

    async with get_session() as session:
        exam_enum = ExamCategory(cat_val) if cat_val in ExamCategory.__members__ else ExamCategory.GENERAL
        subjects = await crud.get_distinct_subjects_by_category(session, exam_category=exam_enum)

    text = f"📂 <b>{cat_label}</b>\n\n📖 <b>विषय निवडा (Select Subject):</b>"
    if callback.message:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_subjects_keyboard(category=cat_val, subjects=subjects),
        )
    await callback.answer()


# ------------------------------------------------------------------------------
# 3. Year / Filter Selection
# ------------------------------------------------------------------------------
@categories_router.callback_query(CategoryNavCallback.filter(F.action == NavAction.SELECT_SUBJ.value))
async def handle_nav_select_subject(callback: CallbackQuery, callback_data: CategoryNavCallback) -> None:
    """Show available years or all materials for the selected subject."""
    cat_val = callback_data.category or ExamCategory.GENERAL.value
    subj = callback_data.subject or "General"
    cat_label = CATEGORY_LABELS.get(cat_val, cat_val)

    async with get_session() as session:
        exam_enum = ExamCategory(cat_val) if cat_val in ExamCategory.__members__ else ExamCategory.GENERAL
        years = await crud.get_distinct_years_by_category_and_subject(
            session, exam_category=exam_enum, subject=subj
        )

    text = f"📂 <b>{cat_label}</b>\n📖 विषय: <b>{subj}</b>\n\n📅 <b>वर्ष निवडा किंवा सर्व साहित्य पहा:</b>"
    if callback.message:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_years_or_materials_keyboard(category=cat_val, subject=subj, years=years),
        )
    await callback.answer()


# ------------------------------------------------------------------------------
# 4. Paginated Materials List
# ------------------------------------------------------------------------------
@categories_router.callback_query(CategoryNavCallback.filter(F.action == NavAction.LIST_MATERIALS.value))
async def handle_nav_list_materials(callback: CallbackQuery, callback_data: CategoryNavCallback) -> None:
    """Display paginated list of study materials matching filters."""
    cat_val = callback_data.category
    subj = callback_data.subject
    yr = callback_data.year
    mat_type_val = callback_data.material_type
    page = max(1, callback_data.page)
    offset = (page - 1) * PAGE_SIZE

    exam_enum: Optional[ExamCategory] = None
    if cat_val and cat_val in ExamCategory.__members__:
        exam_enum = ExamCategory(cat_val)

    type_enum: Optional[MaterialType] = None
    if mat_type_val and mat_type_val in MaterialType.__members__:
        type_enum = MaterialType(mat_type_val)

    async with get_session() as session:
        # Fetch one extra to determine if there is a next page
        materials = await crud.search_study_materials(
            session=session,
            exam_category=exam_enum,
            subject=subj,
            material_type=type_enum,
            year=yr,
            limit=PAGE_SIZE + 1,
            offset=offset,
        )

    has_next = len(materials) > PAGE_SIZE
    items_to_show = materials[:PAGE_SIZE]

    # Build description header
    header_parts = []
    if cat_val:
        header_parts.append(f"🏛️ {CATEGORY_LABELS.get(cat_val, cat_val)}")
    if subj:
        header_parts.append(f"📖 {subj}")
    if yr:
        header_parts.append(f"📅 {yr}")
    if mat_type_val:
        header_parts.append(f"🏷️ {MATERIAL_TYPE_LABELS.get(mat_type_val, mat_type_val)}")

    filter_desc = " • ".join(header_parts) if header_parts else "सर्व साहित्य (All Material)"

    if not items_to_show:
        text = f"📂 <b>{filter_desc}</b>\n\n⚠️ या विभागासाठी सध्या कोणतेही साहित्य उपलब्ध नाही."
    else:
        text = (
            f"📂 <b>{filter_desc}</b>\n"
            f"<i>दस्तऐवज डाउनलोड करण्यासाठी खालील बटनावर टॅप करा:</i>"
        )

    if callback.message:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_materials_list_keyboard(
                materials=items_to_show,
                category=cat_val,
                subject=subj,
                year=yr,
                material_type=mat_type_val,
                page=page,
                has_next=has_next,
            ),
        )
    await callback.answer()


# ------------------------------------------------------------------------------
# 5. Direct Feed Handlers (GR, PYQ, Current Affairs)
# ------------------------------------------------------------------------------
@categories_router.callback_query(CategoryNavCallback.filter(F.action == NavAction.GR_FEED.value))
async def handle_nav_gr_feed(callback: CallbackQuery) -> None:
    """Direct shortcut to Government Resolutions (GR)."""
    async with get_session() as session:
        materials = await crud.get_materials_by_type_or_category(
            session=session,
            material_type=MaterialType.GR,
            limit=PAGE_SIZE + 1,
            offset=0,
        )
    has_next = len(materials) > PAGE_SIZE
    items = materials[:PAGE_SIZE]

    text = "📑 <b>महाराष्ट्र शासन निर्णय (Govt Resolutions / GR)</b>\n<i>नवीनतम अधिकृत शासन परिपत्रके:</i>"
    if callback.message:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_materials_list_keyboard(
                materials=items,
                material_type=MaterialType.GR.value,
                page=1,
                has_next=has_next,
            ),
        )
    await callback.answer()


@categories_router.callback_query(CategoryNavCallback.filter(F.action == NavAction.PYQ_FEED.value))
async def handle_nav_pyq_feed(callback: CallbackQuery) -> None:
    """Direct shortcut to Previous Year Question Papers (PYQ)."""
    async with get_session() as session:
        materials = await crud.get_materials_by_type_or_category(
            session=session,
            material_type=MaterialType.PYQ,
            limit=PAGE_SIZE + 1,
            offset=0,
        )
    has_next = len(materials) > PAGE_SIZE
    items = materials[:PAGE_SIZE]

    text = "📝 <b>मागील वर्षांच्या प्रश्नपत्रिका (Previous Year Question Papers)</b>\n<i>अधिकृत पेपर्स:</i>"
    if callback.message:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_materials_list_keyboard(
                materials=items,
                material_type=MaterialType.PYQ.value,
                page=1,
                has_next=has_next,
            ),
        )
    await callback.answer()


@categories_router.callback_query(CategoryNavCallback.filter(F.action == NavAction.CA_FEED.value))
async def handle_nav_ca_feed(callback: CallbackQuery) -> None:
    """Direct shortcut to Daily/Monthly Current Affairs."""
    async with get_session() as session:
        materials = await crud.get_materials_by_type_or_category(
            session=session,
            material_type=MaterialType.CURRENT_AFFAIRS,
            limit=PAGE_SIZE + 1,
            offset=0,
        )
    has_next = len(materials) > PAGE_SIZE
    items = materials[:PAGE_SIZE]

    text = "📰 <b>चालू घडामोडी (Current Affairs)</b>\n<i>दैनिक आणि मासिक महत्त्वाच्या चालू घडामोडी:</i>"
    if callback.message:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_materials_list_keyboard(
                materials=items,
                material_type=MaterialType.CURRENT_AFFAIRS.value,
                page=1,
                has_next=has_next,
            ),
        )
    await callback.answer()


# ------------------------------------------------------------------------------
# 6. Instant Document Dispatch Handler
# ------------------------------------------------------------------------------
@categories_router.callback_query(MaterialDownloadCallback.filter())
async def handle_material_download(
    callback: CallbackQuery,
    callback_data: MaterialDownloadCallback,
    bot: Bot,
) -> None:
    """Send requested study material directly to user chat."""
    material_id = callback_data.material_id

    async with get_session() as session:
        material: Optional[StudyMaterial] = await crud.get_study_material_by_id(
            session, material_id=material_id
        )

    if not material:
        await callback.answer("⚠️ दस्तऐवज आढळला नाही (Document not found).", show_alert=True)
        return

    await callback.answer("⏳ दस्तऐवज पाठवत आहे...")

    caption = (
        f"📄 <b>{material.title}</b>\n"
        f"🏛️ <b>परीक्षा:</b> {material.exam_category.value}\n"
        f"📖 <b>विषय:</b> {material.subject}\n"
        f"🏷️ <b>प्रकार:</b> {material.material_type.value}\n"
    )
    if material.year:
        caption += f"📅 <b>वर्ष:</b> {material.year}\n"
    caption += "\n📥 <i>अभ्यासासाठी मोफत उपलब्ध | Share with friends!</i>"

    target_chat_id = callback.message.chat.id if callback.message else callback.from_user.id

    try:
        # Case 1: Cached Telegram File ID (Fastest, zero bandwidth)
        if material.telegram_file_id:
            await bot.send_document(
                chat_id=target_chat_id,
                document=material.telegram_file_id,
                caption=caption,
            )
            return

        # Case 2: URL file
        if material.file_path.startswith("http://") or material.file_path.startswith("https://"):
            input_file = URLInputFile(material.file_path, filename=f"{material.title[:40]}.pdf")
            sent_msg = await bot.send_document(
                chat_id=target_chat_id,
                document=input_file,
                caption=caption,
            )
            # Cache file_id for future requests
            if sent_msg.document:
                async with get_session() as session:
                    await crud.update_material_telegram_file_id(
                        session, material_id=material.id, telegram_file_id=sent_msg.document.file_id
                    )
            return

        # Case 3: Local file
        if os.path.exists(material.file_path):
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

        # Fallback: Send link
        await bot.send_message(
            chat_id=target_chat_id,
            text=f"{caption}\n\n🔗 <a href='{material.file_path}'>येथून डाउनलोड करा (Download Link)</a>",
            disable_web_page_preview=False,
        )

    except Exception as e:
        await bot.send_message(
            chat_id=target_chat_id,
            text=f"⚠️ दस्तऐवज पाठवताना त्रुटी आली: {str(e)}\n🔗 <a href='{material.file_path}'>थेट लिंक वापरा</a>",
        )
