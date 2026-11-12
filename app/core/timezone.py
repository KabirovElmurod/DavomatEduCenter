"""Vaqt zonasi yordamchilari (roadmap 8.8)

'Bugun' doim Asia/Tashkent bo'yicha hisoblanadi,
bazada esa UTC saqlanadi.
"""
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

TASHKENT_TZ = ZoneInfo("Asia/Tashkent")


def today_tashkent() -> date:
    """Hozirgi sana (Asia/Tashkent bo'yicha)"""
    return datetime.now(TASHKENT_TZ).date()


def tashkent_day_bounds_utc(day: date) -> tuple[datetime, datetime]:
    """Berilgan Tashkent sanasining UTC oralig'i [start, end)"""
    start_local = datetime.combine(day, time.min, tzinfo=TASHKENT_TZ)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def now_utc() -> datetime:
    return datetime.now(UTC)
