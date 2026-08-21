"""Mass Backfill Job Supervisor & Detached Process Control CLI.

Usage:
  python scripts/backfill_control.py start     # Launch detached daemon, verify running, exit
  python scripts/backfill_control.py status    # Show real-time job progress & channel breakdown
  python scripts/backfill_control.py pause     # Gracefully pause current job
  python scripts/backfill_control.py resume    # Resume paused job
  python scripts/backfill_control.py cancel    # Cancel active job
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from database.session import init_db, get_session
from database import crud
from database.models import BackfillJob, BackfillJobStatus, BackfillChannelTask, BackfillTaskStatus, StudyMaterial

PID_FILE = Path("data/backfill_worker.pid")
STOP_FILE = Path("data/backfill_worker.stop")
STATUS_FILE = Path("data/backfill_status.json")
LOG_FILE = Path("data/backfill_daemon.log")


def is_pid_running(pid: int) -> bool:
    """Check if process with PID is currently alive."""
    if pid <= 0:
        return False
    try:
        if sys.platform == "win32":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        else:
            os.kill(pid, 0)
            return True
    except Exception:
        return False


def get_active_worker_pid() -> int:
    """Read PID from PID_FILE if process is alive."""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text(encoding="utf-8").strip())
            if is_pid_running(pid):
                return pid
        except Exception:
            pass
    return 0


async def start_job(per_channel_limit: int = 50):
    """Launch detached background backfill daemon, verify running, and exit."""
    await init_db()
    existing_pid = get_active_worker_pid()
    if existing_pid:
        print(f"⚠️ Backfill Worker Daemon is ALREADY RUNNING (PID: {existing_pid}).")
        await show_status()
        return

    if STOP_FILE.exists():
        try: STOP_FILE.unlink()
        except Exception: pass

    python_exe = sys.executable
    daemon_script = str(Path("workers/backfill_daemon.py").resolve())

    print("=" * 135)
    print(" 🚀 LAUNCHING DETACHED RESUMABLE MASS BACKFILL WORKER")
    print(f" 📅 Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 135 + "\n")

    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

    # Spawn fully detached process
    proc = subprocess.Popen(
        [python_exe, daemon_script],
        cwd=str(Path(__file__).resolve().parent.parent),
        creationflags=flags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )

    print(f"📡 Worker process spawned (OS PID: {proc.pid}). Waiting for initialization...")

    # Wait up to 5 seconds to verify startup & DB registration
    verified = False
    for _ in range(10):
        await asyncio.sleep(0.5)
        active_pid = get_active_worker_pid()
        if active_pid:
            verified = True
            break

    if verified:
        print(f"✅ VERIFIED: Mass Backfill Daemon is RUNNING INDEPENDENTLY (PID: {proc.pid}).")
        async with get_session() as session:
            job = await crud.get_active_backfill_job(session)
            if job:
                print(f"📋 Active Job UUID : {job.job_uuid} (Job ID: #{job.id})")
                print(f"📊 Channels Queued : {job.total_channels} channels")
                print(f"🔒 Checkpointing   : Enabled (Persistent Database Transactions)")
        print("\n💡 Antigravity agent can safely exit. The worker is running detached.")
        print("💡 Use 'python scripts/backfill_control.py status' to monitor progress anytime.\n")
    else:
        print(f"⚠️ Warning: Process spawned with PID {proc.pid}, but PID file not written yet. Check {LOG_FILE}.")


async def show_status():
    """Display real-time telemetry, database state, and per-channel checkpoints."""
    await init_db()
    active_pid = get_active_worker_pid()
    pid_status = f"🟢 RUNNING (PID: {active_pid})" if active_pid else "🔴 STOPPED / IDLE"

    async with get_session() as session:
        job = await crud.get_latest_backfill_job(session)
        tasks = await crud.get_backfill_tasks_for_job(session, job.id) if job else []
        mat_res = await session.execute(select(StudyMaterial))
        total_materials = len(mat_res.scalars().all())

    print("=" * 135)
    print(" 📊 TELEGRAM MASS BACKFILL TELEMETRY & JOB STATUS")
    print(f" 📅 Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f" ⚙️ Worker Daemon State : {pid_status}")
    print("=" * 135 + "\n")

    if not job:
        print("ℹ️ No backfill jobs found in database. Run 'python scripts/backfill_control.py start' to initiate.")
        return

    heartbeat_str = job.heartbeat_at.strftime("%Y-%m-%d %H:%M:%S UTC") if job.heartbeat_at else "Never"
    started_str = job.started_at.strftime("%Y-%m-%d %H:%M:%S UTC") if job.started_at else "N/A"

    print(f"📋 Job UUID             : {job.job_uuid} (Job ID: #{job.id})")
    print(f"🔄 Job Status           : {job.status.value}")
    print(f"⏱️ Started At           : {started_str}")
    print(f"💓 Last Heartbeat       : {heartbeat_str}")
    print(f"📥 Channels Completed   : {job.completed_channels} / {job.total_channels}")
    print(f"📄 Messages Scanned     : {job.total_scanned}")
    print(f"📚 Verified Ingested    : +{job.total_ingested} PDFs in this job")
    print(f"🏛️ Total Verified in DB : {total_materials} PDFs")
    if job.error_message:
        print(f"⚠️ Last Error / Notice  : {job.error_message}")

    print("\n" + "=" * 135)
    print(" 📑 PER-CHANNEL CHECKPOINTS & PROGRESS")
    print("=" * 135)
    print(f"{'#':<3} | {'USERNAME':<32} | {'CAT':<12} | {'STATUS':<12} | {'LAST MSG ID':<13} | {'SCANNED':<9} | {'INGESTED':<10} | {'TITLE'}")
    print("─" * 135)

    for idx, t in enumerate(tasks, 1):
        uname = f"@{t.channel_username}" if t.channel_username else f"ID {t.channel_id}"
        status_icon = "✅" if t.status == BackfillTaskStatus.COMPLETED else ("⏳" if t.status == BackfillTaskStatus.IN_PROGRESS else "⚪")
        print(f"{idx:2d}. | {uname:<32} | #{t.exam_category.value:<11} | {status_icon} {t.status.value:<9} | #{t.last_successful_msg_id:<12} | {t.messages_scanned:<9} | +{t.pdfs_ingested:<9} | {t.title[:35]}")

    print("=" * 135 + "\n")


async def pause_job():
    """Gracefully signal the active worker daemon to pause."""
    STOP_FILE.write_text("STOP", encoding="utf-8")
    print("🛑 Stop flag set (data/backfill_worker.stop). Worker daemon will pause gracefully at next checkpoint.")
    active_pid = get_active_worker_pid()
    if active_pid:
        print(f"⏳ Waiting for Worker PID {active_pid} to shut down...")
        for _ in range(10):
            if not is_pid_running(active_pid):
                print(f"✅ Worker PID {active_pid} stopped cleanly.")
                break
            await asyncio.sleep(0.5)


async def cancel_job():
    """Cancel the active job in the database and stop worker."""
    await init_db()
    STOP_FILE.write_text("STOP", encoding="utf-8")
    async with get_session() as session:
        job = await crud.get_active_backfill_job(session)
        if job:
            await crud.update_backfill_job_status(session, job.id, BackfillJobStatus.CANCELLED)
            print(f"🚫 Cancelled Backfill Job #{job.id} ({job.job_uuid}).")
        else:
            print("ℹ️ No active backfill job to cancel.")


def main():
    cmd = sys.argv[1].lower() if len(sys.argv) > 1 else "status"

    if cmd == "start":
        asyncio.run(start_job())
    elif cmd in ("status", "info"):
        asyncio.run(show_status())
    elif cmd in ("pause", "stop"):
        asyncio.run(pause_job())
    elif cmd == "resume":
        asyncio.run(start_job())
    elif cmd == "cancel":
        asyncio.run(cancel_job())
    else:
        print(f"Unknown command: '{cmd}'. Available commands: start, status, pause, resume, cancel")


if __name__ == "__main__":
    main()
