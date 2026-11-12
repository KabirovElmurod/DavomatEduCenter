"""
Notification yuborish servisi (roadmap 9.1-9.8)

- Atomik claim: UPDATE ... WHERE status='pending' AND attempts=N
  (optimistic locking — ikki worker bir xil notification'ni olmaydi)
- Xabar matni shakllantirish
- Redis rate limit: global <= 25/s, chatga <= 1/s
- 429 -> kutib qayta urinish; 403 -> blocked; tarmoq xatosi -> backoff, max 5
"""
import time
from datetime import UTC, datetime, timedelta

import redis.asyncio as aioredis
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.timezone import TASHKENT_TZ
from app.models.attendance import Attendance
from app.models.base import AttendanceStatus, NotificationStatus
from app.models.group import Group
from app.models.lesson import Lesson
from app.models.notification import Notification
from app.models.student import Student
from app.models.user import User

logger = get_logger(__name__)

MAX_ATTEMPTS = 5
GLOBAL_RATE_PER_SEC = 25
CHAT_INTERVAL_SEC = 1.0
BATCH_SIZE = 50
BACKOFF_BASE_SEC = 30
BACKOFF_MAX_SEC = 300


def _backoff_seconds(attempts: int) -> int:
    """Exponential backoff: 1->30s, 2->60s, 3->120s, 4->240s (cap 300s)"""
    if attempts <= 0:
        return 0
    return min(BACKOFF_BASE_SEC * (2 ** (attempts - 1)), BACKOFF_MAX_SEC)


def _is_eligible(updated_at: datetime | None, attempts: int, now: datetime) -> bool:
    """Backoff o'tganini tekshirish (attempts=0 — darhol)"""
    if attempts <= 0 or updated_at is None:
        return True
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    return updated_at + timedelta(seconds=_backoff_seconds(attempts)) <= now

STATUS_TEXT = {
    AttendanceStatus.PRESENT: "keldi ✅",
    AttendanceStatus.ABSENT: "kelmadi ❌",
    AttendanceStatus.LATE: "kech qoldi ⏰",
}


async def claim_batch(
    session: AsyncSession, lesson_id: int, limit: int = BATCH_SIZE
) -> list[Notification]:
    """
    Pending notification'larni atomik claim qilish.

    Har bir yozuv uchun attempts+1 bilan UPDATE — faqat status='pending'
    bo'lgandagina muvaffaqiyatli (optimistic lock). Qaytgan yozuvlar
    allaqachon 'claimed' holatda — xato bo'lsa pending'ga qaytariladi.
    """
    stmt = (
        select(Notification.id, Notification.attempts, Notification.updated_at)
        .where(
            Notification.status == NotificationStatus.PENDING,
            Notification.attempts < MAX_ATTEMPTS,
            Notification.attendance_id.in_(
                select(Attendance.id).where(Attendance.lesson_id == lesson_id)
            ),
        )
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    now = datetime.now(UTC)
    claimed = []
    for nid, attempts, updated_at in rows:
        if not _is_eligible(updated_at, attempts, now):
            continue
        res = await session.execute(
            update(Notification)
            .where(
                Notification.id == nid,
                Notification.status == NotificationStatus.PENDING,
                Notification.attempts == attempts,
            )
            .values(attempts=attempts + 1)
        )
        if res.rowcount == 1:
            notif = await session.get(Notification, nid)
            if notif:
                claimed.append(notif)
    await session.flush()
    return claimed


async def wait_rate_limit(redis: aioredis.Redis, telegram_id: int) -> None:
    """Global 25/s + chatga 1/s limitni kutish"""
    # Global oyna
    while True:
        now = int(time.time())
        key = f"rl:global:{now}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 2)
        if count <= GLOBAL_RATE_PER_SEC:
            break
        await asyncio_sleep(0.05)

    # Chat interval
    chat_key = f"rl:chat:{telegram_id}"
    while True:
        ok = await redis.set(chat_key, "1", nx=True, ex=int(CHAT_INTERVAL_SEC) + 1)
        if ok:
            break
        ttl = await redis.ttl(chat_key)
        await asyncio_sleep(min(max(ttl, 0.05), CHAT_INTERVAL_SEC))


async def asyncio_sleep(sec: float) -> None:
    import asyncio

    await asyncio.sleep(sec)


def format_message(
    student_name: str,
    status: AttendanceStatus,
    group_name: str,
    day,
    center_name: str | None = None,
    teacher_name: str | None = None,
) -> str:
    lines = [
        "📋 <b>Davomat</b>",
        "",
        f"O'quvchi: {student_name}",
        f"Holat: {STATUS_TEXT.get(status, status.value)}",
    ]
    if center_name:
        lines.append(f"Markaz: {center_name}")
    group_line = f"Guruh: {group_name}"
    if teacher_name:
        group_line += f" (Ustoz: {teacher_name})"
    lines.append(group_line)
    lines.append(f"Sana: {day.strftime('%d.%m.%Y')}")
    return "\n".join(lines)


async def load_context(session: AsyncSession, notif: Notification) -> dict | None:
    """Xabar uchun kerakli ma'lumotlarni yuklash"""
    att = await session.get(Attendance, notif.attendance_id)
    if att is None:
        return None
    student = await session.get(Student, att.student_id)
    lesson = await session.get(Lesson, att.lesson_id)
    if student is None or lesson is None:
        return None
    group = await session.get(Group, lesson.group_id)
    parent = await session.get(User, notif.parent_user_id)
    if parent is None or not parent.is_active:
        return None

    center_name = None
    from app.models.center import Center

    center = await session.get(Center, student.center_id)
    if center:
        center_name = center.name

    teacher_name = None
    if group and group.teacher_id:
        from app.models.teacher import Teacher

        teacher = await session.get(Teacher, group.teacher_id)
        if teacher:
            teacher_user = await session.get(User, teacher.user_id)
            if teacher_user:
                teacher_name = " ".join(
                    x for x in [teacher_user.first_name, teacher_user.last_name] if x
                ) or None

    day = lesson.lesson_date.astimezone(TASHKENT_TZ).date() if lesson.lesson_date.tzinfo else lesson.lesson_date.date()
    return {
        "telegram_id": parent.telegram_id,
        "text": format_message(
            student.name,
            att.status,
            group.name if group else "-",
            day,
            center_name=center_name,
            teacher_name=teacher_name,
        ),
    }


async def send_one(
    session: AsyncSession,
    bot: Bot,
    redis: aioredis.Redis,
    notif: Notification,
) -> str:
    """
    Bitta notification'ni yuborish.

    Returns: 'sent' | 'blocked' | 'failed' | 'retry'
    """
    ctx = await load_context(session, notif)
    if ctx is None:
        notif.status = NotificationStatus.FAILED
        await session.flush()
        return "failed"

    try:
        await wait_rate_limit(redis, ctx["telegram_id"])
        await bot.send_message(ctx["telegram_id"], ctx["text"], parse_mode="HTML")
        notif.status = NotificationStatus.SENT
        await session.flush()
        return "sent"
    except TelegramForbiddenError:
        # Bot bloklangan — qayta urinmaydi
        notif.status = NotificationStatus.BLOCKED
        await session.flush()
        logger.warning("Bot bloklangan", parent_user_id=notif.parent_user_id)
        return "blocked"
    except TelegramRetryAfter as e:
        # 429 — kutib qayta urinish
        await asyncio_sleep(e.retry_after + 0.5)
        try:
            await wait_rate_limit(redis, ctx["telegram_id"])
            await bot.send_message(ctx["telegram_id"], ctx["text"], parse_mode="HTML")
            notif.status = NotificationStatus.SENT
            await session.flush()
            return "sent"
        except Exception:
            pass
        return await _handle_failure(session, notif)
    except Exception as e:
        logger.warning("Xabar yuborish xatosi", error=str(e), notification_id=notif.id)
        return await _handle_failure(session, notif)


async def _handle_failure(session: AsyncSession, notif: Notification) -> str:
    """Tarmoq/ boshqa xato — attempts limiti bo'yicha failed yoki pending"""
    if notif.attempts >= MAX_ATTEMPTS:
        notif.status = NotificationStatus.FAILED
        await session.flush()
        return "failed"
    # pending'da qoldiradi — reaper qayta navbatga qo'yadi
    notif.status = NotificationStatus.PENDING
    await session.flush()
    return "retry"


async def process_lesson(
    session: AsyncSession,
    bot: Bot,
    redis: aioredis.Redis,
    lesson_id: int,
) -> dict:
    """Dars bo'yicha barcha pending notification'larni drain qilish"""
    stats = {"sent": 0, "blocked": 0, "failed": 0, "retry": 0}
    while True:
        claimed = await claim_batch(session, lesson_id)
        if not claimed:
            break
        for notif in claimed:
            result = await send_one(session, bot, redis, notif)
            stats[result] += 1
        await session.commit()
    return stats


async def reap_stale(session: AsyncSession, redis: aioredis.Redis, bot: Bot) -> int:
    """
    Reaper (har daqiika): 2 daqiqadan eski pending/sending'larni qayta ishlash.

    Bizda 'sending' statusi yo'q — claim attempts orqali. Pending bo'lib
    updated_at eski bo'lganlarni qayta enqueue/drain qilamiz.
    """
    stale_before = datetime.now(UTC) - timedelta(minutes=2)
    # updated_at NULL bo'lishi mumkin (hech qachon UPDATE bo'lmagan) —
    # u holda created_at'ga qaraymiz
    effective_ts = func.coalesce(Notification.updated_at, Notification.created_at)
    stmt = (
        select(Notification.attendance_id)
        .join(Attendance, Notification.attendance_id == Attendance.id)
        .where(
            Notification.status == NotificationStatus.PENDING,
            effective_ts < stale_before,
        )
    )
    att_ids = (await session.execute(stmt)).scalars().all()
    if not att_ids:
        return 0

    lesson_ids = (
        await session.execute(
            select(Attendance.lesson_id)
            .where(Attendance.id.in_(att_ids))
            .distinct()
        )
    ).scalars().all()

    total = 0
    for lid in lesson_ids:
        stats = await process_lesson(session, bot, redis, lid)
        total += stats["sent"] + stats["blocked"] + stats["failed"]
    await session.commit()
    return total
