"""
Admin davomat testlari (roadmap 10-bosqich)

O'tgan darslar ro'yxati, davomatni tuzatish (audit bilan),
ota-ona xabar holati, tenant izolyatsiya, dublikat xabar yo'qligi.
"""

import itertools
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.attendance import Attendance
from app.models.audit_log import AuditLog
from app.models.base import AttendanceStatus, NotificationStatus, UserRole
from app.models.center import Center
from app.models.group import Group
from app.models.lesson import Lesson
from app.models.notification import Notification
from app.models.parent_link import ParentLink
from app.models.student import Student
from app.models.user import User

_telegram_ids = itertools.count(950000)


# --------------------------------------------------------------------------
# Helper'lar
# --------------------------------------------------------------------------
async def make_center_with_owner(db, name="Markaz", telegram_id=None):
    if telegram_id is None:
        telegram_id = next(_telegram_ids)
    center = Center(name=name)
    db.add(center)
    await db.flush()
    owner = User(
        telegram_id=telegram_id,
        first_name="Owner",
        last_name="User",
        username="owner_user",
        role=UserRole.OWNER,
        center_id=center.id,
        is_active=True,
    )
    db.add(owner)
    await db.flush()
    return center, owner


def auth_cookies(user: User, center: Center, csrf="test-csrf"):
    token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value, "center_id": center.id}
    )
    return {
        "cookies": {"admin_session": token, "csrf_token": csrf},
        "headers": {"X-CSRF-Token": csrf},
    }


async def make_lesson_with_attendance(db, center, status=AttendanceStatus.PRESENT):
    """Guruh + o'quvchi + dars + bitta attendance yozuvi"""
    group = Group(name="Guruh A", center_id=center.id, is_active=True)
    db.add(group)
    await db.flush()
    student = Student(name="O'quvchi", center_id=center.id, group_id=group.id, is_active=True)
    db.add(student)
    await db.flush()
    lesson = Lesson(
        group_id=group.id,
        lesson_date=datetime(2026, 11, 5, 19, 0, tzinfo=UTC),
    )
    db.add(lesson)
    await db.flush()
    att = Attendance(lesson_id=lesson.id, student_id=student.id, status=status)
    db.add(att)
    await db.flush()
    return group, student, lesson, att


async def make_parent(db, center, student):
    """Ota-ona user + parent_link"""
    parent = User(
        telegram_id=next(_telegram_ids),
        first_name="Ota",
        last_name="Ona",
        role=UserRole.PARENT,
        center_id=center.id,
        is_active=True,
    )
    db.add(parent)
    await db.flush()
    link = ParentLink(
        student_id=student.id,
        user_id=parent.id,
        invite_token=f"p_{student.id}_{parent.id}",
    )
    db.add(link)
    await db.flush()
    return parent, link


# --------------------------------------------------------------------------
# Ro'yxat va detail sahifalar
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_attendance_list_page(client, db_session):
    """Davomat ro'yxati: guruh bo'yicha foiz + o'tgan darslar"""
    center, owner = await make_center_with_owner(db_session, "M1", 9601)
    await make_lesson_with_attendance(db_session, center)
    await db_session.commit()
    auth = auth_cookies(owner, center)

    r = await client.get("/admin/attendance", **auth)
    assert r.status_code == 200
    assert "Davomat" in r.text
    assert "Guruh A" in r.text


@pytest.mark.asyncio
async def test_attendance_detail_page(client, db_session):
    """Dars sahifasi: statuslar + ota-ona xabarlari holati"""
    center, owner = await make_center_with_owner(db_session, "M2", 9602)
    group, student, lesson, att = await make_lesson_with_attendance(
        db_session, center, AttendanceStatus.ABSENT
    )
    parent, _ = await make_parent(db_session, center, student)
    db_session.add(
        Notification(
            attendance_id=att.id,
            parent_user_id=parent.id,
            status=NotificationStatus.SENT,
            attempts=1,
        )
    )
    await db_session.commit()
    auth = auth_cookies(owner, center)

    r = await client.get(f"/admin/attendance/{lesson.id}", **auth)
    assert r.status_code == 200
    assert "O'quvchi" in r.text
    assert "yuborildi" in r.text
    assert 'name="notify"' in r.text


# --------------------------------------------------------------------------
# Tuzatish
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_attendance_correction_audit(client, db_session):
    """Status tuzatish saqlanadi va audit_log'ga yoziladi"""
    center, owner = await make_center_with_owner(db_session, "M3", 9603)
    _, _, lesson, att = await make_lesson_with_attendance(
        db_session, center, AttendanceStatus.PRESENT
    )
    await db_session.commit()
    auth = auth_cookies(owner, center)

    r = await client.post(
        f"/admin/attendance/{lesson.id}",
        data={f"status_{att.id}": "absent"},
        follow_redirects=False,
        **auth,
    )
    assert r.status_code == 303

    await db_session.refresh(att)
    assert att.status == AttendanceStatus.ABSENT

    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.entity == "attendance",
                AuditLog.entity_id == lesson.id,
            )
        )
    ).scalar_one()
    assert audit.action.value == "update"
    assert audit.old["records"][str(att.id)]["status"] == "present"
    assert audit.new["records"][str(att.id)]["status"] == "absent"


@pytest.mark.asyncio
async def test_correction_notify_creates_and_dedupes(client, db_session):
    """notify=1 -> pending notification; qayta yuborish dublikat yaratmaydi"""
    center, owner = await make_center_with_owner(db_session, "M4", 9604)
    _, student, lesson, att = await make_lesson_with_attendance(
        db_session, center, AttendanceStatus.PRESENT
    )
    parent, _ = await make_parent(db_session, center, student)
    await db_session.commit()
    auth = auth_cookies(owner, center)

    # present -> absent + notify
    r = await client.post(
        f"/admin/attendance/{lesson.id}",
        data={f"status_{att.id}": "absent", "notify": "1"},
        follow_redirects=False,
        **auth,
    )
    assert r.status_code == 303

    notifs = (
        await db_session.execute(
            select(Notification).where(Notification.attendance_id == att.id)
        )
    ).scalars().all()
    assert len(notifs) == 1
    assert notifs[0].parent_user_id == parent.id
    assert notifs[0].status == NotificationStatus.PENDING

    # Qayta tuzatish (absent -> absent emas, late) + notify: dublikat bo'lmasligi kerak
    # lekin status o'zgaradi -> pending o'chadi, late uchun yangi yaratiladi (1 ta)
    r = await client.post(
        f"/admin/attendance/{lesson.id}",
        data={f"status_{att.id}": "late", "notify": "1"},
        follow_redirects=False,
        **auth,
    )
    assert r.status_code == 303
    notifs = (
        await db_session.execute(
            select(Notification).where(Notification.attendance_id == att.id)
        )
    ).scalars().all()
    assert len(notifs) == 1  # dublikat yo'q


@pytest.mark.asyncio
async def test_correction_no_notify_and_pending_cleanup(client, db_session):
    """notify'siz: xabar yaratilmaydi; pending eskirgan xabar o'chadi"""
    center, owner = await make_center_with_owner(db_session, "M5", 9605)
    _, student, lesson, att = await make_lesson_with_attendance(
        db_session, center, AttendanceStatus.ABSENT
    )
    parent, _ = await make_parent(db_session, center, student)
    # Mavjud pending xabar (ustoz belgilaganda yaratilgan)
    db_session.add(
        Notification(
            attendance_id=att.id,
            parent_user_id=parent.id,
            status=NotificationStatus.PENDING,
            attempts=0,
        )
    )
    await db_session.commit()
    auth = auth_cookies(owner, center)

    # absent -> present, notify'siz
    r = await client.post(
        f"/admin/attendance/{lesson.id}",
        data={f"status_{att.id}": "present"},
        follow_redirects=False,
        **auth,
    )
    assert r.status_code == 303

    notifs = (
        await db_session.execute(
            select(Notification).where(Notification.attendance_id == att.id)
        )
    ).scalars().all()
    assert len(notifs) == 0  # pending o'chirildi, yangisi yaratilmedi


# --------------------------------------------------------------------------
# Tenant izolyatsiya
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_attendance_tenant_isolation(client, db_session):
    """Boshqa markaz darsini ko'rish/tuzatish mumkin emas"""
    center_a, owner_a = await make_center_with_owner(db_session, "A", 9606)
    center_b, _ = await make_center_with_owner(db_session, "B", 9607)
    _, _, lesson_b, att_b = await make_lesson_with_attendance(db_session, center_b)
    await db_session.commit()
    auth = auth_cookies(owner_a, center_a)

    r = await client.get(f"/admin/attendance/{lesson_b.id}", **auth)
    assert r.status_code == 404

    r = await client.post(
        f"/admin/attendance/{lesson_b.id}",
        data={f"status_{att_b.id}": "absent"},
        **auth,
    )
    assert r.status_code in (400, 404)
    await db_session.refresh(att_b)
    assert att_b.status != AttendanceStatus.ABSENT
