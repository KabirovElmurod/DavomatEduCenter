# roadmap 8.9
"""
Davomat idempotency testlari (roadmap 8.9)

Bir xil Idempotency-Key bilan 5 ta so'rov (parallel ham)
-> bazada 1 ta submission, attendance yozuvlari dublikat emas.
"""
import itertools

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.security import create_access_token
from app.models.attendance import Attendance
from app.models.attendance_submission import AttendanceSubmission
from app.models.base import AttendanceStatus, UserRole
from app.models.center import Center
from app.models.group import Group
from app.models.lesson import Lesson
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.user import User

_telegram_ids = itertools.count(920000)


async def _setup(db):
    """Markaz + ustoz + guruh + 3 o'quvchi"""
    center = Center(name="Idem Markaz")
    db.add(center)
    await db.flush()

    user = User(
        telegram_id=next(_telegram_ids),
        first_name="Ustoz",
        role=UserRole.TEACHER,
        center_id=center.id,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    teacher = Teacher(user_id=user.id, is_active=True)
    db.add(teacher)
    await db.flush()

    group = Group(name="G1", center_id=center.id, teacher_id=teacher.id)
    db.add(group)
    await db.flush()

    students = [
        Student(name=f"O'quvchi {i}", center_id=center.id, group_id=group.id)
        for i in range(3)
    ]
    db.add_all(students)
    await db.flush()
    await db.commit()
    return center, user, group, students


def _headers(user: User, center_id: int) -> dict:
    token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value, "center_id": center_id}
    )
    return {"Authorization": f"Bearer {token}"}


def _payload(students):
    return {
        "items": [
            {"student_id": s.id, "status": "present"} for s in students
        ]
    }


@pytest.mark.asyncio
async def test_five_same_requests_one_submission(client: AsyncClient, db_session):
    """5 ta bir xil Idempotency-Key -> 1 submission, attendance takrorlanmaydi"""
    center, user, group, students = await _setup(db_session)
    headers = _headers(user, center.id)
    key = "idem-key-1"
    url = f"/api/v1/groups/{group.id}/attendance"

    for _ in range(5):
        r = await client.post(
            url,
            json=_payload(students),
            headers={**headers, "Idempotency-Key": key},
        )
        assert r.status_code == 200

    # Hisoblar faqat shu guruh bo'yicha (baza testlar orasida tozalanmaydi)
    subs = (
        await db_session.execute(
            select(func.count(AttendanceSubmission.id))
            .join(Lesson, AttendanceSubmission.lesson_id == Lesson.id)
            .where(Lesson.group_id == group.id)
        )
    ).scalar_one()
    atts = (
        await db_session.execute(
            select(func.count(Attendance.id))
            .join(Lesson, Attendance.lesson_id == Lesson.id)
            .where(Lesson.group_id == group.id)
        )
    ).scalar_one()
    lessons = (
        await db_session.execute(
            select(func.count(Lesson.id)).where(Lesson.group_id == group.id)
        )
    ).scalar_one()

    assert subs == 1
    assert atts == 3  # 3 o'quvchi, dublikat yo'q
    assert lessons == 1


@pytest.mark.asyncio
async def test_sequential_requests_separate_sessions(client: AsyncClient, db_session, engine):
    """Har bir so'rov alohida session bilan (production kabi) -> 1 submission"""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.core.db import get_db
    from app.main import app

    center, user, group, students = await _setup(db_session)
    headers = _headers(user, center.id)
    url = f"/api/v1/groups/{group.id}/attendance"

    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    try:
        results = []
        for _ in range(5):
            results.append(
                await client.post(
                    url,
                    json=_payload(students),
                    headers={**headers, "Idempotency-Key": "parallel-key"},
                )
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert all(r.status_code == 200 for r in results)

    subs = (
        await db_session.execute(
            select(func.count(AttendanceSubmission.id))
            .join(Lesson, AttendanceSubmission.lesson_id == Lesson.id)
            .where(Lesson.group_id == group.id)
        )
    ).scalar_one()
    assert subs == 1


@pytest.mark.asyncio
async def test_different_key_updates_attendance(client: AsyncClient, db_session):
    """Boshqa Idempotency-Key -> status yangilanadi, submission yangi"""
    center, user, group, students = await _setup(db_session)
    headers = _headers(user, center.id)
    url = f"/api/v1/groups/{group.id}/attendance"

    r1 = await client.post(
        url,
        json=_payload(students),
        headers={**headers, "Idempotency-Key": "key-a"},
    )
    assert r1.status_code == 200

    # Barcha yo'qlik
    payload2 = {
        "items": [
            {"student_id": s.id, "status": "absent"} for s in students
        ]
    }
    r2 = await client.post(
        url,
        json=payload2,
        headers={**headers, "Idempotency-Key": "key-b"},
    )
    assert r2.status_code == 200

    subs = (
        await db_session.execute(
            select(func.count(AttendanceSubmission.id))
            .join(Lesson, AttendanceSubmission.lesson_id == Lesson.id)
            .where(Lesson.group_id == group.id)
        )
    ).scalar_one()
    atts = (
        await db_session.execute(
            select(func.count(Attendance.id))
            .join(Lesson, Attendance.lesson_id == Lesson.id)
            .where(Lesson.group_id == group.id, Attendance.status == AttendanceStatus.ABSENT)
        )
    ).scalar_one()
    assert subs == 2
    assert atts == 3


@pytest.mark.asyncio
async def test_missing_idempotency_key(client: AsyncClient, db_session):
    """Idempotency-Key'siz so'rov -> 422/400"""
    center, user, group, students = await _setup(db_session)
    headers = _headers(user, center.id)
    url = f"/api/v1/groups/{group.id}/attendance"

    r = await client.post(url, json=_payload(students), headers=headers)
    assert r.status_code in (400, 422)
