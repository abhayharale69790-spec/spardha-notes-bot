"""Start, Help, and Root Navigation Handlers."""

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from bot.keyboards.inline_menus import (
    NavAction,
    CategoryNavCallback,
    get_main_menu_keyboard,
)

start_router = Router(name="start_router")

WELCOME_TEXT = (
    "🎯 <b>स्पर्धा परीक्षा अभ्यास मंच (Competitive Exam Hub)</b>\n"
    "<i>MPSC • पोलीस भरती • तलाठी/सरळ सेवा • बँकिंग</i>\n\n"
    "नमस्कार विद्यार्थी मित्रांनो! 👋\n"
    "या प्लॅटफॉर्मवर आपल्याला सर्व स्पर्धा परीक्षांसाठी आवश्यक <b>शासन निर्णय (GR), "
    "मागील वर्षांच्या प्रश्नपत्रिका (PYQ), नोट्स आणि चालू घडामोडी</b> एकाच ठिकाणी मिळतील.\n\n"
    "📌 <b>खालील पर्यायांपैकी एक निवडा:</b>"
)

HELP_TEXT = (
    "📖 <b>बॉट कसा वापरावा? (How to Use):</b>\n\n"
    "1️⃣ <b>📚 परीक्षानिहाय साहित्य:</b> MPSC, पोलीस भरती, बँकिंग इत्यादी परीक्षांचे विषयवार साहित्य मिळवा.\n"
    "2️⃣ <b>📑 शासन निर्णय (GR):</b> महाराष्ट्र शासनाचे ताजे अधिकृत शासन निर्णय व परिपत्रके.\n"
    "3️⃣ <b>📝 प्रश्नपत्रिका (PYQ):</b> मागील वर्षांचे अधिकृत पेपर्स आणि उत्तरे.\n"
    "4️⃣ <b>🔍 शोध (Search):</b> <code>/search &lt;विषय/वर्ष&gt;</code> लिहा किंवा इनलाईन मोड वापरा (उदा: <code>@bot Polity 2023</code>).\n\n"
    "💡 <i>कोणत्याही अडचणीसाठी किंवा अभ्यासाच्या साहित्यासाठी मुख्य मेनू वापरा.</i>"
)


@start_router.message(CommandStart())
async def handle_start_command(message: Message) -> None:
    """Handle /start command."""
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
