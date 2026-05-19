from aiogram import F, Router
from aiogram.types import Message
from aiogram.filters import Command
from ..config import ADMIN_CHAT_ID, GROUP_CHAT_ID, TARGET_URL
from ..services import reporting, screenshot
from pathlib import Path
import datetime

router = Router()


@router.message(Command("run_screenshot"))
@router.message(F.text.casefold() == "run screenshot")
async def run_screenshot(message: Message):
    if ADMIN_CHAT_ID and message.from_user and message.from_user.id != ADMIN_CHAT_ID:
        await message.reply("Unauthorized.")
        return
    if not GROUP_CHAT_ID:
        await message.reply("GROUP_CHAT_ID is not configured.")
        return

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    base_name = f"manual-{stamp}"
    try:
        images = await screenshot.capture_sections(TARGET_URL, Path("screenshots"), base_name)
    except Exception as e:
        await message.reply(f"Capture failed: {e}")
        return

    result = await reporting.send_report(message.bot, GROUP_CHAT_ID, images)
    success_count = len(result["sent"])
    failed_count = len(result["failed"])

    if failed_count:
        failure_lines = "\n".join(
            f"{item['title']}: {item['error']}" for item in result["failed"][:5]
        )
        await message.reply(
            f"Report delivery finished.\n"
            f"Group: {GROUP_CHAT_ID}\n"
            f"Images: {len(images)}\n"
            f"Sent: {success_count}\n"
            f"Failed: {failed_count}\n"
            f"{failure_lines}"
        )
        return

    await message.reply(
        f"Report sent successfully.\n"
        f"Group: {GROUP_CHAT_ID}\n"
        f"Images: {len(images)}\n"
        f"Sent: {success_count}\n"
        f"Link: {result['url'] or 'not set'}"
    )
