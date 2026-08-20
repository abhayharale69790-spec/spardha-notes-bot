"""Start, Help, and Root Navigation Handlers with Deep Linking Support."""

import html
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from bot.keyboards.inline_menus import (
    NavAction,
    CategoryNavCallback,
    MaterialDownloadCallback,
    get_main_menu_keyboard,
    build_categories_keyboard,
)
from bot.handlers.categories import get_working_portal_url
from database.session import get_session
from database import crud
from database.models import StudyMaterial

start_router = Router(name="start_router")

WELCOME_TEXT = (
    "🎯 <b>स्पर्धा परीक्षा अभ्यास मंच (Competitive Exam Hub)</b>\n"
    "<i>MPSC • पोलीस भरती • तलाठी/सरळ सेवा • JEE/NEET • UPSC • बोर्ड</i>\n\n"
    "नमस्कार विद्यार्थी मित्रांनो! 👋\n"
    "या प्लॅटफॉर्मवर आपल्याला सर्व स्पर्धा परीक्षांसाठी आवश्यक <b>शासन निर्णय (GR), "
    "मागील वर्षांच्या प्रश्नपत्रिका (PYQ), नोट्स आणि चालू घडामोडी</b> एकाच ठिकाणी मिळतील.\n\n"
    "📌 <b>खालील पर्यायांपैकी एक निवडा:</b>"
)

HELP_TEXT = (
    "📖 <b>बॉट कसा वापरावा? (How to Use):</b>\n\n"
    "1️⃣ <b>📚 परीक्षानिहाय साहित्य:</b> MPSC, पोलीस भरती, JEE, NEET इत्यादी परीक्षांचे विषयवार साहित्य मिळवा.\n"
    "2️⃣ <b>📑 शासन निर्णय (GR):</b> महाराष्ट्र शासनाचे ताजे अधिकृत शासन निर्णय व परिपत्रके.\n"
    "3️⃣ <b>📝 प्रश्नपत्रिका (PYQ):</b> मागील वर्षांचे अधिकृत पेपर्स आणि उत्तरे.\n"
    "4️⃣ <b>🔍 शोध (Search):</b> <code>/search &lt;विषय/वर्ष&gt;</code> लिहा किंवा थेट चॅटमध्ये नाव टाईप करा (उदा: <code>MPSC History</code>).\n\n"
    "💡 <i>कोणत्याही मदतीसाठी किंवा अभ्यासाच्या साहित्यासाठी खालील मेनू वापरा.</i>"
)


@start_router.message(CommandStart())
async def handle_start_command(message: Message, command: CommandObject, bot: Bot) -> None:
    """Handle /start command with support for deep links (e.g. /start mat_123)."""
    args = command.args

    # Case 1: Deep link to specific study material (e.g. shared link)
    if args and args.startswith("mat_"):
        try:
            mat_id_str = args.replace("mat_", "").strip()
            material_id = int(mat_id_str)
            async with get_session() as session:
                material: Optional[StudyMaterial] = await crud.get_study_material_by_id(
                    session, material_id=material_id
                )

            if material:
                working_url = get_working_portal_url(material)
                safe_title = html.escape(material.title)
                card_text = (
                    f"📄 <b>{safe_title}</b>\n\n"
                    f"🏛️ <b>परीक्षा:</b> #{material.exam_category.value}\n"
                    f"📖 <b>विषय:</b> {material.subject}\n"
                    f"🏷️ <b>साहित्य प्रकार:</b> #{material.material_type.value}\n"
                )
                if material.year:
                    card_text += f"📅 <b>वर्ष:</b> {material.year}\n"

                card_text += "\n📥 <i>अभ्यासासाठी मोफत उपलब्ध | Spardha Notes Hub</i>"

                reply_markup = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="📥 दस्तऐवज मिळवा (Get Document)",
                                callback_data=MaterialDownloadCallback(material_id=material.id).pack(),
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text="🌐 अधिकृत पोर्टल",
                                url=working_url,
                            ),
                            InlineKeyboardButton(
                                text="🏠 मुख्य मेनू",
                                callback_data=CategoryNavCallback(action=NavAction.MAIN.value).pack(),
                            ),
                        ],
                    ]
                )
                await message.answer(text=card_text, reply_markup=reply_markup)
                return
        except Exception:
            pass

    # Case 2: Standard Start Welcome Menu
    await message.answer(
        text=WELCOME_TEXT,
        reply_markup=get_main_menu_keyboard(),
    )


@start_router.message(Command("help"))
async def handle_help_command(message: Message) -> None:
    """Handle /help command."""
    await message.answer(
        text=HELP_TEXT,
        reply_markup=get_main_menu_keyboard(),
    )


@start_router.message(Command("exams", "notes", "study", "materials"))
async def handle_exams_shortcut(message: Message) -> None:
    """Shortcut command aliases for direct category exploration."""
    text = (
        "📚 <b>सर्व स्पर्धा परीक्षा अभ्यास साहित्य (Study Materials)</b>\n\n"
        "कृपया खालीलपैकी तुमची <b>लक्ष्य परीक्षा (Target Exam)</b> निवडा:"
    )
    await message.answer(text=text, reply_markup=build_categories_keyboard())


@start_router.callback_query(CategoryNavCallback.filter(F.action == NavAction.MAIN.value))
async def handle_nav_main_menu(callback: CallbackQuery) -> None:
    """Handle back to main menu callback."""
    if callback.message:
        await callback.message.edit_text(
            text=WELCOME_TEXT,
            reply_markup=get_main_menu_keyboard(),
        )
    await callback.answer()


@start_router.callback_query(F.data == "noop")
async def handle_noop(callback: CallbackQuery) -> None:
    """Acknowledge non-interactive informational buttons (e.g. Page number)."""
    await callback.answer()
