from aiogram import F, Router
from aiogram.types import Message
from aiogram.filters import Command
from ..config import ADMIN_CHAT_ID, GROUP_CHAT_ID, SCREENSHOTS_DIR, TARGET_URL, TIMEZONE
from ..services import reporting, screenshot
import datetime

router = Router()


@router.message(Command("run_screenshot"))
@router.message(F.text.casefold() == "run screenshot")
async def run_screenshot(message: Message):
    if not ADMIN_CHAT_ID or not message.from_user or message.from_user.id != ADMIN_CHAT_ID:
        await message.reply("Unauthorized.")
        return
    if not GROUP_CHAT_ID:
        await message.reply("GROUP_CHAT_ID is not configured.")
        return

    if not TARGET_URL:
        await message.reply("TARGET_URL is not configured.")
        return

    now = datetime.datetime.now(TIMEZONE)
    stamp = now.strftime("%Y%m%d-%H%M%S")
    base_name = f"manual-{stamp}"
    try:
        images = await screenshot.capture_sections(TARGET_URL, SCREENSHOTS_DIR, base_name)
    except Exception as e:
        await message.reply(f"Capture failed: {e}")
        return

    result = await reporting.send_report(message.bot, GROUP_CHAT_ID, images, now=now)

    if result["failed"]:
        failure_lines = "\n".join(
            f"{item['title']}: {item['error']}" for item in result["failed"][:5]
        )
        await message.reply(f"Report delivery failed:\n{failure_lines}")
