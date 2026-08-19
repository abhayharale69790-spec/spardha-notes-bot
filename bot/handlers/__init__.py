"""Telegram Bot handlers package."""
from bot.handlers.start import start_router
from bot.handlers.categories import categories_router
from bot.handlers.search import search_router
from bot.handlers.admin_staging import admin_staging_router

__all__ = [
    "start_router",
    "categories_router",
    "search_router",
    "admin_staging_router",
]
