import datetime
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup

from ..config import ENV_FILE, TARGET_URL, TIMEZONE, WEB_APP_URL


UZBEK_MONTHS = (
    "yanvar",
    "fevral",
    "mart",
    "aprel",
    "may",
    "iyun",
    "iyul",
    "avgust",
    "sentabr",
    "oktabr",
    "noyabr",
    "dekabr",
)


def get_effective_web_app_url() -> str:
    return (WEB_APP_URL or TARGET_URL or "").strip()


def sync_web_app_url_env() -> str:
    url = get_effective_web_app_url()
    if not url:
        return ""

    existing = []
    if ENV_FILE.exists():
        existing = ENV_FILE.read_text(encoding="utf-8").splitlines()

    updated = []
    found = False
    for line in existing:
        if line.startswith("WEB_APP_URL="):
            updated.append(f"WEB_APP_URL={url}")
            found = True
        else:
            updated.append(line)

    if not found:
        updated.append(f"WEB_APP_URL={url}")

    ENV_FILE.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8")
    return url


def build_report_caption(now: datetime.datetime | None = None) -> str:
    if now is None:
        now = datetime.datetime.now(TIMEZONE)

    date_text = f"{now.year}-yil {now.day}-{UZBEK_MONTHS[now.month - 1]}"
    return f"{date_text} holatiga ko'ra TV yo'nalishi bo'yicha savdo natijalari hisoboti."


def build_report_markup(url: str) -> InlineKeyboardMarkup | None:
    if not url:
        return None

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Dashboardni ochish", url=url)]
        ]
    )


async def send_report(bot: Bot, chat_ids: list[int], image_path: str | Path) -> dict:
    url = sync_web_app_url_env()
    caption = build_report_caption()
    reply_markup = build_report_markup(url)
    image = Path(image_path)

    sent_to = []
    failed = []
    unique_chat_ids = list(dict.fromkeys(chat_ids))

    for chat_id in unique_chat_ids:
        try:
            photo = FSInputFile(image, filename=image.name)
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                reply_markup=reply_markup,
            )
            sent_to.append(chat_id)
        except Exception as exc:
            failed.append({"chat_id": chat_id, "error": str(exc)})

    return {
        "caption": caption,
        "url": url,
        "sent_to": sent_to,
        "failed": failed,
    }
