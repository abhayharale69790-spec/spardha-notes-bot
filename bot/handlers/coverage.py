"""Telegram Bot Handlers for Syllabus-Driven Content Coverage (/coverage).

Provides interactive navigation:
- Overview of all 10 exams with visual progress bars.
- 1-tap drilldown into Subject and Topic matrices.
- Clear indicators for Missing Topics, Weak Topics, and missing Material Types.
- 1-tap autonomous gap remediation trigger.
"""

import logging
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.models import ExamCategory
from services.coverage_engine import coverage_engine
from services.coverage_report import (
    format_telegram_exam_drilldown_card,
    format_telegram_overview_card,
)
from services.gap_detector import gap_detector

logger = logging.getLogger(__name__)
coverage_router = Router()


def build_overview_keyboard() -> InlineKeyboardMarkup:
    """Build interactive keyboard listing all 10 exam categories."""
    buttons = [
        [
            InlineKeyboardButton(text="🏛️ MPSC", callback_data="cov_exam:MPSC"),
            InlineKeyboardButton(text="👮 Police Bharti", callback_data="cov_exam:POLICE_BHARTI"),
        ],
        [
            InlineKeyboardButton(text="📑 Saral Seva", callback_data="cov_exam:SARAL_SEVA"),
            InlineKeyboardButton(text="🔬 NCERT", callback_data="cov_exam:NCERT"),
        ],
        [
            InlineKeyboardButton(text="🏫 10th/12th Board", callback_data="cov_exam:BOARD_10_12"),
            InlineKeyboardButton(text="⚙️ JEE", callback_data="cov_exam:JEE"),
        ],
        [
            InlineKeyboardButton(text="🩺 NEET", callback_data="cov_exam:NEET"),
            InlineKeyboardButton(text="🇮🇳 UPSC", callback_data="cov_exam:UPSC"),
        ],
        [
            InlineKeyboardButton(text="🏦 Banking", callback_data="cov_exam:BANKING"),
            InlineKeyboardButton(text="🏢 SSC", callback_data="cov_exam:SSC"),
        ],
        [
            InlineKeyboardButton(text="🔄 Refresh Coverage", callback_data="cov_refresh"),
            InlineKeyboardButton(text="⚡ Auto-Remediate Gaps", callback_data="cov_remediate"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_exam_drilldown_keyboard(exam_category: str) -> InlineKeyboardMarkup:
    """Build keyboard for exam drilldown view."""
    buttons = [
        [
            InlineKeyboardButton(text="⚡ Remediate Exam Gaps", callback_data="cov_remediate"),
        ],
        [
            InlineKeyboardButton(text="🔙 Back to All Exams", callback_data="cov_overview"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@coverage_router.message(Command("coverage"))
async def handle_coverage_command(message: Message):
    """Handle /coverage command by generating live syllabus coverage matrix."""
    try:
        matrix = await coverage_engine.compute_coverage_matrix()
        text = format_telegram_overview_card(matrix)
        keyboard = build_overview_keyboard()
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error generating coverage report: {e}")
        await message.answer("❌ कव्हरेज अहवाल तयार करताना त्रुटी आली. कृपया पुन्हा प्रयत्न करा.")


@coverage_router.callback_query(F.data == "cov_overview")
@coverage_router.callback_query(F.data == "cov_refresh")
async def handle_coverage_overview_callback(query: CallbackQuery):
    """Handle refresh and back to overview callbacks."""
    try:
        matrix = await coverage_engine.compute_coverage_matrix()
        text = format_telegram_overview_card(matrix)
        keyboard = build_overview_keyboard()
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await query.answer("✅ Coverage Matrix Refreshed!")
    except Exception as e:
        logger.error(f"Error refreshing coverage overview: {e}")
        await query.answer("❌ Refresh failed", show_alert=True)


@coverage_router.callback_query(F.data.startswith("cov_exam:"))
async def handle_coverage_exam_drilldown_callback(query: CallbackQuery):
    """Handle specific exam category drilldown callback."""
    try:
        cat_str = query.data.split(":")[1]
        exam_cat = ExamCategory(cat_str)
        em = await coverage_engine.get_exam_coverage(exam_cat)

        if not em:
            await query.answer("❌ Exam metrics not found.", show_alert=True)
            return

        text = format_telegram_exam_drilldown_card(em)
        keyboard = build_exam_drilldown_keyboard(cat_str)
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await query.answer(f"Loaded {em.display_name}")
    except Exception as e:
        logger.error(f"Error rendering exam drilldown: {e}")
        await query.answer("❌ Failed loading exam drilldown", show_alert=True)


@coverage_router.callback_query(F.data == "cov_remediate")
async def handle_coverage_remediation_callback(query: CallbackQuery):
    """Trigger autonomous gap remediation loop directly from Telegram."""
    try:
        await query.answer("⚡ Starting Autonomous Gap Remediation Cycle in background...")
        res = await gap_detector.run_autonomous_remediation_cycle(max_remediations=10)
        matrix = res.get("matrix") or await coverage_engine.compute_coverage_matrix()
        text = (
            f"⚡ <b>Autonomous Gap Remediation Completed!</b>\n\n"
            f"🎯 <b>Gaps Remediated:</b> <code>{res['remediations_completed']}</code>\n"
            f"📈 <b>Coverage Improvement:</b> <code>{res['initial_coverage_pct']}% ➔ {res['final_coverage_pct']}%</code>\n\n"
            + format_telegram_overview_card(matrix)
        )
        keyboard = build_overview_keyboard()
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error during gap remediation: {e}")
        await query.answer(f"❌ Remediation Error: {str(e)[:40]}", show_alert=True)
