# roadmap 9.9
"""
Notification worker testlari (roadmap 9.9)

Mock bot + mock redis bilan drain, status transitions, rate limit.
"""
import itertools

import pytest

from app.models.attendance import Attendance
from app.models.base import AttendanceStatus, NotificationStatus, UserRole
from app.models.center import Center
from app.models.group import Group
from app.models.lesson import Lesson
from app.models.notification import Notification
from app.models.parent_link import ParentLink
from app.models.student import Student
from app.models.user import User
from app.services import notification_sender

_telegram_ids = itertools.count(930000)


class FakeRedis:
    """Minimal Redis mock — rate limit doim o'tadi"""

    async def incr(self, key):
        return 1

    async def expire(self, key, ttl):
        return True

    async def set(self, key, val, nx=False, ex=None):
        return True

    async def ttl(self, key):
        return 0


class FakeBot:
    def __init__(self, fail_times=0, forbidden=False):
        self.sent = []
        self.fail_times = fail_times
        self.forbidden = forbidden

    async def send_message(self, chat_id, text, parse_mode=None):
        if self.forbidden:
            from aiogram.exceptions import TelegramForbiddenError

            raise TelegramForbiddenError(method=None, message="Forbidden")
        if self.fail_times > 0:
            self.fail_times -= 1
            raise ConnectionError("network error")
        self.sent.append((chat_id, text))


async def _setup(db):
    """Markaz + guruh + dars + o'quvchi + ota-ona + attendance + notification"""
    center = Center(name="N Markaz")
    db.add(center)
    await db.flush()

    teacher_user = User(
        telegram_id=next(_telegram_ids), first_name="T", role=UserRole.TEACHER,
        center_id=center.id,
    )
    parent_user = User(
        telegram_id=next(_telegram_ids), first_name="P", role=UserRole.PARENT,
        center_id=center.id,
    )
    db.add_all([teacher_user, parent_user])
    await db.flush()

    group = Group(name="G", center_id=center.id)
    db.add(group)
    await db.flush()

    student = Student(name="O'quvchi", center_id=center.id, group_id=group.id)
    db.add(student)
    await db.flush()

    from app.core.timezone import tashkent_day_bounds_utc, today_tashkent

    start, _ = tashkent_day_bounds_utc(today_tashkent())
    lesson = Lesson(group_id=group.id, lesson_date=start)
    db.add(lesson)
    await db.flush()

    att = Attendance(lesson_id=lesson.id, student_id=student.id,
                     status=AttendanceStatus.ABSENT)
    db.add(att)
    await db.flush()

    link = ParentLink(student_id=student.id, user_id=parent_user.id,
                      invite_token=f"p_{next(_telegram_ids)}")
    db.add(link)
    await db.flush()

    notif = Notification(attendance_id=att.id, parent_user_id=parent_user.id,
                         status=NotificationStatus.PENDING, attempts=0)
    db.add(notif)
    await db.commit()
    return center, lesson, notif, parent_user


@pytest.mark.asyncio
async def test_drain_sends_notifications(db_session):
    """Pending notification'lar yuboriladi -> status sent"""
    _, lesson, notif, parent = await _setup(db_session)
    bot = FakeBot()

    stats = await notification_sender.process_lesson(
        db_session, bot, FakeRedis(), lesson.id
    )

    assert stats["sent"] == 1
    assert len(bot.sent) == 1
    assert bot.sent[0][0] == parent.telegram_id
    assert "kelmadi" in bot.sent[0][1]

    await db_session.refresh(notif)
    assert notif.status == NotificationStatus.SENT


@pytest.mark.asyncio
async def test_blocked_on_forbidden(db_session):
    """403 -> blocked, qayta urinmaydi"""
    _, lesson, notif, _ = await _setup(db_session)
    bot = FakeBot(forbidden=True)

    stats = await notification_sender.process_lesson(
        db_session, bot, FakeRedis(), lesson.id
    )

    assert stats["blocked"] == 1
    await db_session.refresh(notif)
    assert notif.status == NotificationStatus.BLOCKED


@pytest.mark.asyncio
async def test_retry_on_network_error(db_session):
    """Tarmoq xatosi -> pending'da qoladi (reaper qayta urinadi)"""
    _, lesson, notif, _ = await _setup(db_session)
    bot = FakeBot(fail_times=10)  # doim xato

    stats = await notification_sender.process_lesson(
        db_session, bot, FakeRedis(), lesson.id
    )

    assert stats["retry"] == 1
    await db_session.refresh(notif)
    # attempts=1 < 5 -> pending
    assert notif.status == NotificationStatus.PENDING
    assert notif.attempts == 1


@pytest.mark.asyncio
async def test_max_attempts_failed(db_session):
    """5 urinishdan keyin -> failed"""
    _, lesson, notif, _ = await _setup(db_session)
    notif.attempts = 4  # keyingi claim 5-bo'ladi
    await db_session.commit()
    # backoff o'tganini simulyatsiya qilish (onupdate'ni chetlab)
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import text

    await db_session.execute(
        text("UPDATE notifications SET updated_at = :ts WHERE id = :id"),
        {"ts": datetime.now(UTC) - timedelta(minutes=10), "id": notif.id},
    )
    await db_session.commit()

    bot = FakeBot(fail_times=10)
    stats = await notification_sender.process_lesson(
        db_session, bot, FakeRedis(), lesson.id
    )

    assert stats["failed"] == 1
    await db_session.refresh(notif)
    assert notif.status == NotificationStatus.FAILED


@pytest.mark.asyncio
async def test_no_double_send(db_session):
    """Ikki marta process_lesson -> faqat 1 marta yuboriladi"""
    _, lesson, _, _ = await _setup(db_session)
    bot = FakeBot()

    await notification_sender.process_lesson(db_session, bot, FakeRedis(), lesson.id)
    stats2 = await notification_sender.process_lesson(
        db_session, bot, FakeRedis(), lesson.id
    )

    assert len(bot.sent) == 1
    assert stats2["sent"] == 0


async def _bulk_notifications(db, center, lesson, group, parent_user, count):
    """count ta o'quvchi + attendance + notification yaratish"""
    from app.models.notification import Notification as N

    students = [
        Student(name=f"O{q}", center_id=center.id, group_id=group.id)
        for q in range(count)
    ]
    db.add_all(students)
    await db.flush()

    atts = [
        Attendance(lesson_id=lesson.id, student_id=s.id,
                   status=AttendanceStatus.PRESENT)
        for s in students
    ]
    db.add_all(atts)
    await db.flush()

    notifs = [
        N(attendance_id=a.id, parent_user_id=parent_user.id,
          status=NotificationStatus.PENDING, attempts=0)
        for a in atts
    ]
    db.add_all(notifs)
    await db.commit()
    return notifs


@pytest.mark.asyncio
async def test_drain_500(db_session):
    """6.9: 500 notification drain — barchasi sent, dublikat yo'q"""
    center, lesson, _, parent = await _setup(db_session)
    group = await db_session.get(Group, lesson.group_id)
    await _bulk_notifications(db_session, center, lesson, group, parent, 500)

    bot = FakeBot()
    stats = await notification_sender.process_lesson(
        db_session, bot, FakeRedis(), lesson.id
    )

    assert stats["sent"] == 501  # 1 ta _setup + 500 ta bulk
    assert len(bot.sent) == 501

    # Qayta drain — hech narsa yuborilmaydi
    stats2 = await notification_sender.process_lesson(
        db_session, bot, FakeRedis(), lesson.id
    )
    assert stats2["sent"] == 0
    assert len(bot.sent) == 501


@pytest.mark.asyncio
async def test_worker_restart_no_loss(db_session):
    """6.9: worker o'chib-yoqilsa — pending'lar yo'qolmaydi, dublikat ketmaydi"""
    center, lesson, _, parent = await _setup(db_session)
    group = await db_session.get(Group, lesson.group_id)
    await _bulk_notifications(db_session, center, lesson, group, parent, 60)

    # 60 tasini "oldin claim qilingan" holatda simulyatsiya qilish:
    # attempts=1, status=pending, backoff o'tgan
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import text

    await db_session.execute(
        text(
            "UPDATE notifications SET attempts = 1, "
            "updated_at = :ts WHERE status = 'pending'"
        ),
        {"ts": datetime.now(UTC) - timedelta(minutes=10)},
    )
    await db_session.commit()

    bot = FakeBot()
    stats = await notification_sender.process_lesson(
        db_session, bot, FakeRedis(), lesson.id
    )

    # Barcha 61 ta notification yuboriladi (restart'dan keyin ham)
    assert stats["sent"] == 61
    assert len(bot.sent) == 61


def test_format_message_rich():
    """Xabar matni: markaz, guruh, ustoz, sana bilan"""
    from datetime import date

    from app.models.base import AttendanceStatus
    from app.services.notification_sender import format_message

    text = format_message(
        "Ali Valiyev",
        AttendanceStatus.ABSENT,
        "Ingliz 5-A",
        date(2026, 11, 10),
        center_name="Bilim Markazi",
        teacher_name="Jonibek Teacher",
    )
    assert "O'quvchi: Ali Valiyev" in text
    assert "kelmadi" in text
    assert "Markaz: Bilim Markazi" in text
    assert "Guruh: Ingliz 5-A (Ustoz: Jonibek Teacher)" in text
    assert "10.11.2026" in text


def test_format_message_minimal():
    """Markaz/ustoz yo'q bo'lsa ham xabar shakllanadi"""
    from datetime import date

    from app.models.base import AttendanceStatus
    from app.services.notification_sender import format_message

    text = format_message("Test", AttendanceStatus.PRESENT, "-", date(2026, 1, 1))
    assert "keldi" in text
    assert "Markaz:" not in text
