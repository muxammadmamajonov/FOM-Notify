#!/usr/bin/env python3
"""Dev helper: POST a one-shot screenshot (default: screenshots/run-once.png)
to one or more Telegram chats listed in INITIAL_SUBSCRIBERS.

Uses only the standard library so there's no extra dependency on `requests`.
Run from anywhere — the screenshot path is resolved against the project root.

Example:
    INITIAL_SUBSCRIBERS=123,-100456 venv/bin/python tools/send_screenshot_http.py
"""
import json
import mimetypes
import os
import sys
import urllib.request
import uuid
from pathlib import Path

# Make `from src.config import ...` work no matter where this script is run from.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    print("No TELEGRAM_BOT_TOKEN in env")
    raise SystemExit(1)

raw_subs = os.getenv("INITIAL_SUBSCRIBERS", "")
chat_ids = [int(x.strip()) for x in raw_subs.split(",") if x.strip()]
if not chat_ids:
    print("INITIAL_SUBSCRIBERS is empty; nothing to do.")
    raise SystemExit(0)

img = PROJECT_ROOT / "screenshots" / "run-once.png"
if not img.exists():
    print("Screenshot not found:", img)
    raise SystemExit(1)


def post_photo(chat_id: int, photo: Path, caption: str) -> dict:
    boundary = uuid.uuid4().hex
    sep = f"--{boundary}".encode()
    end = f"--{boundary}--".encode()
    mime = mimetypes.guess_type(photo.name)[0] or "application/octet-stream"

    body = b"\r\n".join(
        [
            sep,
            b'Content-Disposition: form-data; name="chat_id"',
            b"",
            str(chat_id).encode(),
            sep,
            b'Content-Disposition: form-data; name="caption"',
            b"",
            caption.encode("utf-8"),
            sep,
            f'Content-Disposition: form-data; name="photo"; filename="{photo.name}"'.encode(),
            f"Content-Type: {mime}".encode(),
            b"",
            photo.read_bytes(),
            end,
            b"",
        ]
    )

    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


for cid in chat_ids:
    try:
        result = post_photo(cid, img, "Automated test screenshot (Playwright)")
        print(f"Sent to {cid}: ok={result.get('ok')}")
    except Exception as exc:
        print(f"Failed to send to {cid}: {exc}")
