"""Test Telegram Bot /coverage command and callback queries."""

import asyncio
from datetime import datetime, timezone
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiogram import Bot
from config.settings import get_settings
from services.coverage_engine import coverage_engine
from services.coverage_report import (
    format_telegram_overview_card,
    format_telegram_exam_drilldown_card,
)
from bot.handlers.coverage import build_overview_keyboard, build_exam_drilldown_keyboard
from database.models import ExamCategory

settings = get_settings()


async def main():
    bot = Bot(token=settings.bot_token)
    staging_chat_id = settings.staging_channel_id or settings.main_channel_id or 8691719772

    print("=" * 80)
    print(" 🤖 TELEGRAM BOT /coverage INTERACTION TEST")
    print("=" * 80)

    # 1. Test Overview Card
    print("1️⃣ Testing /coverage Overview Card...")
    matrix = await coverage_engine.compute_coverage_matrix()
    overview_text = format_telegram_overview_card(matrix)
    overview_kb = build_overview_keyboard()

    msg1 = await bot.send_message(
        chat_id=staging_chat_id,
        text=overview_text,
        reply_markup=overview_kb,
        parse_mode="HTML",
    )
    print(f"   ✅ Overview Card Sent! Msg ID: {msg1.message_id}")

    await asyncio.sleep(2.0)

    # 2. Test Exam Drilldown Cards for MPSC and Police Bharti
    print("2️⃣ Testing Exam Drilldown Cards (MPSC & Police Bharti)...")
    for cat in (ExamCategory.MPSC, ExamCategory.POLICE_BHARTI):
        em = await coverage_engine.get_exam_coverage(cat)
        if em:
            drilldown_text = format_telegram_exam_drilldown_card(em)
            drilldown_kb = build_exam_drilldown_keyboard(cat.value)
            msg2 = await bot.send_message(
                chat_id=staging_chat_id,
                text=drilldown_text,
                reply_markup=drilldown_kb,
                parse_mode="HTML",
            )
            print(f"   ✅ {cat.value} Drilldown Card Sent! Msg ID: {msg2.message_id}")
            await asyncio.sleep(1.5)

    await bot.session.close()
    print("\n🎉 /coverage Telegram Bot Interaction Test Complete!")


if __name__ == "__main__":
    asyncio.run(main())
