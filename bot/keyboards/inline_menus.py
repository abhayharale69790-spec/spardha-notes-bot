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


# Human-friendly labels
CATEGORY_LABELS = {
    ExamCategory.MPSC.value: "🏛️ MPSC (Rajyaseva / Combine)",
    ExamCategory.POLICE_BHARTI.value: "👮 Police Bharti (पोलीस भरती)",
    ExamCategory.BANKING.value: "🏦 Banking (IBPS / SBI / RBI)",
    ExamCategory.SARAL_SEVA.value: "📑 Saral Seva (Talathi / ZP / Nagar Parishad)",
    ExamCategory.GENERAL.value: "🌐 General / All Exams",
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
            text="📚 Exam Wise Material (परीक्षानिहाय अभ्यास साहित्य)",
            callback_data=CategoryNavCallback(action=NavAction.EXAMS.value).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📑 Latest Govt Resolutions (शासन निर्णय / GR)",
            callback_data=CategoryNavCallback(action=NavAction.GR_FEED.value).pack(),
        ),
        InlineKeyboardButton(
            text="📝 Previous Year Papers (PYQ)",
            callback_data=CategoryNavCallback(action=NavAction.PYQ_FEED.value).pack(),
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="📰 Daily Current Affairs (चालू घडामोडी)",
            callback_data=CategoryNavCallback(action=NavAction.CA_FEED.value).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔍 Search Material (शोध घ्या)",
            switch_inline_query_current_chat="",
        )
    )
    return builder.as_markup()


def get_categories_keyboard() -> InlineKeyboardMarkup:
    """Build list of competitive exam categories."""
    builder = InlineKeyboardBuilder()

    for cat_enum in ExamCategory:
        label = CATEGORY_LABELS.get(cat_enum.value, cat_enum.value)
        builder.row(
            InlineKeyboardButton(
                text=label,
                callback_data=CategoryNavCallback(
                    action=NavAction.SELECT_CAT.value,
                    category=cat_enum.value,
                ).pack(),
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="🔙 Back to Main Menu",
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
