import asyncio
import datetime

from src.config import TIMEZONE
from src.services import reporting
from src.services.screenshot import CapturedSection


class FakeBot:
    def __init__(self):
        self.calls = []

    async def send_photo(self, **kwargs):
        self.calls.append(kwargs)


def test_build_report_caption():
    stamp = datetime.datetime(2026, 5, 14, 10, 0, tzinfo=TIMEZONE)
    caption = reporting.build_report_caption(stamp)
    assert caption == "2026-yil 14-may holatiga ko'ra savdo natijalari hisoboti."


def test_build_report_markup():
    markup = reporting.build_report_markup("https://example.com/app")
    assert markup is not None
    assert markup.inline_keyboard[0][0].url == "https://example.com/app"


def test_build_section_caption():
    report_caption = "2026-yil 14-may holatiga ko'ra savdo natijalari hisoboti."
    assert (
        reporting.build_section_caption(report_caption, "FULL", "FULL SCREENSHOT")
        == "2026-yil 14-may holatiga ko'ra savdo natijalari hisoboti."
    )
    assert (
        reporting.build_section_caption(report_caption, "AA", "ArzonApteka")
        == "ArzonApteka bo'yicha top 3ta o'rin."
    )


def test_send_report_single_full_image_attaches_button_and_cleans_up(tmp_path, monkeypatch):
    """Current backend (ScreenshotOne) returns one FULL image per send."""

    async def run():
        bot = FakeBot()
        screenshots_dir = tmp_path / "screenshots"
        screenshots_dir.mkdir()
        monkeypatch.setattr(reporting, "SCREENSHOTS_DIR", screenshots_dir)

        path = screenshots_dir / "01-full.png"
        path.write_bytes(b"fake-png")
        images = [
            CapturedSection(
                product_code="FULL",
                title="FULL SCREENSHOT",
                slug="full-screenshot",
                path=path,
            )
        ]

        result = await reporting.send_report(bot, -100123, images)
        expected_caption = reporting.build_report_caption()

        assert len(bot.calls) == 1
        assert bot.calls[0]["chat_id"] == -100123
        assert bot.calls[0]["caption"] == expected_caption
        # The first (and only) message gets the "Dashboardni ochish" button.
        assert bot.calls[0]["reply_markup"] is not None
        assert len(result["sent"]) == 1
        assert result["failed"] == []
        assert len(result["deleted"]) == 1
        assert result["cleanup_failed"] == []
        assert not path.exists()

    asyncio.run(run())


def test_send_report_still_handles_multi_image_payload(tmp_path, monkeypatch):
    """Reporting layer remains generic in case we re-enable per-card capture."""

    async def run():
        bot = FakeBot()
        screenshots_dir = tmp_path / "screenshots"
        screenshots_dir.mkdir()
        monkeypatch.setattr(reporting, "SCREENSHOTS_DIR", screenshots_dir)

        images = []
        for index, (code, title) in enumerate(
            [
                ("FULL", "FULL SCREENSHOT"),
                ("AA", "ArzonApteka"),
                ("FA", "F-Apteka"),
                ("FK", "F-Kassa"),
                ("FS", "F-Summary"),
            ],
            start=1,
        ):
            path = screenshots_dir / f"{index}.png"
            path.write_bytes(b"fake")
            images.append(
                CapturedSection(
                    product_code=code,
                    title=title,
                    slug=title.lower().replace(" ", "-"),
                    path=path,
                )
            )

        result = await reporting.send_report(bot, -100123, images)

        assert len(bot.calls) == 5
        # Only the first message carries the inline button.
        assert bot.calls[0]["reply_markup"] is not None
        assert bot.calls[1]["reply_markup"] is None
        assert bot.calls[1]["caption"] == "ArzonApteka bo'yicha top 3ta o'rin."
        assert len(result["sent"]) == 5
        assert result["failed"] == []

    asyncio.run(run())
