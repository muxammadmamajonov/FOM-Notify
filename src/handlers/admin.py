from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from ..config import ADMIN_CHAT_ID, DB_PATH, INITIAL_SUBSCRIBERS, TARGET_URL
from ..services import reporting, screenshot, subscriptions
from pathlib import Path
import datetime
import struct

router = Router()


def _png_size(path: Path):
    try:
        data = path.read_bytes()
        if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
            w, h = struct.unpack(">II", data[16:24])
            return w, h
    except Exception:
        pass
    return "?", "?"


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
    targets = list(dict.fromkeys(subs + INITIAL_SUBSCRIBERS))
    if message.chat and message.chat.id not in targets:
        targets.append(message.chat.id)
    if not targets:
        await message.reply("No subscribers to send to.")
        return

    result = await reporting.send_report(message.bot, targets, out)
    success_count = len(result["sent_to"])
    failed_count = len(result["failed"])
    width, height = _png_size(out)

    if failed_count:
        failure_lines = "\n".join(
            f"{item['chat_id']}: {item['error']}" for item in result["failed"][:5]
        )
        await message.reply(
            f"Report delivery finished.\n"
            f"Targets: {len(targets)}\n"
            f"Sent: {success_count}\n"
            f"Failed: {failed_count}\n"
            f"Image: {width}x{height}\n"
            f"{failure_lines}"
        )
        return

    await message.reply(
        f"Report sent successfully.\n"
        f"Targets: {len(targets)}\n"
        f"Sent: {success_count}\n"
        f"Image: {width}x{height}\n"
        f"Sent to: {', '.join(map(str, result['sent_to']))}\n"
        f"Link: {result['url'] or 'not set'}"
    )
