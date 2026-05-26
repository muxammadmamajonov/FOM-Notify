#!/usr/bin/env python3
"""Dev helper: send a one-shot screenshot via aiogram 3 to chats listed in
INITIAL_SUBSCRIBERS (or GROUP_CHAT_ID as a single fallback).

Example:
    venv/bin/python tools/send_screenshot_to_group.py
"""
import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402
from aiogram import Bot  # noqa: E402
from aiogram.types import FSInputFile  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    print("No TELEGRAM_BOT_TOKEN in env")
    raise SystemExit(1)

raw_subs = os.getenv("INITIAL_SUBSCRIBERS", "")
chat_ids = [int(x.strip()) for x in raw_subs.split(",") if x.strip()]
if not chat_ids:
    fallback = os.getenv("GROUP_CHAT_ID")
    if fallback:
        chat_ids = [int(fallback)]
if not chat_ids:
    print("Neither INITIAL_SUBSCRIBERS nor GROUP_CHAT_ID is set; nothing to do.")
    raise SystemExit(0)

img = PROJECT_ROOT / "screenshots" / "run-once.png"
if not img.exists():
    print("Screenshot not found:", img)
    raise SystemExit(1)


async def main():
    bot = Bot(token=TOKEN)
    try:
        photo = FSInputFile(str(img), filename=img.name)
        for cid in chat_ids:
            try:
                await bot.send_photo(
                    chat_id=cid,
                    photo=photo,
                    caption="Automated test screenshot (Playwright)",
                )
                print(f"Sent to {cid}")
            except Exception as exc:
                print(f"Failed to send to {cid}: {exc}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
