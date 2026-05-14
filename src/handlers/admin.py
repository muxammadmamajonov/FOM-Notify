from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from ..config import ADMIN_CHAT_ID, DB_PATH, TARGET_URL
from ..services import screenshot, subscriptions
from pathlib import Path
import datetime

router = Router()

@router.message(Command("run_screenshot"))
async def run_screenshot(message: Message):
    if ADMIN_CHAT_ID and message.from_user and message.from_user.id != ADMIN_CHAT_ID:
        await message.reply("Unauthorized.")
        return

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = Path("screenshots") / f"manual-{stamp}.png"
    try:
        await screenshot.capture(TARGET_URL, str(out))
    except Exception as e:
        await message.reply(f"Capture failed: {e}")
        return

    subs = await subscriptions.list_subscribers(DB_PATH)
    if not subs:
        await message.reply("No subscribers to send to.")
        return

    with open(out, "rb") as f:
        data = f.read()
        for chat_id in subs:
            try:
                await message.bot.send_photo(chat_id, data)
            except Exception:
                pass

    await message.reply("Screenshot sent to subscribers.")
