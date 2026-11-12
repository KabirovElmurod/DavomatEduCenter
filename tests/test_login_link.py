"""
Bot orqali bir martalik admin login link testlari.

Token: Redis'da 10 daqiqa, GETDEL — bir martalik.
Endpoint: /admin/login-link?token=...
"""

import itertools

import pytest

from app.models.base import UserRole
from app.models.center import Center
from app.models.user import User
from app.services.login_token import (
    _PREFIX,
    consume_login_token,
    create_login_token,
)

_telegram_ids = itertools.count(970000)


class FakeRedis:
    """Minimal Redis mock — set(ex) va getdel"""

    def __init__(self):
        self.store: dict[str, str] = {}

    async def set(self, key, value, ex=None):
        self.store[key] = value
        return True

    async def getdel(self, key):
        return self.store.pop(key, None)


# --------------------------------------------------------------------------
# Service
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_login_token_one_time():
    """Token bir marta ishlatiladi — ikkinchi consume None qaytaradi"""
    fake = FakeRedis()
    token = await create_login_token(42, redis=fake)
    assert token.startswith("lg_")
    assert fake.store[f"{_PREFIX}{token}"] == "42"

    assert await consume_login_token(token, redis=fake) == 42
    assert await consume_login_token(token, redis=fake) is None


@pytest.mark.asyncio
async def test_login_token_unknown():
    """Noma'lum token None qaytaradi"""
    fake = FakeRedis()
    assert await consume_login_token("lg_nonexistent", redis=fake) is None


# --------------------------------------------------------------------------
# Endpoint
# --------------------------------------------------------------------------
async def _make_user(db, role=UserRole.OWNER, center_id=None):
    if center_id is None:
        center = Center(name="C")
        db.add(center)
        await db.flush()
        center_id = center.id
    user = User(
        telegram_id=next(_telegram_ids),
        first_name="Test",
        role=role,
        center_id=center_id if role != UserRole.SUPER_ADMIN else None,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest.mark.asyncio
async def test_login_link_success(client, db_session, monkeypatch):
    """To'g'ri token -> sessiya cookie + role bo'yicha redirect"""
    import app.admin.router_auth as ra

    owner = await _make_user(db_session, UserRole.OWNER)
    await db_session.commit()

    async def fake_consume(token, redis=None):
        return owner.id if token == "good" else None

    monkeypatch.setattr(ra, "consume_login_token", fake_consume)

    r = await client.get("/admin/login-link?token=good", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/groups"
    assert "admin_session" in r.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_login_link_super_admin(client, db_session, monkeypatch):
    """super_admin -> /admin/centers ga redirect"""
    import app.admin.router_auth as ra

    sa = await _make_user(db_session, UserRole.SUPER_ADMIN)
    await db_session.commit()

    async def fake_consume(token, redis=None):
        return sa.id

    monkeypatch.setattr(ra, "consume_login_token", fake_consume)

    r = await client.get("/admin/login-link?token=x", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/centers"


@pytest.mark.asyncio
async def test_login_link_invalid_token(client, monkeypatch):
    """Noto'g'ri/eskirgan token -> login sahifasiga xato bilan"""
    import app.admin.router_auth as ra

    async def fake_consume(token, redis=None):
        return None

    monkeypatch.setattr(ra, "consume_login_token", fake_consume)

    r = await client.get("/admin/login-link?token=bad", follow_redirects=False)
    assert r.status_code == 303
    assert "/admin/login" in r.headers["location"]


@pytest.mark.asyncio
async def test_login_link_parent_rejected(client, db_session, monkeypatch):
    """Parent roli admin login link orqali kira olmaydi"""
    import app.admin.router_auth as ra

    parent = await _make_user(db_session, UserRole.PARENT)
    await db_session.commit()

    async def fake_consume(token, redis=None):
        return parent.id

    monkeypatch.setattr(ra, "consume_login_token", fake_consume)

    r = await client.get("/admin/login-link?token=x", follow_redirects=False)
    assert r.status_code == 303
    assert "/admin/login" in r.headers["location"]
    assert "admin_session" not in r.headers.get("set-cookie", "")
