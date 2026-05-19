import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from aiogram import Bot
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup

from ..config import ENV_FILE, TARGET_URL, TIMEZONE, WEB_APP_URL
from .screenshot import CapturedSection


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

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCREENSHOTS_DIR = PROJECT_ROOT / "screenshots"

SECTION_LABELS = {
    "AA": "ArzonApteka",
    "FA": "F-Apteka",
    "FK": "F-Kassa",
    "FS": "F-Summary",
}


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
    return f"{date_text} holatiga ko'ra savdo natijalari hisoboti."


def build_report_markup(url: str) -> InlineKeyboardMarkup | None:
    if not url:
        return None

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Dashboardni ochish", url=url)]
        ]
    )


def build_section_caption(
    report_caption: str,
    product_code: str,
    fallback_title: str = "",
) -> str:
    code = (product_code or "").strip().upper()
    if code == "FULL":
        return report_caption

    label = SECTION_LABELS.get(code)
    if label:
        return f"{label} bo'yicha top 3ta o'rin."

    return fallback_title or report_caption


def delete_sent_screenshot(path: Path) -> bool:
    try:
        target = path.resolve()
        target.relative_to(SCREENSHOTS_DIR.resolve())
    except (OSError, ValueError):
        return False

    try:
        target.unlink(missing_ok=True)
        return True
    except OSError:
        return False


async def send_report(bot: Bot, chat_id: int, images: list[CapturedSection], now: datetime.datetime | None = None) -> dict:
    url = sync_web_app_url_env()

    caption = build_report_caption(now=now)

    url_with_date = url
    if url and now is not None:
        date_str = now.astimezone(TIMEZONE).strftime("%Y-%m-%d")
        parsed = urlparse(url)
        q = dict(parse_qsl(parsed.query))
        q.update({"date": date_str})
        parsed = parsed._replace(query=urlencode(q))
        url_with_date = urlunparse(parsed)

    reply_markup = build_report_markup(url_with_date)

    sent = []
    failed = []
    deleted = []
    cleanup_failed = []

    for index, image in enumerate(images, start=1):
        try:
            photo = FSInputFile(image.path, filename=image.path.name)
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=build_section_caption(caption, image.product_code, image.title),
                reply_markup=reply_markup if index == 1 else None,
            )
            sent.append({"title": image.title, "path": str(image.path)})
            if delete_sent_screenshot(image.path):
                deleted.append(str(image.path))
            elif image.path.exists():
                cleanup_failed.append(str(image.path))
        except Exception as exc:
            failed.append(
                {
                    "chat_id": chat_id,
                    "title": image.title,
                    "path": str(image.path),
                    "error": str(exc),
                }
            )

    return {
        "caption": caption,
        "url": url_with_date,
        "chat_id": chat_id,
        "sent": sent,
        "failed": failed,
        "deleted": deleted,
        "cleanup_failed": cleanup_failed,
    }
