# FOM-Notify — Daily Dashboard Telegram Bot

`aiogram`-based Telegram bot that captures the FOM Apps Script dashboard
every day at **10:00 Asia/Tashkent** and posts it to one Telegram group.

The screenshot backend is **[ScreenshotOne](https://screenshotone.com)** (HTTP
API). No Playwright / Chromium installed, so the project runs comfortably on
free shared hosting like AlwaysData (~5 MB instead of ~300 MB).

Files of interest:
- `src/main.py` — entrypoint (`python -m src.main`)
- `src/config.py` — env + project paths + ScreenshotOne account loader
- `src/services/screenshot.py` — ScreenshotOne client + multi-account failover
- `src/services/scheduler.py` — APScheduler triggers (09:30 + 10:00 Tashkent)
- `src/services/reporting.py` — caption + Telegram delivery
- `src/handlers/` — `/start`, `/report`, `/run_screenshot` commands

Report behaviour:
- One full-page screenshot per send, posted as a single Telegram photo with
  the daily Uzbek caption + a "Dashboardni ochish" inline button.
- Two scheduled triggers per day: 09:30 (Apps Script auto-deploy, optional)
  and 10:00 (capture + send).
- Manual triggers: `/report` (any chat the bot is in) and `/run_screenshot`
  (admin-only, sends to `GROUP_CHAT_ID`).

---

## Local development

### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
# edit .env — at minimum: TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID, GROUP_CHAT_ID,
# TARGET_URL, SCREENSHOTONE_ACCESS_KEY, SCREENSHOTONE_SECRET_KEY
python -m src.main
```

### One-shot capture (no bot needed)

```bash
RUN_ONCE=1 python -m src.main
ls screenshots/   # should contain one PNG
```

### Tests

```bash
venv/bin/python -m pytest tests/
```

A live-API smoke test is opt-in (uses real ScreenshotOne quota — keep it off
in normal runs):

```bash
TEST_REAL_SCREENSHOTONE=1 venv/bin/python -m pytest tests/test_screenshot.py
```

---

## ScreenshotOne — multi-account failover

`src/services/screenshot.py` tries up to **four** ScreenshotOne accounts in
order. On HTTP 402 (quota exhausted), 429 (rate limited), any 5xx, or any
network error it falls through to the next account.

`.env` keys:

```dotenv
SCREENSHOTONE_ACCESS_KEY=primary_key
SCREENSHOTONE_SECRET_KEY=primary_secret      # optional; only needed if you
                                             # enable "Signed requests only"
                                             # on the ScreenshotOne dashboard
SCREENSHOTONE_ACCESS_KEY_2=backup_key
SCREENSHOTONE_SECRET_KEY_2=backup_secret
# … _3 and _4 also supported
```

**Free-tier math:** 100 screenshots/month per account. With one screenshot per
send and the daily 10:00 trigger, you spend 30/mo on the daily job, leaving
~70 for manual `/report` calls. Add a second account and you have 170/mo of
manual headroom.

If every configured account fails, `/report` replies with `Capture failed: …`
and the daily run prints the combined error list to the bot's logs.

---

## Deploy on AlwaysData

AlwaysData is a Linux shared host; the bot runs as a **long-running user
program**. Steps assume SSH is enabled on your account.

### 1. Clone

```bash
ssh <account>@ssh-<account>.alwaysdata.net
git clone https://github.com/muxammadmamajonov/FOM-Notify.git
cd FOM-Notify
```

### 2. Python venv + deps

Pick Python 3.10+ in the AlwaysData panel (*Environment → Python*), then:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

No `playwright install` step — the HTTP backend has no native dependencies.

### 3. Configure `.env`

```bash
cp .env.example .env
nano .env
```

Required fields: `TELEGRAM_BOT_TOKEN`, `ADMIN_CHAT_ID`, `GROUP_CHAT_ID`,
`TARGET_URL`, `SCREENSHOTONE_ACCESS_KEY`, `SCREENSHOTONE_SECRET_KEY`.

### 4. Smoke-test

```bash
RUN_ONCE=1 python -m src.main
ls screenshots/                       # one PNG
file screenshots/*.png                # should say "PNG image data, 1920 x …"
```

If you see `All ScreenshotOne accounts failed: …`, the error message will
tell you which account replied with what HTTP status. Fix the key or top up
the quota before continuing.

### 5. Register the long-running process

In the AlwaysData panel: **Tools → Processes → Add a process** (or
**Sites → Add a site → User program** in older UIs):

| Field             | Value                                                                 |
| ----------------- | --------------------------------------------------------------------- |
| Command           | `/home/<account>/FOM-Notify/venv/bin/python -m src.main`              |
| Working directory | `/home/<account>/FOM-Notify`                                          |
| Environment       | *(none — `.env` is read from the working directory)*                  |
| Restart on exit   | **Yes**                                                               |

Save and start.

### 6. Verify

```bash
ps -fu <account> | grep src.main      # one python process
```

In Telegram, send `/start` then `/report` to the bot. The bot replies, then
posts a screenshot to the chat. If you see `Capture failed: …`, copy the
message back here.

### 7. Updates

```bash
ssh <account>@ssh-<account>.alwaysdata.net
cd ~/FOM-Notify
git pull
source venv/bin/activate
pip install -r requirements.txt       # only when requirements change
# Restart the process from the AlwaysData panel.
```

---

## Migrating off Playwright (if you deployed an older revision)

Earlier revisions of this repo used Playwright + Chromium. To reclaim the
~300 MB of browser binaries on AlwaysData:

```bash
# Wipe the cached Chromium / WebKit / Firefox builds
rm -rf ~/.cache/ms-playwright
rm -rf ~/.cache/playwright

# Drop the Python package from the venv
source ~/FOM-Notify/venv/bin/activate
pip uninstall -y playwright
deactivate

# Confirm
du -sh ~/.cache/* 2>/dev/null         # ms-playwright should be gone
du -sh ~/FOM-Notify/venv              # venv should be a few MB
```

If `du` still shows a `chromium-*` directory anywhere under `~/.cache`, delete
it manually.

---

## Apps Script auto-update (optional)

If you want the 09:30 auto-deploy of `Index.html` / `Code.gs`, install Node.js
+ `clasp` on the AlwaysData account, log in, set `APPS_SCRIPT_AUTO_UPDATE=1`
in `.env`, and provide `CLASP_DEPLOYMENT_ID`. Otherwise leave
`APPS_SCRIPT_AUTO_UPDATE=0` — the scheduler will skip cleanly.

---

## Windows-only autostart (legacy)

The `tools/*.ps1` scripts wire the bot into Windows Task Scheduler. Not used
on AlwaysData; safe to ignore on Linux.

```powershell
powershell -ExecutionPolicy Bypass -File tools\install_autostart.ps1 -Action Install
powershell -ExecutionPolicy Bypass -File tools\install_autostart.ps1 -Action Status
powershell -ExecutionPolicy Bypass -File tools\install_autostart.ps1 -Action Restart
```

---

## Troubleshooting

| Symptom | Likely cause / fix |
| --- | --- |
| `Capture failed: All ScreenshotOne accounts failed:` | All keys exhausted or invalid. Check `SCREENSHOTONE_ACCESS_KEY*` in `.env`. |
| `Capture failed: … HTTP 401: …signature…` | Account requires signed requests but `SECRET_KEY` is missing or wrong. |
| `Capture failed: … HTTP 402: …` | That account's free-tier quota is gone for the month. Add a backup account. |
| `Dashboard did not finish loading` (legacy Playwright error) | You're running an old revision. `git pull` and restart. |
| Bot starts but `/report` does nothing | Check the AlwaysData process logs for the actual error; paste it in an issue. |
