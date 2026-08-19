"""Authentication and Admin Authorization Middleware and Filters."""

from typing import Any, Awaitable, Callable, Dict, Union
from aiogram import BaseMiddleware
from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message, TelegramObject
from config.settings import get_settings

settings = get_settings()


class IsAdminFilter(Filter):
    """Filter to restrict command/callback execution exclusively to authorized admins."""

    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        user_id = event.from_user.id if event.from_user else None
        if not user_id:
            return False
        return settings.is_admin(user_id)


class AdminAuthMiddleware(BaseMiddleware):
    """Middleware for defense-in-depth validation on administrative routers."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id = None
        if isinstance(event, (Message, CallbackQuery)) and event.from_user:
            user_id = event.from_user.id

        if not user_id or not settings.is_admin(user_id):
            if isinstance(event, CallbackQuery):
                await event.answer("⛔ प्रशासकीय अधिकार आवश्यक आहेत (Admin access required).", show_alert=True)
            elif isinstance(event, Message):
                await event.answer("⛔ आपल्याकडे या कृतीसाठी प्रशासकीय अधिकार नाहीत.")
            return None

        return await handler(event, data)
