"""Aiogram 3.x Bot and Dispatcher Configuration with Throttling Middlewares."""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config.settings import get_settings
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.handlers.start import start_router
from bot.handlers.coverage import coverage_router
from bot.handlers.categories import categories_router
from bot.handlers.search import search_router
from bot.handlers.admin_staging import admin_staging_router
from bot.handlers.admin_upload import admin_upload_router
from bot.handlers.telegram_collector_admin import telegram_collector_admin_router




def create_bot(token: str) -> Bot:
    """Create configured aiogram Bot instance with HTML parse mode."""
    return Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    """Create and configure aiogram Dispatcher with registered middlewares and routers."""
    dp = Dispatcher()
    settings = get_settings()

    # Register anti-flood throttling middleware
    throttling_middleware = ThrottlingMiddleware(
        rate=settings.rate_limit_rate,
        capacity=settings.rate_limit_burst,
    )
    dp.message.middleware(throttling_middleware)
    dp.callback_query.middleware(throttling_middleware)

    # Include modular routers
    dp.include_router(start_router)
    dp.include_router(coverage_router)
    dp.include_router(categories_router)
    dp.include_router(search_router)
    dp.include_router(admin_staging_router)
    dp.include_router(admin_upload_router)
    dp.include_router(telegram_collector_admin_router)

    return dp




def setup_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    """Convenience initialization helper using application settings."""
    settings = get_settings()
    bot = create_bot(settings.bot_token)
    dp = create_dispatcher()
    return bot, dp
