import datetime
from pathlib import Path

from src.config import TIMEZONE
from src.services import reporting


class FakeBot:
    def __init__(self):
        self.calls = []

    async def send_photo(self, **kwargs):
        self.calls.append(kwargs)


def test_build_report_caption():
    stamp = datetime.datetime(2026, 5, 14, 10, 0, tzinfo=TIMEZONE)
    caption = reporting.build_report_caption(stamp)
    assert caption == "2026-yil 14-may holatiga ko'ra TV yo'nalishi bo'yicha savdo natijalari hisoboti."


def test_build_report_markup():
    markup = reporting.build_report_markup("https://example.com/app")
    assert markup is not None
    assert markup.inline_keyboard[0][0].url == "https://example.com/app"

