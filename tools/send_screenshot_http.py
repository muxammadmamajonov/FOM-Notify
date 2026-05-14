#!/usr/bin/env python3
import os
from dotenv import load_dotenv
import requests
from pathlib import Path

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    print("No TELEGRAM_BOT_TOKEN in env")
    raise SystemExit(1)

INITIAL_SUBSCRIBERS = os.getenv("INITIAL_SUBSCRIBERS", "")
if INITIAL_SUBSCRIBERS:
    chat_ids = [int(x.strip()) for x in INITIAL_SUBSCRIBERS.split(",") if x.strip()]
else:
    chat_ids = []

img = Path("screenshots/run-once.png")
if not img.exists():
    print("Screenshot not found:", img)
    raise SystemExit(1)

for cid in chat_ids:
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    with img.open("rb") as f:
        files = {"photo": f}
        data = {"chat_id": str(cid), "caption": "Automated test screenshot (Playwright)"}
        try:
            r = requests.post(url, files=files, data=data, timeout=60)
            r.raise_for_status()
            print(f"Sent to {cid}:", r.json().get("ok"))
        except Exception as e:
            print(f"Failed to send to {cid}: {e}")
