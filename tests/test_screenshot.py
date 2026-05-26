"""Unit tests for the ScreenshotOne URL builder.

A real-API smoke test against ScreenshotOne is opt-in to avoid burning
free-tier quota in CI / local dev:

    TEST_REAL_SCREENSHOTONE=1 venv/bin/python -m pytest tests/test_screenshot.py
"""
import asyncio
import hashlib
import hmac
import os
from urllib.parse import parse_qs, urlparse

import pytest

from src.config import _ScreenshotOneAccount
from src.services import screenshot


def test_build_request_url_includes_access_key_and_url():
    account = _ScreenshotOneAccount(access_key="ak123", secret_key="", label="t1")
    url = screenshot._build_request_url("https://example.com/dash", account)

    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    assert parsed.netloc == "api.screenshotone.com"
    assert parsed.path == "/take"
    assert qs["access_key"] == ["ak123"]
    assert qs["url"] == ["https://example.com/dash"]
    assert qs["format"] == ["png"]
    assert qs["full_page"] == ["true"]
    assert "signature" not in qs  # no secret -> no signing


def test_build_request_url_signs_when_secret_provided():
    account = _ScreenshotOneAccount(
        access_key="ak123", secret_key="super-secret", label="t2"
    )
    url = screenshot._build_request_url("https://example.com/dash", account)

    parsed = urlparse(url)
    # The signature must be the HMAC-SHA256 of the unsigned query.
    unsigned, sep, sig_part = parsed.query.rpartition("&signature=")
    assert sep == "&signature="
    expected = hmac.new(
        b"super-secret", unsigned.encode(), hashlib.sha256
    ).hexdigest()
    assert sig_part == expected


def test_build_request_url_extra_overrides_defaults():
    account = _ScreenshotOneAccount(access_key="ak", secret_key="", label="t3")
    url = screenshot._build_request_url(
        "https://example.com",
        account,
        extra={"viewport_width": "800", "viewport_height": "600"},
    )
    qs = parse_qs(urlparse(url).query)
    assert qs["viewport_width"] == ["800"]
    assert qs["viewport_height"] == ["600"]


def test_capture_raises_when_no_accounts_configured(monkeypatch, tmp_path):
    monkeypatch.setattr(screenshot, "SCREENSHOTONE_ACCOUNTS", [])

    async def run():
        with pytest.raises(RuntimeError, match="No ScreenshotOne accounts"):
            await screenshot.capture("https://example.com", tmp_path / "x.png")

    asyncio.run(run())


@pytest.mark.skipif(
    os.getenv("TEST_REAL_SCREENSHOTONE") != "1",
    reason="Set TEST_REAL_SCREENSHOTONE=1 to hit the live ScreenshotOne API.",
)
def test_capture_against_live_screenshotone(tmp_path):
    from src.config import SCREENSHOTONE_ACCOUNTS, TARGET_URL

    assert SCREENSHOTONE_ACCOUNTS, "Configure SCREENSHOTONE_ACCESS_KEY in .env."
    assert TARGET_URL, "Configure TARGET_URL in .env."

    out = tmp_path / "live.png"
    asyncio.run(screenshot.capture(TARGET_URL, out))

    assert out.exists()
    assert out.stat().st_size > 1000
    assert out.read_bytes().startswith(b"\x89PNG")
