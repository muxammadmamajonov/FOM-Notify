#!/usr/bin/env python3
import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.types import InputFile
from pathlib import Path

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    print("No TELEGRAM_BOT_TOKEN in env")
    raise SystemExit(1)

INITIAL_SUBSCRIBERS = os.getenv("INITIAL_SUBSCRIBERS", "")
if INITIAL_SUBSCRIBERS:
    chat_ids = [int(x.strip()) for x in INITIAL_SUBSCRIBERS.split(",") if x.strip()]
else:
    chat_ids = []

img = Path("screenshots/run-once.png")
if not img.exists():
    print("Screenshot not found:", img)
    raise SystemExit(1)

async def main():
    bot = Bot(TOKEN)
    try:
        for cid in chat_ids:
            try:
                photo = InputFile(path=str(img))
                await bot.send_photo(chat_id=cid, photo=photo, caption="Automated test screenshot (Playwright)")
                print(f"Sent to {cid}")
            except Exception as e:
                print(f"Failed to send to {cid}: {e}")
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
