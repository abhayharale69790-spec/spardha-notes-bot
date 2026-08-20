"""Dynamic Inline Keyboard Builders and Type-Safe Callback Data Factories."""

import enum
from typing import List, Optional, Sequence
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.models import ExamCategory, MaterialType, StudyMaterial


class NavAction(str, enum.Enum):
    """Actions used in navigation callbacks."""
    MAIN = "main"
    EXAMS = "exams"
    SELECT_CAT = "sel_cat"
    SELECT_SUBJ = "sel_subj"
    SELECT_YEAR = "sel_year"
    LIST_MATERIALS = "list_mat"
    GR_FEED = "gr_feed"
    PYQ_FEED = "pyq_feed"
    CA_FEED = "ca_feed"


class CategoryNavCallback(CallbackData, prefix="nav"):
    """Callback data for hierarchical drill-down navigation."""
    action: str
    category: Optional[str] = None
    subject: Optional[str] = None
    year: Optional[int] = None
    material_type: Optional[str] = None
    page: int = 1


class MaterialDownloadCallback(CallbackData, prefix="dl"):
    """Callback data for instant document download / dispatch."""
    material_id: int


class StagingApprovalCallback(CallbackData, prefix="stg"):
    """Callback data for admin staging approval workflow."""
    action: str  # "approve" or "discard"
    staging_id: int


# Human-friendly labels for all 10 major exam categories
CATEGORY_LABELS = {
    ExamCategory.UPSC.value: "🇮🇳 UPSC Civil Services (IAS / IPS)",
    ExamCategory.MPSC.value: "🏛️ MPSC (Rajyaseva / Combine)",
    ExamCategory.POLICE_BHARTI.value: "👮 Police Bharti (महाराष्ट्र पोलीस भरती)",
    ExamCategory.SARAL_SEVA.value: "📑 Saral Seva (तलाठी / ZP / नगर परिषद)",
    ExamCategory.JEE.value: "⚡ JEE Main & Advanced (Engineering)",
    ExamCategory.NEET.value: "🩺 NEET UG (Medical / MBBS)",
    ExamCategory.BOARD_10_12.value: "🏫 10th & 12th Board (SSC / HSC)",
    ExamCategory.NCERT.value: "📖 NCERT Textbooks (Class 6 - 12)",
    ExamCategory.BANKING.value: "🏦 Banking (IBPS / SBI / RBI)",
    ExamCategory.SSC.value: "🎯 SSC (CGL / CHSL / GD / MTS)",
    ExamCategory.GENERAL.value: "🌐 General / शासन निर्णय (GR)",
}

MATERIAL_TYPE_LABELS = {
    MaterialType.GR.value: "📑 शासन निर्णय (Govt Resolution)",
    MaterialType.PYQ.value: "📝 प्रश्नपत्रिका (PYQ)",
    MaterialType.SHORT_NOTES.value: "📌 शॉर्ट नोट्स (Revision Notes)",
    MaterialType.SYLLABUS.value: "📋 अभ्यासक्रम (Syllabus)",
    MaterialType.TEST_PAPER.value: "🎯 सराव पेपर (Mock Test)",
    MaterialType.CURRENT_AFFAIRS.value: "📰 चालू घडामोडी (Current Affairs)",
}


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Build root navigation menu for student aspirants."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="📚 All Exams & Material (परीक्षानिहाय अभ्यास साहित्य)",
            callback_data=CategoryNavCallback(action=NavAction.EXAMS.value).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📑 Latest GRs (शासन निर्णय)",
            callback_data=CategoryNavCallback(action=NavAction.GR_FEED.value).pack(),
        ),
        InlineKeyboardButton(
            text="📝 Question Papers (PYQ)",
            callback_data=CategoryNavCallback(action=NavAction.PYQ_FEED.value).pack(),
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="📰 Daily Current Affairs (चालू घडामोडी)",
            callback_data=CategoryNavCallback(action=NavAction.CA_FEED.value).pack(),
        ),
        InlineKeyboardButton(
            text="📊 Syllabus Coverage (कव्हरेज)",
            callback_data="cov_overview",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="🔍 Search Material (शोध घ्या)",
            switch_inline_query_current_chat="",
        )
    )
    return builder.as_markup()



def get_categories_keyboard() -> InlineKeyboardMarkup:
    """Build list of competitive & academic exam categories grouped logically."""
    builder = InlineKeyboardBuilder()

    # 1. Civil Services & State
    builder.row(
        InlineKeyboardButton(
            text="🇮🇳 UPSC Civil Services",
            callback_data=CategoryNavCallback(
                action=NavAction.SELECT_CAT.value,
                category=ExamCategory.UPSC.value,
            ).pack(),
        ),
        InlineKeyboardButton(
            text="🏛️ MPSC (Rajyaseva)",
            callback_data=CategoryNavCallback(
                action=NavAction.SELECT_CAT.value,
                category=ExamCategory.MPSC.value,
            ).pack(),
        ),
    )

    # 2. State Recruitment
    builder.row(
        InlineKeyboardButton(
            text="👮 पोलीस भरती (Police)",
            callback_data=CategoryNavCallback(
                action=NavAction.SELECT_CAT.value,
                category=ExamCategory.POLICE_BHARTI.value,
            ).pack(),
        ),
        InlineKeyboardButton(
            text="📑 सरळ सेवा (Talathi/ZP)",
            callback_data=CategoryNavCallback(
                action=NavAction.SELECT_CAT.value,
                category=ExamCategory.SARAL_SEVA.value,
            ).pack(),
        ),
    )

    # 3. National Engineering & Medical
    builder.row(
        InlineKeyboardButton(
            text="⚡ JEE Main & Advanced",
            callback_data=CategoryNavCallback(
                action=NavAction.SELECT_CAT.value,
                category=ExamCategory.JEE.value,
            ).pack(),
        ),
        InlineKeyboardButton(
            text="🩺 NEET UG (Medical)",
            callback_data=CategoryNavCallback(
                action=NavAction.SELECT_CAT.value,
                category=ExamCategory.NEET.value,
            ).pack(),
        ),
    )

    # 4. School & NCERT Foundation
    builder.row(
        InlineKeyboardButton(
            text="🏫 10th & 12th Board",
            callback_data=CategoryNavCallback(
                action=NavAction.SELECT_CAT.value,
                category=ExamCategory.BOARD_10_12.value,
            ).pack(),
        ),
        InlineKeyboardButton(
            text="📖 NCERT (6th to 12th)",
            callback_data=CategoryNavCallback(
                action=NavAction.SELECT_CAT.value,
                category=ExamCategory.NCERT.value,
            ).pack(),
        ),
    )

    # 5. Banking & SSC
    builder.row(
        InlineKeyboardButton(
            text="🏦 Banking (IBPS/SBI)",
            callback_data=CategoryNavCallback(
                action=NavAction.SELECT_CAT.value,
                category=ExamCategory.BANKING.value,
            ).pack(),
        ),
        InlineKeyboardButton(
            text="🎯 SSC (CGL/CHSL)",
            callback_data=CategoryNavCallback(
                action=NavAction.SELECT_CAT.value,
                category=ExamCategory.SSC.value,
            ).pack(),
        ),
    )

    # 6. General / GR
    builder.row(
        InlineKeyboardButton(
            text="🌐 शासन निर्णय (GR) व General Studies",
            callback_data=CategoryNavCallback(
                action=NavAction.SELECT_CAT.value,
                category=ExamCategory.GENERAL.value,
            ).pack(),
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="🔙 मुख्य मेनू (Back to Main Menu)",
            callback_data=CategoryNavCallback(action=NavAction.MAIN.value).pack(),
        )
    )
    return builder.as_markup()


def get_subjects_keyboard(category: str, subjects: List[str]) -> InlineKeyboardMarkup:
    """Build subject selection menu for chosen exam category."""
    builder = InlineKeyboardBuilder()

    if subjects:
        for subj in subjects:
            builder.row(
                InlineKeyboardButton(
                    text=f"📖 {subj}",
                    callback_data=CategoryNavCallback(
                        action=NavAction.SELECT_SUBJ.value,
                        category=category,
                        subject=subj,
                    ).pack(),
                )
            )
    else:
        builder.row(
            InlineKeyboardButton(
                text="📂 View All Material in this Category",
                callback_data=CategoryNavCallback(
                    action=NavAction.LIST_MATERIALS.value,
                    category=category,
                ).pack(),
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="🔙 Back to Exams",
            callback_data=CategoryNavCallback(action=NavAction.EXAMS.value).pack(),
        ),
        InlineKeyboardButton(
            text="🏠 Home",
            callback_data=CategoryNavCallback(action=NavAction.MAIN.value).pack(),
        ),
    )
    return builder.as_markup()


def get_years_or_materials_keyboard(
    category: str,
    subject: str,
    years: List[int],
) -> InlineKeyboardMarkup:
    """Build year filter or all-materials selection menu."""
    builder = InlineKeyboardBuilder()

    # Show Years buttons in pairs
    year_buttons = []
    for yr in years:
        year_buttons.append(
            InlineKeyboardButton(
                text=f"📅 {yr}",
                callback_data=CategoryNavCallback(
                    action=NavAction.LIST_MATERIALS.value,
                    category=category,
                    subject=subject,
                    year=yr,
                ).pack(),
            )
        )

    for i in range(0, len(year_buttons), 2):
        builder.row(*year_buttons[i : i + 2])

    builder.row(
        InlineKeyboardButton(
            text="📂 View All Years / All Materials",
            callback_data=CategoryNavCallback(
                action=NavAction.LIST_MATERIALS.value,
                category=category,
                subject=subject,
            ).pack(),
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="🔙 Back to Subjects",
            callback_data=CategoryNavCallback(
                action=NavAction.SELECT_CAT.value,
                category=category,
            ).pack(),
        ),
        InlineKeyboardButton(
            text="🏠 Home",
            callback_data=CategoryNavCallback(action=NavAction.MAIN.value).pack(),
        ),
    )
    return builder.as_markup()


def get_materials_list_keyboard(
    materials: Sequence[StudyMaterial],
    category: Optional[str] = None,
    subject: Optional[str] = None,
    year: Optional[int] = None,
    material_type: Optional[str] = None,
    page: int = 1,
    has_next: bool = False,
) -> InlineKeyboardMarkup:
    """Build paginated list of study materials with direct download buttons."""
    builder = InlineKeyboardBuilder()

    for item in materials:
        type_prefix = {
            MaterialType.GR.value: "📑",
            MaterialType.PYQ.value: "📝",
            MaterialType.SHORT_NOTES.value: "📌",
            MaterialType.SYLLABUS.value: "📋",
            MaterialType.TEST_PAPER.value: "🎯",
            MaterialType.CURRENT_AFFAIRS.value: "📰",
        }.get(str(item.material_type.value if hasattr(item.material_type, "value") else item.material_type), "📄")

        year_suffix = f" ({item.year})" if item.year else ""
        btn_text = f"{type_prefix} {item.title[:42]}{year_suffix}"

        builder.row(
            InlineKeyboardButton(
                text=btn_text,
                callback_data=MaterialDownloadCallback(material_id=item.id).pack(),
            )
        )

    # Pagination controls
    nav_buttons = []
    if page > 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="⬅️ Prev",
                callback_data=CategoryNavCallback(
                    action=NavAction.LIST_MATERIALS.value,
                    category=category,
                    subject=subject,
                    year=year,
                    material_type=material_type,
                    page=page - 1,
                ).pack(),
            )
        )

    nav_buttons.append(
        InlineKeyboardButton(
            text=f"📄 Page {page}",
            callback_data="noop",
        )
    )

    if has_next:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Next ➡️",
                callback_data=CategoryNavCallback(
                    action=NavAction.LIST_MATERIALS.value,
                    category=category,
                    subject=subject,
                    year=year,
                    material_type=material_type,
                    page=page + 1,
                ).pack(),
            )
        )

    builder.row(*nav_buttons)

    # Contextual Back button
    back_action = NavAction.EXAMS.value
    if subject and category:
        back_action = NavAction.SELECT_CAT.value
    elif category:
        back_action = NavAction.EXAMS.value

    builder.row(
        InlineKeyboardButton(
            text="🔙 Back",
            callback_data=CategoryNavCallback(
                action=back_action,
                category=category,
            ).pack(),
        ),
        InlineKeyboardButton(
            text="🏠 Home",
            callback_data=CategoryNavCallback(action=NavAction.MAIN.value).pack(),
        ),
    )
    return builder.as_markup()


def get_staging_action_keyboard(staging_id: int) -> InlineKeyboardMarkup:
    """Build admin moderation inline buttons for Staging Channel."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Approve & Broadcast",
            callback_data=StagingApprovalCallback(
                action="approve",
                staging_id=staging_id,
            ).pack(),
        ),
        InlineKeyboardButton(
            text="❌ Discard",
            callback_data=StagingApprovalCallback(
                action="discard",
                staging_id=staging_id,
            ).pack(),
        ),
    )
    return builder.as_markup()


# Aliases for consistent naming across handlers
build_main_menu_keyboard = get_main_menu_keyboard
build_categories_keyboard = get_categories_keyboard
build_subjects_keyboard = get_subjects_keyboard
build_materials_list_keyboard = get_materials_list_keyboard
build_staging_action_keyboard = get_staging_action_keyboard

