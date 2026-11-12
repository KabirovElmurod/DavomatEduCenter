# roadmap 4.8
"""
Ustoz izolyatsiya testlari (roadmap 4.10, 8-bosqich)

Ustoz faqat o'z guruhlarini ko'ra oladi.
"""
import itertools

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.base import UserRole
from app.models.center import Center
from app.models.group import Group
from app.models.teacher import Teacher
from app.models.user import User

_telegram_ids = itertools.count(910000)


async def _make_teacher(db, center_id, name="Ustoz"):
    uid = next(_telegram_ids)
    user = User(
        telegram_id=uid,
        first_name=name,
        role=UserRole.TEACHER,
        center_id=center_id,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    teacher = Teacher(user_id=user.id, is_active=True)
    db.add(teacher)
    await db.flush()
    return user, teacher


def _token(user: User, center_id: int) -> dict:
    token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value, "center_id": center_id}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_teacher_cannot_access_other_teacher_group(client: AsyncClient, db_session):
    """Ustoz boshqa ustoz guruhiga kira olmaydi (403)"""
    center = Center(name="C1")
    db_session.add(center)
    await db_session.flush()

    u1, t1 = await _make_teacher(db_session, center.id, "Ustoz1")
    u2, t2 = await _make_teacher(db_session, center.id, "Ustoz2")

    g1 = Group(name="G1", center_id=center.id, teacher_id=t1.id)
    g2 = Group(name="G2", center_id=center.id, teacher_id=t2.id)
    db_session.add_all([g1, g2])
    await db_session.commit()

    # Ustoz1 o'z guruhini ko'radi
    r = await client.get(
        f"/api/v1/groups/{g1.id}/lesson/today", headers=_token(u1, center.id)
    )
    assert r.status_code == 200

    # Ustoz1 ustoz2 guruhiga kira olmaydi
    g2_id = g2.id
    r = await client.get(
        f"/api/v1/groups/{g2_id}/lesson/today", headers=_token(u1, center.id)
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_teacher_list_only_own_groups(client: AsyncClient, db_session):
    """GET /teacher/groups faqat o'z guruhlarini qaytaradi"""
    center = Center(name="C2")
    db_session.add(center)
    await db_session.flush()

    u1, t1 = await _make_teacher(db_session, center.id, "UstozA")
    u2, t2 = await _make_teacher(db_session, center.id, "UstozB")

    db_session.add_all(
        [
            Group(name="GA", center_id=center.id, teacher_id=t1.id),
            Group(name="GB", center_id=center.id, teacher_id=t2.id),
        ]
    )
    await db_session.commit()

    r = await client.get("/api/v1/teacher/groups", headers=_token(u1, center.id))
    assert r.status_code == 200
    names = [g["name"] for g in r.json()["groups"]]
    assert names == ["GA"]
