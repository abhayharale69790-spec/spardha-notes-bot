"""Rate-Limited Asynchronous Broadcasting Worker (Leaky Bucket Queue)."""

import asyncio
from dataclasses import dataclass
import logging
import time
from typing import Optional, Union
from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup, Message, FSInputFile, URLInputFile
from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class BroadcastJob:
    """Encapsulates a message or document payload scheduled for broadcast."""
    chat_id: Union[int, str]
    document: Optional[Union[str, FSInputFile, URLInputFile]] = None
    text: Optional[str] = None
    caption: Optional[str] = None
    reply_markup: Optional[InlineKeyboardMarkup] = None
    future: Optional[asyncio.Future] = None


class BroadcastQueue:
    """Thread-safe and async-safe broadcast dispatcher with flood protection."""

    def __init__(self, bot: Bot, max_rate: float = 20.0) -> None:
        self.bot = bot
        self.max_rate = max_rate  # Maximum dispatches per second (Telegram allows ~30)
        self.interval = 1.0 / max_rate if max_rate > 0 else 0.05
        self.queue: asyncio.Queue[BroadcastJob] = asyncio.Queue()
        self._last_send_time = 0.0

    async def enqueue(self, job: BroadcastJob) -> asyncio.Future:
        """Enqueue a broadcast job and return an awaitable Future for the resulting Message."""
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        job.future = future
        await self.queue.put(job)
        return future

    async def run_worker(self, stop_event: asyncio.Event) -> None:
        """Continuously process queued broadcast jobs respecting rate limits."""
        logger.info(f"Broadcast queue worker started (Rate limit: {self.max_rate} msg/s).")

        while not stop_event.is_set():
            try:
                # Wait for next job with timeout to check stop_event
                try:
                    job = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                # Enforce interval spacing
                now = time.monotonic()
                time_since_last = now - self._last_send_time
                if time_since_last < self.interval:
                    await asyncio.sleep(self.interval - time_since_last)

                # Send message or document with retry logic
                sent_msg = await self._send_job(job)
                self._last_send_time = time.monotonic()

                if job.future and not job.future.done():
                    if sent_msg:
                        job.future.set_result(sent_msg)
                    else:
                        job.future.set_exception(RuntimeError("Broadcast dispatch failed"))

                self.queue.task_done()

            except Exception as e:
                logger.error(f"Error in broadcast queue worker loop: {e}", exc_info=True)

        logger.info("Broadcast queue worker stopped.")

    async def _send_job(self, job: BroadcastJob) -> Optional[Message]:
        """Dispatch a single broadcast job with Telegram flood control handling."""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                if job.document is not None:
                    # Send document
                    return await self.bot.send_document(
                        chat_id=job.chat_id,
                        document=job.document,
                        caption=job.caption,
                        reply_markup=job.reply_markup,
                    )
                elif job.text:
                    # Send text message
                    return await self.bot.send_message(
                        chat_id=job.chat_id,
                        text=job.text,
                        reply_markup=job.reply_markup,
                        disable_web_page_preview=False,
                    )
                else:
                    logger.warning("Empty broadcast job received (no document or text).")
                    return None

            except TelegramRetryAfter as flood:
                wait_sec = flood.retry_after
                logger.warning(f"[Broadcast Worker] Flood limit reached. Sleeping {wait_sec}s...")
                await asyncio.sleep(wait_sec + 0.5)
            except Exception as e:
                logger.error(f"[Broadcast Worker] Dispatch attempt {attempt + 1} failed: {e}")
                if attempt == max_attempts - 1:
                    return None
                await asyncio.sleep(1.0)

        return None
