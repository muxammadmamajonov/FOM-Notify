from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from ..services import subscriptions
from ..config import DB_PATH

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    await subscriptions.add_subscriber(DB_PATH, message.chat.id)
    await message.reply("Subscribed to daily screenshots (10:00 Asia/Tashkent).")

@router.message(Command("stop"))
async def cmd_stop(message: Message):
    await subscriptions.remove_subscriber(DB_PATH, message.chat.id)
    await message.reply("Unsubscribed from daily screenshots.")
