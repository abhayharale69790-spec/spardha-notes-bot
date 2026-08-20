"""Inline, Command-based, and Natural Language Search Handlers for Fast Study Material Discovery."""

import hashlib
import html
from typing import List
from aiogram import Router, Bot, F
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
from bot.handlers.categories import get_working_portal_url

search_router = Router(name="search_router")


# ------------------------------------------------------------------------------
# 1. Text Command Search Handler: /search <keywords>
# ------------------------------------------------------------------------------
@search_router.message(Command("search", "find", "shodh"))
async def handle_search_command(message: Message, command: CommandObject) -> None:
    """Handle /search, /find, or /shodh command with keyword query."""
    query = command.args

    if not query or not query.strip():
        guide_text = (
            "🔍 <b>अभ्यास साहित्य शोधा (Search Study Materials):</b>\n\n"
            "कसे शोधावे (How to search):\n"
            "• <code>/search Polity 2024</code>\n"
            "• <code>/search MPSC History</code>\n"
            "• <code>/search पोलीस भरती गणित</code>\n"
            "• <code>/search शासन निर्णय</code>\n\n"
            "💡 <i>किंवा थेट कोणताही विषय या चॅटमध्ये टाईप करा!</i>"
        )
        await message.answer(guide_text)
        return

    await execute_and_reply_search(message, query=query.strip())


# ------------------------------------------------------------------------------
# 2. Natural Language Plain-Text Fallback Search (User directly types keywords)
# ------------------------------------------------------------------------------
@search_router.message(F.text & ~F.text.startswith("/"))
async def handle_natural_text_search(message: Message) -> None:
    """Trigger search automatically when a user sends any non-command text."""
    query = message.text.strip()
    if not query or len(query) < 2:
        return

    # Skip reply keyboard menu button text
    if query in ["📚 अभ्यास साहित्य (Study Material)", "📑 शासन निर्णय (GR)", "📝 प्रश्नपत्रिका (PYQ)"]:
        return

    await execute_and_reply_search(message, query=query)


async def execute_and_reply_search(message: Message, query: str) -> None:
    """Search materials with RapidFuzz + AI embeddings and render results."""
    async with get_session() as session:
        results = await crud.search_study_materials(session, query=query, limit=8)

    safe_query = html.escape(query)

    if not results:
        await message.answer(
            f"🔍 <b>'{safe_query}'</b> साठी कोणतेही साहित्य आढळले नाही.\n"
            f"कृपया वेगळे शब्द वापरून पुन्हा प्रयत्न करा किंवा /categories मधून निवडा."
        )
        return

    response_text = (
        f"🔍 <b>'{safe_query}'</b> चे शोध परिणाम (Search Results):\n"
        f"<i>दस्तऐवज मिळवण्यासाठी खालील बटनावर टॅप करा:</i>"
    )

    buttons = []
    for item in results:
        cat_str = item.exam_category.value if hasattr(item.exam_category, "value") else str(item.exam_category)
        safe_title = html.escape(item.title[:38])
        btn_text = f"📄 {safe_title} [{cat_str}]"
        buttons.append([
            InlineKeyboardButton(
                text=btn_text,
                callback_data=MaterialDownloadCallback(material_id=item.id).pack(),
            )
        ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(response_text, reply_markup=keyboard)


# ------------------------------------------------------------------------------
# 3. Telegram Inline Query Handler (@bot query in any group/chat)
# ------------------------------------------------------------------------------
@search_router.inline_query()
async def handle_inline_search(inline_query: InlineQuery, bot: Bot) -> None:
    """Handle instant inline search queries in any chat or group."""
    query = inline_query.query.strip() if inline_query.query else ""

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
        working_url = get_working_portal_url(item)
        safe_title = html.escape(item.title)

        card_text = (
            f"📚 <b>{safe_title}</b>\n"
            f"🏛️ <b>परीक्षा:</b> {cat_label}\n"
            f"📖 <b>विषय:</b> {item.subject}\n"
            f"🏷️ <b>प्रकार:</b> {type_label}\n"
        )
        if item.year:
            card_text += f"📅 <b>वर्ष:</b> {item.year}\n"

        card_text += f"\n🔗 <a href='{working_url}'>अधिकृत पोर्टलवर उघडा (Official Portal)</a>"

        # Unique ID for each inline result
        result_id = hashlib.md5(f"mat_{item.id}_{query}".encode()).hexdigest()

        reply_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🌐 Open Official Portal",
                        url=working_url,
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
