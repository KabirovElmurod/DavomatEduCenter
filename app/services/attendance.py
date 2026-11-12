"""
Davomat servisi (roadmap 8.4-8.6)

Bitta tranzaksiyada: lesson (get-or-create) + attendance yozuvlari +
attendance_submission (idempotency) + notifications (outbox).
Tranzaksiyadan keyin ARQ'ga enqueue qilinadi (request ichida Telegram yo'q).
"""
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.timezone import tashkent_day_bounds_utc
from app.models.attendance import Attendance
from app.models.attendance_submission import AttendanceSubmission
from app.models.base import AttendanceStatus, NotificationStatus
from app.models.group import Group
from app.models.lesson import Lesson
from app.models.notification import Notification
from app.models.parent_link import ParentLink
from app.models.student import Student
from app.services.audit import AuditService

logger = get_logger(__name__)

# ARQ task nomi — worker (roadmap 9) shu nom bilan funksiyani ro'yxatga oladi
NOTIFY_TASK = "send_pending_notifications"

# Qaysi holatlar ota-onaga xabar yuboradi
NOTIFY_STATUSES = {AttendanceStatus.ABSENT, AttendanceStatus.LATE}


class AttendanceError(Exception):
    """Davomat so'rovi xatosi"""

    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


async def get_or_create_lesson(
    session: AsyncSession, group_id: int, day: date
) -> Lesson:
    """Guruh + sana uchun darsni topish yoki yaratish (Tashkent sanasi)"""
    start_utc, end_utc = tashkent_day_bounds_utc(day)

    stmt = select(Lesson).where(
        Lesson.group_id == group_id,
        Lesson.lesson_date >= start_utc,
        Lesson.lesson_date < end_utc,
    )
    lesson = (await session.execute(stmt)).scalar_one_or_none()
    if lesson:
        return lesson

    lesson = Lesson(group_id=group_id, lesson_date=start_utc)
    session.add(lesson)
    try:
        async with session.begin_nested():
            await session.flush()
    except Exception:
        # Parallel so'rov — boshqa transaction yaratgan bo'lishi mumkin
        lesson = (await session.execute(stmt)).scalar_one()
    return lesson


async def get_lesson_for_day(
    session: AsyncSession, group_id: int, day: date
) -> Lesson | None:
    """Darsni faqat topish (yaratmaydi)"""
    start_utc, end_utc = tashkent_day_bounds_utc(day)
    stmt = select(Lesson).where(
        Lesson.group_id == group_id,
        Lesson.lesson_date >= start_utc,
        Lesson.lesson_date < end_utc,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_group_students(session: AsyncSession, group_id: int) -> list[Student]:
    stmt = (
        select(Student)
        .where(Student.group_id == group_id, Student.is_active.is_(True))
        .order_by(Student.name)
    )
    return list((await session.execute(stmt)).scalars().all())


async def find_submission(
    session: AsyncSession, idempotency_key: str
) -> AttendanceSubmission | None:
    stmt = select(AttendanceSubmission).where(
        AttendanceSubmission.idempotency_key == idempotency_key
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def submit_attendance(
    session: AsyncSession,
    group: Group,
    day: date,
    items: list[dict],
    submitted_by: int,
    idempotency_key: str,
) -> dict:
    """
    Davomatni bitta tranzaksiyada saqlash.

    Idempotent: bir xil Idempotency-Key qayta kelsa, mavjud submission
    qaytariladi va bazaga yangi yozuv qo'shilmaydi.

    Returns:
        {"lesson_id", "submission_id", "duplicate", "students", "notifications"}
    """
    # 1. Idempotency check
    existing = await find_submission(session, idempotency_key)
    if existing:
        return {
            "lesson_id": existing.lesson_id,
            "submission_id": existing.id,
            "duplicate": True,
            "students": 0,
            "notifications": 0,
        }

    # 2. Lesson get-or-create
    lesson = await get_or_create_lesson(session, group.id, day)

    # 3. O'quvchilarni tekshirish
    students = await list_group_students(session, group.id)
    student_ids = {s.id for s in students}
    for item in items:
        if item["student_id"] not in student_ids:
            raise AttendanceError(
                f"O'quvchi {item['student_id']} bu guruhda topilmadi", 400
            )
        try:
            AttendanceStatus(item["status"])
        except ValueError:
            raise AttendanceError(f"Noto'g'ri status: {item['status']}", 400)

    # 4. Attendance upsert (lesson_id + student_id unique)
    written = 0
    notify_pairs: list[tuple[int, AttendanceStatus]] = []  # (attendance_id, status)
    for item in items:
        status = AttendanceStatus(item["status"])
        stmt = select(Attendance).where(
            Attendance.lesson_id == lesson.id,
            Attendance.student_id == item["student_id"],
        )
        att = (await session.execute(stmt)).scalar_one_or_none()
        if att is None:
            att = Attendance(
                lesson_id=lesson.id,
                student_id=item["student_id"],
                status=status,
            )
            session.add(att)
            await session.flush()
        else:
            att.status = status
        written += 1
        if status in NOTIFY_STATUSES:
            notify_pairs.append((att.id, status))

    # 5. Submission (idempotency yozuvi)
    submission = AttendanceSubmission(
        lesson_id=lesson.id,
        submitted_by=submitted_by,
        idempotency_key=idempotency_key,
    )
    session.add(submission)
    await session.flush()

    # 6. Notifications outbox — har bir yo'qlik/kechikish uchun ota-onalar
    notifications = 0
    if notify_pairs:
        att_ids = [a for a, _ in notify_pairs]
        links_stmt = select(ParentLink).where(
            ParentLink.student_id.in_(
                select(Attendance.student_id).where(Attendance.id.in_(att_ids))
            ),
            ParentLink.user_id.isnot(None),
            ParentLink.revoked_at.is_(None),
        )
        links = (await session.execute(links_stmt)).scalars().all()
        # attendance_id bo'yicha status
        att_status = dict(notify_pairs)
        for link in links:
            att_stmt = select(Attendance).where(
                Attendance.id.in_(att_ids),
                Attendance.student_id == link.student_id,
            )
            att = (await session.execute(att_stmt)).scalars().first()
            if att is None or att.id not in att_status:
                continue
            # Unique (attendance_id, parent_user_id) — mavjud bo'lsa o'tkazib yuborish
            exists_stmt = select(Notification.id).where(
                Notification.attendance_id == att.id,
                Notification.parent_user_id == link.user_id,
            )
            if (await session.execute(exists_stmt)).scalar_one_or_none():
                continue
            session.add(
                Notification(
                    attendance_id=att.id,
                    parent_user_id=link.user_id,
                    status=NotificationStatus.PENDING,
                    attempts=0,
                )
            )
            notifications += 1
        await session.flush()

    logger.info(
        "Davomat saqlandi",
        group_id=group.id,
        lesson_id=lesson.id,
        submission_id=submission.id,
        students=written,
        notifications=notifications,
    )

    return {
        "lesson_id": lesson.id,
        "submission_id": submission.id,
        "duplicate": False,
        "students": written,
        "notifications": notifications,
    }


async def correct_lesson_attendance(
    session: AsyncSession,
    lesson: Lesson,
    updates: dict[int, AttendanceStatus],
    actor_id: int,
    center_id: int,
    notify_parents: bool,
) -> dict:
    """
    Admin davomat tuzatishi (roadmap 10-bosqich).

    - Faqat lesson'ga tegishli attendance'lar yangilanadi
    - O'zgarish audit_log'ga old/new bilan yoziladi
    - O'zgargan yozuvlarning pending xabarlari o'chiriladi (eskirgan xabar ketmasligi uchun)
    - notify_parents=True bo'lsa, yangi absent/late uchun ota-onalarga
      pending notification yaratiladi (mavjud dublikat yaratilmaydi)

    Returns:
        {"changed": int, "notifications": int}
    """
    if not updates:
        return {"changed": 0, "notifications": 0}

    stmt = select(Attendance).where(
        Attendance.lesson_id == lesson.id,
        Attendance.id.in_(list(updates)),
    )
    rows = (await session.execute(stmt)).scalars().all()

    old_records: dict[str, dict] = {}
    changed: list[Attendance] = []
    for att in rows:
        new_status = updates[att.id]
        if new_status == att.status:
            continue
        old_records[str(att.id)] = {
            "student_id": att.student_id,
            "status": att.status.value,
        }
        att.status = new_status
        changed.append(att)

    if not changed:
        return {"changed": 0, "notifications": 0}

    changed_ids = [a.id for a in changed]

    # Pending xabarlarni o'chirish — status o'zgarganligi sababli
    # eski matnli xabar ota-onaga ketib qolmasligi uchun
    await session.execute(
        delete(Notification).where(
            Notification.attendance_id.in_(changed_ids),
            Notification.status == NotificationStatus.PENDING,
        )
    )

    audit = AuditService(session)
    await audit.log_update(
        center_id=center_id,
        actor_id=actor_id,
        entity="attendance",
        entity_id=lesson.id,
        old={"records": old_records},
        new={
            "records": {
                str(a.id): {"student_id": a.student_id, "status": a.status.value}
                for a in changed
            },
            "notify_parents": notify_parents,
        },
    )

    created = 0
    if notify_parents:
        notify_ids = {a.id for a in changed if a.status in NOTIFY_STATUSES}
        if notify_ids:
            links_stmt = select(ParentLink).where(
                ParentLink.student_id.in_(
                    select(Attendance.student_id).where(Attendance.id.in_(notify_ids))
                ),
                ParentLink.user_id.isnot(None),
                ParentLink.revoked_at.is_(None),
            )
            links = (await session.execute(links_stmt)).scalars().all()
            att_by_student = {a.student_id: a for a in changed if a.id in notify_ids}
            for link in links:
                att = att_by_student.get(link.student_id)
                if att is None:
                    continue
                # Unique (attendance_id, parent_user_id) — dublikat yaratmaymiz
                exists_stmt = select(Notification.id).where(
                    Notification.attendance_id == att.id,
                    Notification.parent_user_id == link.user_id,
                )
                if (await session.execute(exists_stmt)).scalar_one_or_none():
                    continue
                session.add(
                    Notification(
                        attendance_id=att.id,
                        parent_user_id=link.user_id,
                        status=NotificationStatus.PENDING,
                        attempts=0,
                    )
                )
                created += 1
            await session.flush()

    logger.info(
        "Davomat tuzatildi",
        lesson_id=lesson.id,
        changed=len(changed),
        notifications=created,
        notify_parents=notify_parents,
    )
    return {"changed": len(changed), "notifications": created}


async def enqueue_lesson_notifications(lesson_id: int) -> None:
    """
    ARQ'ga notification drain job'ini qo'yish.

    Redis/queue ishlamasa ham davomat saqlangan — reaper qayta urinadi.
    """
    try:
        from urllib.parse import urlparse

        from arq import create_pool
        from arq.connections import RedisSettings

        from app.core.config import settings

        u = urlparse(settings.REDIS_URL)
        pool = await create_pool(
            RedisSettings(
                host=u.hostname or "localhost",
                port=u.port or 6379,
                database=int(u.path.lstrip("/") or 0),
                password=u.password,
            )
        )
        try:
            await pool.enqueue_job(NOTIFY_TASK, lesson_id)
        finally:
            await pool.close()
    except Exception as e:
        logger.warning("ARQ enqueue xatosi", lesson_id=lesson_id, error=str(e))
