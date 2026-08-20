"""Interactive Auth Runner for Telethon MTProto Collector."""

import asyncio
from pathlib import Path
import sys

# Ensure UTF-8 unbuffered output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from config.settings import get_settings

settings = get_settings()
SESSION_DIR = Path("data")
SESSION_DIR.mkdir(parents=True, exist_ok=True)
SESSION_PATH = str(SESSION_DIR / "telegram_user_session")


async def main():
    api_id = settings.telegram_api_id
    api_hash = settings.telegram_api_hash

    if not api_id or not api_hash:
        print("[ERROR] API_ID or API_HASH missing in environment", flush=True)
        return

    client = TelegramClient(SESSION_PATH, api_id, api_hash)
    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"[ALREADY_AUTHORIZED] First Name: {me.first_name}, Username: @{me.username or 'None'}, ID: {me.id}", flush=True)
        await client.disconnect()
        return

    print("[ENTER_PHONE]", flush=True)
    phone = sys.stdin.readline().strip()
    if not phone:
        print("[ERROR] Phone number was empty", flush=True)
        await client.disconnect()
        return

    print(f"Requesting login code for {phone}...", flush=True)
    try:
        sent_code = await client.send_code_request(phone)
    except Exception as e:
        print(f"[ERROR_SEND_CODE] {e}", flush=True)
        await client.disconnect()
        return

    print("[ENTER_CODE]", flush=True)
    code = sys.stdin.readline().strip()
    if not code:
        print("[ERROR] Code was empty", flush=True)
        await client.disconnect()
        return

    try:
        await client.sign_in(phone, code)
    except SessionPasswordNeededError:
        print("[ENTER_PASSWORD]", flush=True)
        password = sys.stdin.readline().strip()
        try:
            await client.sign_in(password=password)
        except Exception as ep:
            print(f"[ERROR_PASSWORD] {ep}", flush=True)
            await client.disconnect()
            return
    except Exception as e:
        print(f"[ERROR_SIGNIN] {e}", flush=True)
        await client.disconnect()
        return

    me = await client.get_me()
    print("[AUTH_SUCCESS]", flush=True)
    print(f"FIRST_NAME: {me.first_name}", flush=True)
    print(f"USERNAME: @{me.username or 'None'}", flush=True)
    print(f"USER_ID: {me.id}", flush=True)
    print(f"SESSION: data/telegram_user_session.session", flush=True)

    # Check access to @spardhanoteshub
    try:
        entity = await client.get_entity("spardhanoteshub")
        print(f"CHANNEL_ACCESS_VERIFIED: {entity.title} (ID: {entity.id})", flush=True)
    except Exception as ec:
        print(f"CHANNEL_ACCESS_NOTE: {ec}", flush=True)

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
