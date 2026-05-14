from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from ..config import ADMIN_CHAT_ID, DB_PATH, TARGET_URL
from ..services import reporting, screenshot, subscriptions
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

    result = await reporting.send_report(message.bot, subs, out)
    success_count = len(result["sent_to"])
    failed_count = len(result["failed"])

    if failed_count:
        failure_lines = "\n".join(
            f"{item['chat_id']}: {item['error']}" for item in result["failed"][:5]
        )
        await message.reply(
            f"Report delivery finished.\n"
            f"Sent: {success_count}\n"
            f"Failed: {failed_count}\n"
            f"{failure_lines}"
        )
        return

    await message.reply(
        f"Report sent successfully.\nSent: {success_count}\nLink: {result['url'] or 'not set'}"
    )
