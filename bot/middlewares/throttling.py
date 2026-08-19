"""Aiogram 3.x Rate-Limiting Throttling Middleware (Leaky-Bucket Algorithm)."""

import asyncio
from collections import defaultdict
import logging
import time
from typing import Any, Awaitable, Callable, Dict, Optional
from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import CallbackQuery, Message, TelegramObject
from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LeakyBucket:
    """In-memory Token/Leaky Bucket rate limiter per user."""

    def __init__(self, rate: float = 1.0, capacity: float = 3.0) -> None:
        self.rate = rate          # Tokens replenished per second
        self.capacity = capacity  # Maximum bucket capacity
        self.tokens = capacity
        self.last_update = time.monotonic()

    def consume(self, amount: float = 1.0) -> bool:
        """Attempt to consume tokens. Returns True if permitted, False if throttled."""
        now = time.monotonic()
        elapsed = now - self.last_update
        self.last_update = now

        # Replenish tokens based on elapsed time
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False


class ThrottlingMiddleware(BaseMiddleware):
    """Middleware enforcing per-user rate limiting and Telegram flood control."""

    def __init__(
        self,
        rate: float = 1.0,
        capacity: int = 3,
    ) -> None:
        self.rate = rate
        self.capacity = capacity
        self.buckets: Dict[int, LeakyBucket] = defaultdict(
            lambda: LeakyBucket(rate=self.rate, capacity=float(self.capacity))
        )
        self.warned_users: Dict[int, float] = defaultdict(float)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id: Optional[int] = None

        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        # Skip rate-limiting if user is not identifiable
        if not user_id:
            return await self._execute_with_retry_handler(handler, event, data)

        bucket = self.buckets[user_id]
        if not bucket.consume(1.0):
            # User exceeded rate limit
            now = time.monotonic()
            last_warned = self.warned_users[user_id]
            if now - last_warned > 3.0:  # Only warn once every 3 seconds to prevent reply spam
                self.warned_users[user_id] = now
                throttle_text = "⚠️ <b>खूप जलद विनंत्या (Rate Limit Exceeded)</b>\nकृपया २ सेकंद थांबा आणि पुन्हा प्रयत्न करा."
                if isinstance(event, Message):
                    await event.answer(throttle_text)
                elif isinstance(event, CallbackQuery):
                    await event.answer("⚠️ कृपया २ सेकंद थांबा...", show_alert=False)
            return None

        return await self._execute_with_retry_handler(handler, event, data)

    async def _execute_with_retry_handler(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Wrap execution to gracefully handle Telegram Flood Limits (HTTP 429)."""
        try:
            return await handler(event, data)
        except TelegramRetryAfter as flood_err:
            retry_after_sec = flood_err.retry_after
            logger.warning(f"Telegram Flood Control triggered. Must wait {retry_after_sec}s. Sleeping...")
            await asyncio.sleep(retry_after_sec)
            try:
                return await handler(event, data)
            except Exception as retry_err:
                logger.error(f"Failed retry after flood wait: {retry_err}")
                return None
        except Exception as e:
            logger.error(f"Unhandled error in Telegram handler pipeline: {e}", exc_info=True)
            raise
