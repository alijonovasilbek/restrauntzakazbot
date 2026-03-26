from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from bot.config import settings


def today_local_date():
    return datetime.now(ZoneInfo(settings.tz)).date()
