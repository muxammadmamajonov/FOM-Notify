from aiogram import Router
from aiogram.types import Message, BotCommand
from aiogram.filters import Command

from ..services import reporting, screenshot
from ..config import TARGET_URL, TIMEZONE
from pathlib import Path
import datetime

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    commands = [
        BotCommand(command="report", description="Send current dashboard screenshot."),
        BotCommand(command="stop", description="Stop subscriber delivery."),
        BotCommand(command="start", description="Show this message."),
    ]
    try:
        await message.bot.set_my_commands(commands)
    except Exception:
        pass

    await message.reply("This bot now sends dashboard screenshots only to the configured group.")


@router.message(Command("report"))
async def cmd_report(message: Message):
    chat_id = message.chat.id
    stamp = datetime.datetime.now(TIMEZONE).strftime("%Y%m%d-%H%M%S")
    base_name = f"manual-{stamp}"
    try:
        if not TARGET_URL:
            await message.reply("TARGET_URL is not configured.")
            return

        images = await screenshot.capture_sections(TARGET_URL, Path("screenshots"), base_name)
    except Exception as e:
        await message.reply(f"Capture failed: {e}")
        return

    result = await reporting.send_report(message.bot, chat_id, images)
    success_count = len(result["sent"])
    failed_count = len(result["failed"])

    if failed_count:
        failure_lines = "\n".join(
            f"{item['title']}: {item['error']}" for item in result["failed"][:5]
        )
        await message.reply(
            f"Report delivery finished.\n"
            f"Chat: {chat_id}\n"
            f"Images: {len(images)}\n"
            f"Sent: {success_count}\n"
            f"Failed: {failed_count}\n"
            f"{failure_lines}"
        )
        return

    await message.reply(
        f"Report sent successfully.\n"
        f"Images: {len(images)}\n"
        f"Sent: {success_count}\n"
        f"Link: {result['url'] or 'not set'}"
    )


@router.message(Command("stop"))
async def cmd_stop(message: Message):
    await message.reply("Subscriber-based delivery is disabled. Reports are sent only to the configured group.")
