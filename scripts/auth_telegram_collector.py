"""Secure Interactive Authentication Script for Telegram MTProto Collector Account.

Safely authenticates a dedicated user account via Telethon, creates a persistent
session file in data/telegram_user_session.session, and verifies channel access.
Never exposes api_hash, passwords, or session strings in logs.
"""

import asyncio
from getpass import getpass
import logging
from pathlib import Path
import sys

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from config.settings import get_settings

settings = get_settings()

SESSION_DIR = Path("data")
SESSION_DIR.mkdir(parents=True, exist_ok=True)
SESSION_PATH = str(SESSION_DIR / "telegram_user_session")


async def authenticate():
    print("=" * 80)
    print(" 🔐 SECURE TELEGRAM MTPROTO COLLECTOR AUTHENTICATION")
    print("=" * 80)
    print("Persistent session will be saved to: data/telegram_user_session.session\n")

    api_id = settings.telegram_api_id
    api_hash = settings.telegram_api_hash

    if not api_id or not api_hash:
        print("❌ TELEGRAM_API_ID or TELEGRAM_API_HASH is missing in .env")
        return

    print("✅ Loaded API ID & API Hash from environment.")
    phone = input("👉 Enter Telegram Phone Number with country code (e.g. +919876543210): ").strip()
    if not phone:
        print("❌ Phone number cannot be empty.")
        return


    print("\n⏳ Connecting to Telegram MTProto Gateway...")
    client = TelegramClient(SESSION_PATH, api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        print(f"📨 Sending login code to {phone}...")
        sent_code = await client.send_code_request(phone)
        code = input("👉 Enter the 5-digit Telegram Login Code you received: ").strip()

        try:
            await client.sign_in(phone, code)
        except SessionPasswordNeededError:
            print("🔒 Two-Step Verification (2FA) is enabled on this account.")
            password = getpass("👉 Enter your Telegram 2FA Cloud Password (hidden): ")
            await client.sign_in(password=password)

    # Step 2: Verify Identity
    me = await client.get_me()
    print("\n" + "=" * 80)
    print(" ✅ COLLECTOR AUTHENTICATION SUCCESSFUL!")
    print("=" * 80)
    print(f" • First Name     : {me.first_name}")
    print(f" • Username       : @{me.username}" if me.username else " • Username       : None")
    print(f" • Telegram ID    : {me.id}")
    print(f" • Session File   : {SESSION_PATH}.session (Created & Persisted)")
    print(f" • Authenticated  : YES")
    print("=" * 80)

    # Step 3: Test Channel Access (@spardhanoteshub)
    print("\n📡 Testing Access to Target Channel '@spardhanoteshub'...")
    try:
        entity = await client.get_entity("spardhanoteshub")
        print(f" ✅ Channel Access Verified: '{entity.title}' (ID: {entity.id})")
    except Exception as e:
        print(f" ⚠️ Channel access check warning: {e}")

    await client.disconnect()
    print("\n🎉 Collector is now ready for background scanning & backfilling!")


if __name__ == "__main__":
    asyncio.run(authenticate())
