import asyncio
import os
from pathlib import Path

import pytest


# This is a real integration test: it launches a Chromium browser and hits the
# live Apps Script dashboard. It is opt-in to keep the default test run fast
# and deterministic on machines that don't have Playwright browsers installed.
#
# Enable with:  TEST_REAL_DASHBOARD=1 venv/bin/python -m pytest tests/test_screenshot.py
@pytest.mark.skipif(
    os.getenv("TEST_REAL_DASHBOARD") != "1",
    reason="Set TEST_REAL_DASHBOARD=1 to run the live-browser smoke test.",
)
def test_capture_against_live_dashboard(tmp_path: Path):
    from src.config import TARGET_URL
    from src.services.screenshot import capture

    assert TARGET_URL, "TARGET_URL must be configured in .env to run this test."

    out = tmp_path / "shot.png"
    asyncio.run(capture(TARGET_URL, str(out)))

    assert out.exists()
    assert out.stat().st_size > 0
