"""Inline and Command-based Search Handlers for Fast Study Material Discovery."""

import hashlib
from typing import List
from aiogram import Router, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    Message,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from database.session import get_session
from database import crud
from bot.keyboards.inline_menus import (
    MaterialDownloadCallback,
    CATEGORY_LABELS,
    MATERIAL_TYPE_LABELS,
)

search_router = Router(name="search_router")


# ------------------------------------------------------------------------------
# 1. Text Command Search Handler: /search <keywords>
# ------------------------------------------------------------------------------
@search_router.message(Command("search"))
async def handle_search_command(message: Message, command: CommandObject) -> None:
    """Handle /search command with keyword query."""
    query = command.args

    if not query or not query.strip():
        guide_text = (
            "🔍 <b>अभ्यास साहित्य शोधा (Search Study Materials):</b>\n\n"
            "कसे शोधावे (How to search):\n"
            "• <code>/search Polity 2024</code>\n"
            "• <code>/search MPSC History</code>\n"
            "• <code>/search पोलीस भरती गणित</code>\n"
            "• <code>/search शासन निर्णय</code>\n\n"
            "💡 <i>किंवा थेट कोणत्याही चॅटमध्ये <code>@bot_username विषय</code> टाईप करून इनलाईन शोधा!</i>"
        )
        await message.answer(guide_text)
        return

    query_str = query.strip()

    async with get_session() as session:
        results = await crud.search_study_materials(session, query=query_str, limit=8)

    if not results:
        await message.answer(
            f"🔍 <b>'{query_str}'</b> साठी कोणतेही साहित्य आढळले नाही.\n"
            f"कृपया वेगळे शब्द वापरून पुन्हा प्रयत्न करा."
        )
        return

    # Build response message with interactive download buttons
    response_text = (
        f"🔍 <b>'{query_str}'</b> चे शोध परिणाम (Search Results):\n"
        f"<i>दस्तऐवज मिळवण्यासाठी खालील बटनावर टॅप करा:</i>"
    )

    buttons = []
    for item in results:
        type_str = item.material_type.value if hasattr(item.material_type, "value") else str(item.material_type)
        cat_str = item.exam_category.value if hasattr(item.exam_category, "value") else str(item.exam_category)
        btn_text = f"📄 {item.title[:38]} [{cat_str}]"
        buttons.append([
            InlineKeyboardButton(
                text=btn_text,
                callback_data=MaterialDownloadCallback(material_id=item.id).pack(),
            )
        ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(response_text, reply_markup=keyboard)


# ------------------------------------------------------------------------------
# 2. Telegram Inline Query Handler (@bot query)
# ------------------------------------------------------------------------------
@search_router.inline_query()
async def handle_inline_search(inline_query: InlineQuery, bot: Bot) -> None:
    """Handle instant inline search queries in any chat or group."""
    query = inline_query.query.strip()

    async with get_session() as session:
        results = await crud.search_study_materials(
            session=session,
            query=query if query else None,
            limit=15,
        )

    articles: List[InlineQueryResultArticle] = []

    for item in results:
        cat_str = item.exam_category.value if hasattr(item.exam_category, "value") else str(item.exam_category)
        type_str = item.material_type.value if hasattr(item.material_type, "value") else str(item.material_type)
        cat_label = CATEGORY_LABELS.get(cat_str, cat_str)
        type_label = MATERIAL_TYPE_LABELS.get(type_str, type_str)

        card_text = (
            f"📚 <b>{item.title}</b>\n"
            f"🏛️ <b>परीक्षा:</b> {cat_label}\n"
            f"📖 <b>विषय:</b> {item.subject}\n"
            f"🏷️ <b>प्रकार:</b> {type_label}\n"
        )
        if item.year:
            card_text += f"📅 <b>वर्ष:</b> {item.year}\n"

        card_text += f"\n🔗 <a href='{item.file_path}'>दस्तऐवज पहा / डाउनलोड करा (Direct Link)</a>"

        # Unique ID for each inline result
        result_id = hashlib.md5(f"mat_{item.id}_{query}".encode()).hexdigest()

        reply_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📥 Download / Open",
                        url=item.file_path if item.file_path.startswith("http") else "https://t.me",
                    )
                ]
            ]
        )

        description = f"{cat_str} • {item.subject} • {type_str}"
        if item.year:
            description += f" • {item.year}"

        articles.append(
            InlineQueryResultArticle(
                id=result_id,
                title=item.title[:64],
                description=description,
                input_message_content=InputTextMessageContent(
                    message_text=card_text,
                    disable_web_page_preview=False,
                ),
                reply_markup=reply_markup,
            )
        )

    await inline_query.answer(
        results=articles,
        cache_time=15,
        is_personal=False,
    )
