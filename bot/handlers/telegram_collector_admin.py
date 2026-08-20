"""Admin Telegram MTProto Collector Commands & Telemetry Handlers."""

import html
import logging
from aiogram import Router, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from config.settings import get_settings
from database.session import get_session
from database import crud
from database.models import ChannelAuthStatus, ExamCategory
from collectors.telegram_channel_registry import telegram_channel_registry
from collectors.telegram_user_collector import telegram_user_collector
from bot.middlewares.auth import IsAdminFilter

logger = logging.getLogger(__name__)
telegram_collector_admin_router = Router(name="telegram_collector_admin_router")
settings = get_settings()


@telegram_collector_admin_router.message(Command("telegram_sources", "tg_sources"), IsAdminFilter())
async def handle_telegram_sources_command(message: Message) -> None:
    """Display all registered approved Telegram channels and their sync states."""
    async with get_session() as session:
        sources = await telegram_channel_registry.get_all_approved_sources(session)
        if not sources:
            sources = await telegram_channel_registry.initialize_defaults(session)

    if not sources:
        await message.reply("ℹ️ कोणतेही अधिकृत टेलिग्राम चॅनेल्स नोंदणीकृत नाहीत (No approved sources).")
        return

    lines = [
        f"📡 <b>{settings.brand_name} | Approved Telegram Sources Registry</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for s in sources:
        status_icon = "🟢" if s.authorization_status == ChannelAuthStatus.AUTHORIZED else "🟡"
        uname_str = f"@{s.channel_username}" if s.channel_username else f"ID {s.channel_id}"
        lines.append(
            f"{status_icon} <b>{html.escape(s.title)}</b>\n"
            f"   🔗 {uname_str} | 🏛️ #{s.exam_category.value}\n"
            f"   📊 Status: <code>{s.authorization_status.value}</code> | 📥 PDFs: <b>{s.total_verified}</b>\n"
            f"   🔄 Last Scanned Msg: <code>#{s.last_scanned_msg_id}</code>"
        )
        lines.append("──────────────────────────────────")

    lines.append("💡 <i>स्कॅन करण्यासाठी <code>/telegram_scan</code> किंवा <code>/telegram_backfill &lt;channel&gt;</code> वापरा.</i>")
    await message.reply("\n".join(lines), parse_mode="HTML")


@telegram_collector_admin_router.message(Command("telegram_scan", "tg_scan"), IsAdminFilter())
async def handle_telegram_scan_command(message: Message) -> None:
    """Trigger on-demand scan across all active approved channels."""
    status_msg = await message.reply("⏳ <b>अधिकृत टेलिग्राम चॅनेल्स स्कॅन करत आहे...</b>\n<i>(MTProto Ingestion Engine Active)</i>", parse_mode="HTML")

    async with get_session() as session:
        sources = await telegram_channel_registry.get_all_approved_sources(session)
        if not sources:
            sources = await telegram_channel_registry.initialize_defaults(session)

    total_added = 0
    scanned_channels = 0

    for s in sources:
        if not s.is_active:
            continue
        scanned_channels += 1
        added = await telegram_user_collector.scan_channel_messages(s, limit=25)
        total_added += added

    summary_text = (
        f"✅ <b>टेलिग्राम स्कॅन यशस्वी (Scan Complete)!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 <b>एकूण तपासलेली चॅनेल्स:</b> <code>{scanned_channels}</code>\n"
        f"📥 <b>नवीन प्रमाणित अभ्यास साहित्य:</b> <code>{total_added}</code> नवीन PDF\n\n"
        f"💡 <i>साहित्य तपासण्यासाठी <code>/telegram_stats</code> किंवा <code>/coverage</code> पहा.</i>"
    )
    await status_msg.edit_text(summary_text, parse_mode="HTML")


@telegram_collector_admin_router.message(Command("telegram_backfill", "tg_backfill"), IsAdminFilter())
async def handle_telegram_backfill_command(message: Message, command: CommandObject) -> None:
    """Trigger historical message backfill for an approved channel."""
    args = (command.args or "").strip().split()
    if not args:
        await message.reply(
            "⚠️ <b>वापर पद्धत (Usage):</b>\n"
            "<code>/telegram_backfill &lt;channel_username&gt; [count]</code>\n"
            "उदा: <code>/telegram_backfill mpsc_study_materials 50</code>",
            parse_mode="HTML",
        )
        return

    target_username = args[0].replace("@", "")
    count = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
    count = min(count, 200)

    async with get_session() as session:
        ch = await crud.get_telegram_channel_by_username(session, target_username)

    if not ch:
        await message.reply(f"❌ चॅनेल <b>@{target_username}</b> नोंदणीकृत नाही (Channel not found in approved registry).", parse_mode="HTML")
        return

    status_msg = await message.reply(f"⏳ <b>@{target_username}</b> मधील मागील {count} मेसेजेस तपासत आहे...", parse_mode="HTML")
    added = await telegram_user_collector.scan_channel_messages(ch, limit=count)

    await status_msg.edit_text(
        f"✅ <b>बॅकफील पूर्ण (Backfill Completed)!</b>\n\n"
        f"📌 <b>चॅनेल:</b> @{target_username}\n"
        f"📥 <b>एकूण नवीन साहित्य:</b> <code>{added}</code> verified PDFs",
        parse_mode="HTML",
    )


@telegram_collector_admin_router.message(Command("telegram_stats", "tg_stats"), IsAdminFilter())
async def handle_telegram_stats_command(message: Message) -> None:
    """Display comprehensive telemetry for Telegram user-collector operations."""
    async with get_session() as session:
        stats = await crud.get_telegram_collector_telemetry(session)
        sources = await telegram_channel_registry.get_all_approved_sources(session)

    stats_text = (
        f"📊 <b>{settings.brand_name} | MTProto User Collector Telemetry</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 <b>नोंदणीकृत अधिकृत चॅनेल्स:</b> <code>{len(sources)} Active Channels</code>\n"
        f"📥 <b>टेलिग्राममधून प्रमाणित साहित्य:</b> <code>{stats['pdfs_verified']} Verified PDFs</code>\n"
        f"⚙️ <b>वॉटरमार्क &amp; ब्रँडिंग:</b> <code>{settings.brand_name} (Active)</code>\n"
        f"🔒 <b>प्रमाणीकरण पद्धत:</b> <code>%PDF- + pypdf + SHA-256 + Usefulness Filter</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <i>सिस्टम स्टेटस: अखंड स्वयंचलित हार्वेस्टिंग सुरू आहे.</i>"
    )
    await message.reply(stats_text, parse_mode="HTML")
