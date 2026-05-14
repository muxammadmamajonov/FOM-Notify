import asyncio
from pathlib import Path

def test_capture(tmp_path: Path):
    # simple smoke test for the capture function
    from src.services.screenshot import capture

    out = tmp_path / "shot.png"

    asyncio.run(capture("https://example.com", str(out)))

    assert out.exists()
