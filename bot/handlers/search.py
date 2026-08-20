"""Movie-Finder Style Study Material Discovery Engine with Natural Language & Hybrid AI Ranking."""

import hashlib
import html
import re
from typing import List, Optional
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
from database.models import StudyMaterial
from bot.keyboards.inline_menus import (
    MaterialDownloadCallback,
    CategoryNavCallback,
    NavAction,
    CATEGORY_LABELS,
    MATERIAL_TYPE_LABELS,
)
from bot.handlers.categories import get_working_portal_url

search_router = Router(name="search_router")

# Conversational stop words and filler phrases to clean from student queries
CONVERSATIONAL_STOPWORDS = {
    "मला", "पाहिजे", "पाहिजेत", "हवे", "आहे", "आहेत", "द्या", "पाठवा", "कृपया",
    "please", "give", "me", "i", "want", "need", "find", "search", "pdf",
    "notes", "book", "material", "download", "बद्दल", "चे", "च्या", "साठी", "मधील", "आणि",
}


def clean_student_conversational_query(raw_query: str) -> str:
    """Strip conversational filler words to extract core exam/subject/year intent."""
    tokens = raw_query.strip().split()
    cleaned_tokens = [t for t in tokens if t.lower() not in CONVERSATIONAL_STOPWORDS]
    cleaned = " ".join(cleaned_tokens).strip()
    return cleaned if len(cleaned) >= 2 else raw_query.strip()



def format_movie_style_card(item: StudyMaterial) -> str:
    """Format single study material card in clean Movie-Finder style."""
    cat_str = item.exam_category.value if hasattr(item.exam_category, "value") else str(item.exam_category)
    type_str = item.material_type.value if hasattr(item.material_type, "value") else str(item.material_type)
    cat_label = CATEGORY_LABELS.get(cat_str, cat_str)
    type_label = MATERIAL_TYPE_LABELS.get(type_str, type_str)
    safe_title = html.escape(item.title)

    year_str = f"[{item.year}] " if item.year else ""

    card = (
        f"🎬 <b>{year_str}{safe_title}</b>\n"
        f"⭐️ <b>गुणवत्ता (Quality):</b> 🌟🌟🌟🌟🌟 <i>Verified Material</i>\n"
        f"🏛️ <b>परीक्षा प्रवर्ग:</b> #{cat_label}\n"
        f"📖 <b>विषय (Subject):</b> {item.subject}\n"
        f"🏷️ <b>प्रकार (Type):</b> {type_label}\n"
    )
    if item.year:
        card += f"📅 <b>वर्ष / आवृत्ती:</b> {item.year}\n"

    card += "\n📥 <i>मोफत डाऊनलोड करण्यासाठी खालील बटनावर टॅप करा:</i>"
    return card


# ------------------------------------------------------------------------------
# 1. Text Command Search Handler: /search, /find, /shodh
# ------------------------------------------------------------------------------
@search_router.message(Command("search", "find", "shodh"))
async def handle_search_command(message: Message, command: CommandObject) -> None:
    """Handle /search command with keyword query."""
    query = command.args

    if not query or not query.strip():
        guide_text = (
            "🎬 <b>अभ्यास साहित्य शोध इंजिन (Study Material Finder):</b>\n\n"
            "कसे शोधावे (Movie-Style Search Examples):\n"
            "• <code>/search 10th SSC Maths 2024</code>\n"
            "• <code>/search JEE Main Physics Formulas</code>\n"
            "• <code>/search MPSC राज्यशास्त्र PYQ</code>\n"
            "• <code>/search पोलीस भरती सराव पेपर</code>\n\n"
            "💡 <i>किंवा थेट कोणताही विषय या चॅटमध्ये टाईप करा (उदा: 'तलाठी गणित').</i>"
        )
        await message.answer(guide_text)
        return

    await execute_movie_style_search(message, raw_query=query.strip())


# ------------------------------------------------------------------------------
# 2. Natural Language Plain-Text Fallback Search (User naturally types keywords)
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

    await execute_movie_style_search(message, raw_query=query)


async def execute_movie_style_search(message: Message, raw_query: str) -> None:
    """Execute RapidFuzz + AI embeddings search and render Movie-Finder style response."""
    core_query = clean_student_conversational_query(raw_query)

    async with get_session() as session:
        # Search with core cleaned keywords first
        results = await crud.search_study_materials(session, query=core_query, limit=6)
        
        # Fallback to raw query if core query produced 0 results
        if not results and core_query != raw_query:
            results = await crud.search_study_materials(session, query=raw_query, limit=6)

    safe_query = html.escape(raw_query)

    if not results:
        not_found_text = (
            f"🔍 <b>'{safe_query}'</b> साठी कोणतेही अचूक साहित्य आढळले नाही.\n\n"
            f"💡 <b>शोध टिप्स:</b>\n"
            f"• विषयाचे किंवा परीक्षेचे नाव बदला (उदा: <code>MPSC</code>, <code>पोलीस भरती</code>, <code>10th Board</code>, <code>JEE</code>)\n"
            f"• किंवा खालील मेन्यूमधून थेट परीक्षा निवडा."
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📚 सर्व परीक्षा यादी (Browse Exams)",
                        callback_data=CategoryNavCallback(action=NavAction.EXAMS.value).pack(),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🏠 मुख्य मेनू",
                        callback_data=CategoryNavCallback(action=NavAction.MAIN.value).pack(),
                    )
                ],
            ]
        )
        await message.answer(not_found_text, reply_markup=keyboard)
        return

    # Case A: Exactly 1 result -> Show full Movie-Style detail card
    if len(results) == 1:
        item = results[0]
        card_text = format_movie_style_card(item)
        working_url = get_working_portal_url(item)

        buttons = [
            [
                InlineKeyboardButton(
                    text="📥 थेट डाऊनलोड करा (Download PDF)",
                    callback_data=MaterialDownloadCallback(material_id=item.id).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="🌐 अधिकृत पोर्टल",
                    url=working_url,
                ),
                InlineKeyboardButton(
                    text="📢 शेअर करा",
                    url=f"https://t.me/share/url?url=https://t.me/SpardhaNotes_bot?start=mat_{item.id}&text={item.title}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🏠 मुख्य मेनू",
                    callback_data=CategoryNavCallback(action=NavAction.MAIN.value).pack(),
                )
            ],
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer(card_text, reply_markup=keyboard)
        return

    # Case B: Multiple results -> Movie-Finder Results List
    response_text = (
        f"🎬 <b>शोध परिणाम (Search Results) for:</b> <i>'{safe_query}'</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>खालीलपैकी हवे असलेले अभ्यास साहित्य निवडा:</i>"
    )

    buttons = []
    for idx, item in enumerate(results, 1):
        cat_str = item.exam_category.value if hasattr(item.exam_category, "value") else str(item.exam_category)
        year_tag = f" '{str(item.year)[-2:]}" if item.year else ""
        btn_text = f"📄 [{idx}] {item.title[:34]}{year_tag} [{cat_str}]"
        buttons.append([
            InlineKeyboardButton(
                text=btn_text,
                callback_data=MaterialDownloadCallback(material_id=item.id).pack(),
            )
        ])

    # Footer navigation controls
    buttons.append([
        InlineKeyboardButton(
            text="📚 सर्व परीक्षा (All Exams)",
            callback_data=CategoryNavCallback(action=NavAction.EXAMS.value).pack(),
        ),
        InlineKeyboardButton(
            text="🏠 मुख्य मेनू",
            callback_data=CategoryNavCallback(action=NavAction.MAIN.value).pack(),
        ),
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(response_text, reply_markup=keyboard)


# ------------------------------------------------------------------------------
# 3. Telegram Inline Query Handler (@bot query in any group/chat)
# ------------------------------------------------------------------------------
@search_router.inline_query()
async def handle_inline_search(inline_query: InlineQuery, bot: Bot) -> None:
    """Handle instant inline search queries in any chat or group."""
    raw_query = inline_query.query.strip() if inline_query.query else ""
    query = clean_student_conversational_query(raw_query) if raw_query else None

    async with get_session() as session:
        results = await crud.search_study_materials(
            session=session,
            query=query,
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
            f"🎬 <b>{safe_title}</b>\n"
            f"⭐️ <b>गुणवत्ता:</b> 🌟🌟🌟🌟🌟 <i>Verified Notes</i>\n"
            f"🏛️ <b>परीक्षा:</b> #{cat_label}\n"
            f"📖 <b>विषय:</b> {item.subject}\n"
            f"🏷️ <b>प्रकार:</b> {type_label}\n"
        )
        if item.year:
            card_text += f"📅 <b>वर्ष:</b> {item.year}\n"

        card_text += f"\n🔗 <a href='{working_url}'>अधिकृत पोर्टलवर उघडा (Official Portal)</a>"

        # Unique ID for each inline result
        result_id = hashlib.md5(f"mat_{item.id}_{raw_query}".encode()).hexdigest()

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
