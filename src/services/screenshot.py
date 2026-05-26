"""Dashboard capture via the ScreenshotOne HTTP API.

Replaces the Playwright/Chromium backend so the bot runs on tiny hosts
(AlwaysData free, fly.io free, etc.) without ~300 MB of browser binaries.

Behaviour:
- One API call per send → one full-page PNG.
- Tries each configured ScreenshotOne account in order; on HTTP 402/429 or
  any network/other error, falls through to the next account.
- Returns a 1-item list of `CapturedSection` so existing reporting code
  (which iterates a list) keeps working unchanged.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

import aiohttp

from ..config import SCREENSHOTONE_ACCOUNTS, _ScreenshotOneAccount

logger = logging.getLogger(__name__)


def _account_short(a: _ScreenshotOneAccount) -> str:
    return a.label or (a.access_key[:6] + "…")

API_BASE = "https://api.screenshotone.com/take"

# Defaults tuned for the FOM dashboard:
#   - 1920x1080 viewport matches Playwright defaults so the layout is identical.
#   - full_page=true captures everything that scrolls.
#   - wait_until=networkidle waits for fetches to settle (Apps Script + Sheets API).
#   - delay gives the chart libs a beat to finish painting after data lands.
#   - block_* knobs strip cookie banners / ads if any sneak in.
DEFAULT_PARAMS: dict[str, str] = {
    "format": "png",
    "viewport_width": "1920",
    "viewport_height": "1080",
    "full_page": "true",
    # ScreenshotOne wait_until vocabulary: load | domcontentloaded |
    # networkidle0 (no in-flight requests for 500 ms) | networkidle2
    # (≤2 in-flight requests for 500 ms). Apps Script keeps polling the
    # Sheets backend, so networkidle2 is the realistic upper bound;
    # networkidle0 may never trigger.
    "wait_until": "networkidle2",
    # Extra wall-clock wait after wait_until fires, in seconds. Gives the
    # chart libs a beat to finish painting.
    "delay": "4",
    "block_ads": "true",
    "block_cookie_banners": "true",
    "block_trackers": "true",
    "cache": "false",
}

# HTTP statuses that indicate "this account is done, try the next one" rather
# than a permanent problem with the request or the target page.
#
# 400 is here too: ScreenshotOne uses 400 for both "request invalid for the
# whole world" (rare — we control the params) and account-specific errors
# like `signature_is_not_valid` or `unknown_access_key`, which a different
# account might not hit. Trying the next account costs one extra HTTP call.
RETRYABLE_STATUSES = {400, 402, 403, 408, 429, 500, 502, 503, 504}


@dataclass(frozen=True)
class CapturedSection:
    product_code: str
    title: str
    slug: str
    path: Path


def _sign(query: str, secret: str) -> str:
    return hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()


def _build_request_url(
    target_url: str,
    account: _ScreenshotOneAccount,
    extra: dict[str, str] | None = None,
) -> str:
    params = dict(DEFAULT_PARAMS)
    if extra:
        params.update(extra)
    params["url"] = target_url
    params["access_key"] = account.access_key
    query = urlencode(params, doseq=True)
    if account.secret_key:
        signature = _sign(query, account.secret_key)
        query = f"{query}&signature={signature}"
    return f"{API_BASE}?{query}"


async def _try_account(
    client: aiohttp.ClientSession,
    target_url: str,
    account: _ScreenshotOneAccount,
    out: Path,
    extra: dict[str, str] | None,
) -> tuple[bool, bool, str]:
    """Return (success, exhausted_or_retryable, message).

    `exhausted_or_retryable=True` means the caller should try the next account.
    """
    req_url = _build_request_url(target_url, account, extra)
    try:
        timeout = aiohttp.ClientTimeout(total=120)
        async with client.get(req_url, timeout=timeout) as resp:
            if resp.status == 200:
                content_type = (resp.headers.get("Content-Type") or "").lower()
                data = await resp.read()
                if "image" not in content_type and not data.startswith(b"\x89PNG"):
                    # ScreenshotOne sometimes returns JSON errors with HTTP 200
                    # when response_type doesn't match.
                    snippet = data[:300].decode("utf-8", "replace")
                    return False, True, f"non-image response: {snippet}"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(data)
                return True, False, "ok"

            body = (await resp.text())[:400]
            retryable = resp.status in RETRYABLE_STATUSES
            return False, retryable, f"HTTP {resp.status}: {body}"
    except asyncio.TimeoutError:
        return False, True, "timeout after 120s"
    except aiohttp.ClientError as exc:
        return False, True, f"client error: {exc}"
    except Exception as exc:  # pragma: no cover - defensive
        return False, True, f"unexpected: {exc!r}"


async def capture(
    url: str,
    out_path: str | Path,
    width: int = 1920,
    height: int = 1080,
) -> str:
    """Capture `url` to `out_path` using the first ScreenshotOne account that
    succeeds. Raises RuntimeError if every account fails.

    `width`/`height` override the default viewport for this single call.
    """
    if not SCREENSHOTONE_ACCOUNTS:
        raise RuntimeError(
            "No ScreenshotOne accounts configured. Set SCREENSHOTONE_ACCESS_KEY "
            "(and optionally SCREENSHOTONE_SECRET_KEY) in .env."
        )

    out = Path(out_path)
    extra = {"viewport_width": str(width), "viewport_height": str(height)}
    errors: list[str] = []

    async with aiohttp.ClientSession() as client:
        for account in SCREENSHOTONE_ACCOUNTS:
            label = _account_short(account)
            ok, retryable, msg = await _try_account(client, url, account, out, extra)
            if ok:
                logger.info("ScreenshotOne success via %s", label)
                return str(out)
            errors.append(f"{label}: {msg}")
            level = logging.WARNING if retryable else logging.ERROR
            logger.log(level, "ScreenshotOne account %s failed: %s", label, msg)
            if not retryable:
                # Permanent failure for this request (bad URL, signature reject):
                # trying other accounts won't change the outcome.
                break

    raise RuntimeError("All ScreenshotOne accounts failed. " + " | ".join(errors))


async def capture_sections(
    url: str,
    out_dir: str | Path,
    base_name: str,
    width: int = 1920,
    height: int = 1080,
) -> list[CapturedSection]:
    """Capture the dashboard as a single full-page screenshot.

    Returns a 1-item list so the reporting layer can keep iterating without
    changes. The returned item carries `product_code="FULL"`, which the
    caption builder maps to the daily "savdo natijalari" message.
    """
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{base_name}-01-full-screenshot.png"
    await capture(url, path, width=width, height=height)
    return [
        CapturedSection(
            product_code="FULL",
            title="FULL SCREENSHOT",
            slug="full-screenshot",
            path=path,
        )
    ]
