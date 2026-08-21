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


@telegram_collector_admin_router.message(Command("telegram_discover", "tg_discover"), IsAdminFilter())
async def handle_telegram_discover_command(message: Message) -> None:
    """Trigger MTProto global keyword discovery for new public educational study channels."""
    status_msg = await message.reply(
        "🔎 <b>नवीन टेलिग्राम अभ्यास चॅनेल्स शोधत आहे...</b>\n"
        "<i>(MTProto Global Search across 26 exam keywords active...)</i>",
        parse_mode="HTML",
    )

    from collectors.telegram_channel_discovery import telegram_channel_discovery
    discovered = await telegram_channel_discovery.discover_channels(limit_per_keyword=10)

    if not discovered:
        await status_msg.edit_text("ℹ️ कोणतेही नवीन प्रमाणित चॅनेल्स सापडले नाहीत (No new candidate channels found).", parse_mode="HTML")
        return

    # Group by category
    by_cat = {}
    for item in discovered:
        cat = item["category"]
        by_cat.setdefault(cat, []).append(item)

    lines = [
        f"🎉 <b>स्वयंचलित चॅनेल शोध पूर्ण (Discovery Completed)!</b>",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📡 <b>एकूण नवीन शोधलेली चॅनेल्स:</b> <code>{len(discovered)} New Channels</code>",
        f"🔒 <b>स्थिती:</b> <code>PENDING_REVIEW (No downloads performed)</code>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "<b>श्रेणीनुसार सारांश (Summary by Category):</b>",
    ]

    for cat_name, items in sorted(by_cat.items()):
        high_yield = sum(1 for x in items if "High" in x["estimated_yield"])
        lines.append(f"• <b>#{cat_name}</b>: <code>{len(items)} channels</code> (🔥 {high_yield} High-Yield)")

    lines.append("\n💡 <i>तपशील पाहण्यासाठी <code>/telegram_discovered</code> किंवा <code>/telegram_discovered &lt;category&gt;</code> वापरा.</i>")
    await status_msg.edit_text("\n".join(lines), parse_mode="HTML")


@telegram_collector_admin_router.message(Command("telegram_discovered", "tg_discovered"), IsAdminFilter())
async def handle_telegram_discovered_command(message: Message, command: CommandObject) -> None:
    """List newly discovered public channels pending review."""
    args = (command.args or "").strip().upper()
    cat_filter = None
    if args:
        try:
            cat_filter = ExamCategory(args)
        except ValueError:
            pass

    async with get_session() as session:
        channels = await crud.get_discovered_channels(
            session=session,
            status=ChannelAuthStatus.PENDING_REVIEW,
            category=cat_filter,
            limit=20,
        )

    if not channels:
        # Check JSON fallback if database has not been populated yet
        json_path = Path("data/discovered_channels.json")
        if json_path.exists():
            with open(json_path, encoding="utf-8") as f:
                import json
                raw = json.load(f)
                if cat_filter:
                    raw = [x for x in raw if x.get("category") == cat_filter.value]
                if raw:
                    lines = [
                        f"📡 <b>Discovered Channels Pending Review ({len(raw)} items)</b>",
                        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                    ]
                    for item in raw[:15]:
                        lines.append(
                            f"🟡 <b>{html.escape(item['title'])}</b>\n"
                            f"   🔗 {item['username']} | 🏛️ #{item['category']}\n"
                            f"   📥 PDF Yield: <b>{item['pdf_count_sample']}/100 ({item['pdf_yield_pct']}%)</b> | {item['estimated_yield']}\n"
                            f"   📅 Latest: <code>#{item['latest_msg_id']} ({item['latest_date']})</code>"
                        )
                        lines.append("──────────────────────────────────")
                    await message.reply("\n".join(lines), parse_mode="HTML")
                    return

        await message.reply("ℹ️ कोणतेही नवीन शोधलेले चॅनेल्स उपलब्ध नाहीत. शोध घेण्यासाठी <code>/telegram_discover</code> चालवा.", parse_mode="HTML")
        return

    lines = [
        f"📡 <b>शोधलेली अभ्यास चॅनेल्स (Discovered Channels - Review Queue)</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for c in channels:
        uname = f"@{c.channel_username}" if c.channel_username else f"ID {c.channel_id}"
        lines.append(
            f"🟡 <b>{html.escape(c.title)}</b>\n"
            f"   🔗 {uname} | 🏛️ #{c.exam_category.value}\n"
            f"   📊 Status: <code>{c.authorization_status.value}</code> (Active: {c.is_active})\n"
            f"   🔄 Last Msg: <code>#{c.last_scanned_msg_id}</code>"
        )
        lines.append("──────────────────────────────────")

    lines.append("💡 <i>मंजूर करण्यासाठी <code>/telegram_backfill &lt;channel&gt;</code> किंवा ऍडमिन पॅनेल वापरा.</i>")
    await message.reply("\n".join(lines), parse_mode="HTML")


@telegram_collector_admin_router.message(Command("backfill_status", "tg_backfill_status"), IsAdminFilter())
async def handle_backfill_status_command(message: Message) -> None:
    """Display real-time mass backfill daemon state, job progress, and checkpoints."""
    from scripts.backfill_control import get_active_worker_pid
    active_pid = get_active_worker_pid()
    pid_status = f"🟢 <b>RUNNING</b> (PID: <code>{active_pid}</code>)" if active_pid else "🔴 <b>STOPPED / IDLE</b>"

    async with get_session() as session:
        job = await crud.get_latest_backfill_job(session)
        tasks = await crud.get_backfill_tasks_for_job(session, job.id) if job else []
        mat_res = await session.execute(select(StudyMaterial))
        total_materials = len(mat_res.scalars().all())

    if not job:
        await message.reply("ℹ️ कोणतेही बॅकफिल जॉब सुरू नाही. सुरू करण्यासाठी <code>/backfill_start</code> वापरा.", parse_mode="HTML")
        return

    heartbeat_str = job.heartbeat_at.strftime("%H:%M:%S UTC") if job.heartbeat_at else "Never"
    status_text = (
        f"⚙️ <b>Mass Backfill Daemon Job Telemetry</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 <b>Worker State:</b> {pid_status}\n"
        f"📋 <b>Job UUID:</b> <code>{job.job_uuid}</code> (#{job.id})\n"
        f"🔄 <b>Job Status:</b> <code>{job.status.value}</code>\n"
        f"💓 <b>Heartbeat:</b> <code>{heartbeat_str}</code>\n"
        f"📊 <b>Channels Completed:</b> <b>{job.completed_channels} / {job.total_channels}</b>\n"
        f"📄 <b>Messages Scanned:</b> <code>{job.total_scanned}</code>\n"
        f"📥 <b>Verified PDFs Ingested:</b> <b>+{job.total_ingested}</b>\n"
        f"🏛️ <b>Total DB Verified PDFs:</b> <b>{total_materials}</b>\n"
    )

    if tasks:
        status_text += "\n<b>Recent Channel Tasks:</b>\n"
        for t in tasks[:8]:
            uname = f"@{t.channel_username}" if t.channel_username else f"ID {t.channel_id}"
            icon = "✅" if t.status.value == "COMPLETED" else ("⏳" if t.status.value == "IN_PROGRESS" else "⚪")
            status_text += f"{icon} <code>{uname}</code> (+{t.pdfs_ingested} PDFs, #{t.last_successful_msg_id})\n"

    status_text += "\n💡 <i>नियंत्रण: <code>/backfill_start</code> | <code>/backfill_pause</code> | <code>/backfill_resume</code></i>"
    await message.reply(status_text, parse_mode="HTML")


@telegram_collector_admin_router.message(Command("backfill_start", "tg_backfill_start"), IsAdminFilter())
async def handle_backfill_start_command(message: Message) -> None:
    """Launch detached background backfill daemon from Telegram."""
    from scripts.backfill_control import start_job, get_active_worker_pid
    active_pid = get_active_worker_pid()
    if active_pid:
        await message.reply(f"⚠️ बॅकफिल वर्कर आधीच कार्यरत आहे (Worker already running on PID: <code>{active_pid}</code>).", parse_mode="HTML")
        return

    await message.reply("🚀 <b>Detached Mass Backfill Daemon सुरू करत आहे...</b>", parse_mode="HTML")
    await start_job()
    await handle_backfill_status_command(message)


@telegram_collector_admin_router.message(Command("backfill_pause", "tg_backfill_pause"), IsAdminFilter())
async def handle_backfill_pause_command(message: Message) -> None:
    """Pause the active backfill daemon gracefully."""
    from scripts.backfill_control import pause_job
    await pause_job()
    await message.reply("⏸️ <b>Mass Backfill Daemon ला थाबंण्याचा सिग्नल दिला आहे (Job Paused).</b>", parse_mode="HTML")


@telegram_collector_admin_router.message(Command("backfill_resume", "tg_backfill_resume"), IsAdminFilter())
async def handle_backfill_resume_command(message: Message) -> None:
    """Resume paused backfill daemon."""
    from scripts.backfill_control import start_job
    await start_job()
    await message.reply("▶️ <b>Mass Backfill Daemon पुन्हा सुरू केले आहे (Job Resumed).</b>", parse_mode="HTML")


