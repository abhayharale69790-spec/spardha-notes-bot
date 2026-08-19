"""Keyboards package for dynamic Telegram inline menus."""
from bot.keyboards.inline_menus import (
    NavAction,
    CategoryNavCallback,
    MaterialDownloadCallback,
    StagingApprovalCallback,
    get_main_menu_keyboard,
    get_categories_keyboard,
    get_subjects_keyboard,
    get_years_or_materials_keyboard,
    get_materials_list_keyboard,
    get_staging_action_keyboard,
)

__all__ = [
    "NavAction",
    "CategoryNavCallback",
    "MaterialDownloadCallback",
    "StagingApprovalCallback",
    "get_main_menu_keyboard",
    "get_categories_keyboard",
    "get_subjects_keyboard",
    "get_years_or_materials_keyboard",
    "get_materials_list_keyboard",
    "get_staging_action_keyboard",
]
