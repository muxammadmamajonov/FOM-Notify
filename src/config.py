import os
from pathlib import Path
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

# Project root — resolved from this file's location so the bot works no matter
# where the process is launched from (CLI, systemd, AlwaysData supervisor, etc.).
PROJECT_ROOT = Path(__file__).resolve().parents[1]

ENV_FILE = PROJECT_ROOT / ".env"
# override=True so values in .env win over the shell. Important on shared
# hosts (e.g. AlwaysData) where TZ is preset to ":/etc/localtime" — a Unix
# `tzset` convention that ZoneInfo cannot parse.
load_dotenv(ENV_FILE, override=True)

SCREENSHOTS_DIR = PROJECT_ROOT / "screenshots"
DATA_DIR = PROJECT_ROOT / "data"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID")) if os.getenv("ADMIN_CHAT_ID") else None
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID")) if os.getenv("GROUP_CHAT_ID") else None
TARGET_URL = os.getenv("TARGET_URL")
WEB_APP_URL = os.getenv("WEB_APP_URL") or TARGET_URL
def _resolve_tz(raw: str | None) -> str:
    """Coerce a TZ env value into something ZoneInfo can load.

    Unix `tzset(3)` understands forms like ":/etc/localtime" (leading colon
    means "treat the rest as a TZif file path"), but Python's `zoneinfo`
    only accepts IANA names like "Asia/Tashkent". Strip the colon prefix,
    fall back to the default if what's left is empty or an absolute path.
    """
    default = "Asia/Tashkent"
    value = (raw or "").strip()
    if value.startswith(":"):
        value = value[1:]
    if not value or value.startswith("/"):
        return default
    return value


TZ = _resolve_tz(os.getenv("TZ"))
TIMEZONE = ZoneInfo(TZ)

# DB path: honour DB_PATH if set (relative or absolute), otherwise default
# under the project's data/ dir.
_db_env = os.getenv("DB_PATH")
if _db_env:
    _db_path = Path(_db_env)
    DB_PATH = str(_db_path if _db_path.is_absolute() else PROJECT_ROOT / _db_path)
else:
    DB_PATH = str(DATA_DIR / "subscribers.db")

APPS_SCRIPT_AUTO_UPDATE = os.getenv("APPS_SCRIPT_AUTO_UPDATE", "0") == "1"
CLASP_WORKDIR = os.getenv("CLASP_WORKDIR", str(PROJECT_ROOT))
CLASP_DEPLOYMENT_ID = os.getenv("CLASP_DEPLOYMENT_ID", "").strip()

RUN_ONCE = os.getenv("RUN_ONCE", "0") == "1"
# Run Playwright headless by default. Set `HEADLESS=0` in .env to run headful.
_headless_raw = os.getenv("HEADLESS", "1").lower()
HEADLESS = _headless_raw in ("1", "true", "yes")
