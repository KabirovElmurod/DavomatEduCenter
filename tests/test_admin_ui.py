"""
Admin UI testlari (roadmap 7.13)

Smoke testlar + tenant izolyatsiya.
"""

import itertools

import pytest

from app.core.security import create_access_token
from app.models.base import UserRole
from app.models.center import Center
from app.models.group import Group
from app.models.student import Student
from app.models.user import User

_telegram_ids = itertools.count(900000)


# --------------------------------------------------------------------------
# Helper'lar
# --------------------------------------------------------------------------
async def make_center_with_owner(db, name="Test Markaz", telegram_id=None):
    """Markaz + owner user yaratish"""
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
    """Admin cookie'lar + CSRF header"""
    token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value, "center_id": center.id}
    )
    return {
        "cookies": {
            "admin_session": token,
            "csrf_token": csrf,
        },
        "headers": {"X-CSRF-Token": csrf},
    }


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_login_page_renders(client, monkeypatch):
    """Login sahifasi Telegram Login Widget bilan ochiladi"""
    from app.core.config import settings

    monkeypatch.setattr(settings, "BOT_USERNAME", "test_bot")

    r = await client.get("/admin/login")
    assert r.status_code == 200
    assert "telegram-widget" in r.text
    assert "test_bot" in r.text


@pytest.mark.asyncio
async def test_groups_requires_auth(client):
    """Kirmagan user login sahifasiga redirect bo'ladi"""
    r = await client.get("/admin/groups", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/login"


@pytest.mark.asyncio
async def test_post_without_csrf_rejected(client, db_session):
    """CSRF token'siz POST rad etiladi"""
    center, owner = await make_center_with_owner(db_session)
    await db_session.commit()

    token = create_access_token(
        data={"sub": str(owner.id), "role": "owner", "center_id": center.id}
    )
    r = await client.post(
        "/admin/groups",
        data={"name": "Guruh 1"},
        cookies={"admin_session": token, "csrf_token": "tok"},
        # X-CSRF-Token header yo'q
    )
    assert r.status_code == 403


# --------------------------------------------------------------------------
# Guruhlar
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_groups_page_and_create(client, db_session):
    """Guruhlar ro'yxati + yaratish smoke test"""
    center, owner = await make_center_with_owner(db_session)
    await db_session.commit()
    auth = auth_cookies(owner, center)

    # Sahifa ochiladi
    r = await client.get("/admin/groups", **auth)
    assert r.status_code == 200
    assert "Guruhlar" in r.text

    # Yaratish
    r = await client.post("/admin/groups", data={"name": "Matematika 5-A"}, **auth)
    assert r.status_code == 200
    assert r.json()["success"] is True

    # Ro'yxatda ko'rinadi
    r = await client.get("/admin/groups", **auth)
    assert "Matematika 5-A" in r.text


@pytest.mark.asyncio
async def test_group_tenant_isolation(client, db_session):
    """Boshqa markaz guruhini ko'rish/tahrirlash mumkin emas (404)"""
    center_a, owner_a = await make_center_with_owner(db_session, "Markaz A", 2001)
    center_b, _ = await make_center_with_owner(db_session, "Markaz B", 2002)

    group_b = Group(name="B guruh", center_id=center_b.id, is_active=True)
    db_session.add(group_b)
    await db_session.commit()

    auth = auth_cookies(owner_a, center_a)

    # B markaz guruhini ochish -> 404
    r = await client.get(f"/admin/groups/{group_b.id}", **auth)
    assert r.status_code == 404

    # B markaz guruhini arxivlash -> xato
    r = await client.post(f"/admin/groups/{group_b.id}/archive", **auth)
    assert r.status_code == 404

    # A ro'yxatida B guruh ko'rinmaydi
    r = await client.get("/admin/groups", **auth)
    assert "B guruh" not in r.text


# --------------------------------------------------------------------------
# O'quvchilar
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_students_crud_flow(client, db_session):
    """O'quvchi qo'shish, ommaviy qo'shish, arxivlash/tiklash"""
    center, owner = await make_center_with_owner(db_session, "Markaz C", 3001)
    group = Group(name=" Ingliz tili", center_id=center.id, is_active=True)
    db_session.add(group)
    await db_session.commit()
    auth = auth_cookies(owner, center)

    # Yakka qo'shish
    r = await client.post(
        "/admin/students",
        data={"name": "Ali Valiyev", "group_id": str(group.id)},
        **auth,
    )
    assert r.json()["success"] is True

    # Ommaviy qo'shish
    r = await client.post(
        "/admin/students/bulk",
        data={
            "names": "Bekzod Karimov\n\nDilnoza Aliyeva\nBekzod Karimov",
            "group_id": str(group.id),
        },
        **auth,
    )
    assert r.json()["success"] is True
    assert r.json()["created"] == 2  # takroriy qator tozalangan

    # Jadvalda 3 ta o'quvchi
    r = await client.get("/admin/students", **auth)
    assert "Ali Valiyev" in r.text
    assert "Dilnoza Aliyeva" in r.text

    # Qidiruv filtri (HTMX partial)
    r = await client.get("/admin/partials/students-table?q=Bekzod", **auth)
    assert "Bekzod Karimov" in r.text
    assert "Ali Valiyev" not in r.text


@pytest.mark.asyncio
async def test_parent_link_flow(client, db_session):
    """Ota-ona havolasi yaratish -> parents sahifasida ko'rinadi"""
    center, owner = await make_center_with_owner(db_session, "Markaz D", 4001)
    student = Student(name="O'quvchi", center_id=center.id, is_active=True)
    db_session.add(student)
    await db_session.commit()
    auth = auth_cookies(owner, center)

    # Havola yaratish
    r = await client.post("/admin/parents/create", data={"student_id": student.id}, **auth)
    assert r.json()["success"] is True
    assert "start=p_" in r.json()["url"]

    # Ota-onalar sahifasida ko'rinadi
    r = await client.get("/admin/parents", **auth)
    assert "O'quvchi" in r.text


@pytest.mark.asyncio
async def test_super_admin_centers(client, db_session):
    """SUPER_ADMIN markazlarni ko'radi va yaratadi; owner kira olmaydi"""
    # Super admin (markazsiz)
    sa = User(
        telegram_id=next(_telegram_ids),
        first_name="Super",
        last_name="Admin",
        username="superadmin",
        role=UserRole.SUPER_ADMIN,
        center_id=None,
        is_active=True,
    )
    db_session.add(sa)
    await make_center_with_owner(db_session, "Mavjud Markaz", next(_telegram_ids))
    await db_session.commit()

    # center_id=None uchun alohida cookie
    token = create_access_token(
        data={"sub": str(sa.id), "role": "super_admin", "center_id": None}
    )
    auth = {
        "cookies": {"admin_session": token, "csrf_token": "tok"},
        "headers": {"X-CSRF-Token": "tok"},
    }

    # Sahifa ochiladi
    r = await client.get("/admin/centers", **auth)
    assert r.status_code == 200
    assert "Mavjud Markaz" in r.text

    # Markaz yaratish
    r = await client.post(
        "/admin/centers",
        data={
            "name": "Yangi Markaz",
            "owner_telegram_id": "88889999",
            "owner_first_name": "Yangi",
            "owner_last_name": "Owner",
        },
        **auth,
    )
    assert r.json()["success"] is True

    # Ro'yxatda ko'rinadi
    r = await client.get("/admin/centers", **auth)
    assert "Yangi Markaz" in r.text

    # Owner /admin/centers -> 403
    center, owner = await make_center_with_owner(db_session, "Owner Markaz", next(_telegram_ids))
    await db_session.commit()
    owner_auth = auth_cookies(owner, center)
    r = await client.get("/admin/centers", **owner_auth)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_student_tenant_isolation(client, db_session):
    """Boshqa markaz o'quvchisiga tegib bo'lmaydi"""
    center_a, owner_a = await make_center_with_owner(db_session, "A", 5001)
    center_b, _ = await make_center_with_owner(db_session, "B", 5002)
    student_b = Student(name="B o'quvchi", center_id=center_b.id, is_active=True)
    db_session.add(student_b)
    await db_session.commit()

    auth = auth_cookies(owner_a, center_a)
    r = await client.get(f"/admin/students/{student_b.id}", **auth)
    assert r.status_code == 404
