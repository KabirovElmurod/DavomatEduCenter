"""
Auth testlari (roadmap 4.11)

Eskirgan/soxta initData va Login Widget validatsiyasi.
"""
import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    validate_telegram_init_data,
    validate_telegram_login_widget,
)


def test_validate_init_data_missing():
    """
    Bo'sh initData xato beradi.
    """
    with pytest.raises(ValueError, match="init_data bo'sh"):
        validate_telegram_init_data("")


def test_validate_init_data_missing_hash():
    """
    Hash'siz initData xato beradi.
    """
    with pytest.raises(ValueError, match="hash topilmadi"):
        validate_telegram_init_data("auth_date=123")


def test_validate_init_data_missing_auth_date():
    """
    auth_date'siz initData xato beradi (hash ham xato bo'ladi).
    """
    with pytest.raises(ValueError):
        validate_telegram_init_data("hash=abc123")


def test_validate_init_data_invalid_auth_date():
    """
    Noto'g'ri auth_date format xato beradi.
    """
    with pytest.raises(ValueError):
        validate_telegram_init_data("auth_date=invalid&hash=abc123")


def test_validate_login_widget_missing_hash():
    """
    Hash'siz login data xato beradi.
    """
    data = {"id": 123, "first_name": "Test"}
    with pytest.raises(ValueError, match="hash topilmadi"):
        validate_telegram_login_widget(data)


def _widget_hash(data: dict) -> str:
    """Telegram Login Widget uchun to'g'ri hash (SHA256(bot_token) kaliti)"""
    import hashlib
    import hmac
    import time

    from app.core.config import settings

    check = "\n".join(f"{k}={data[k]}" for k in sorted(data) if data[k] is not None)
    secret = hashlib.sha256(settings.BOT_TOKEN.encode()).digest()
    return hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()


def test_validate_login_widget_valid():
    """To'g'ri Login Widget hash'i qabul qilinadi"""
    import time

    data = {
        "id": 12345,
        "first_name": "Test",
        "username": "testuser",
        "auth_date": int(time.time()),
    }
    data["hash"] = _widget_hash(data)
    assert validate_telegram_login_widget(dict(data)) is True


def test_validate_login_widget_wrong_hash():
    """Buzilgan hash rad etiladi"""
    import time

    data = {
        "id": 12345,
        "first_name": "Test",
        "auth_date": int(time.time()),
        "hash": "0" * 64,
    }
    with pytest.raises(ValueError, match="hash validatsiya xatosi"):
        validate_telegram_login_widget(data)


def test_validate_login_widget_stale_auth_date():
    """Eskirgan auth_date rad etiladi"""
    import time

    data = {
        "id": 12345,
        "first_name": "Test",
        "auth_date": int(time.time()) - 7200,
    }
    data["hash"] = _widget_hash(data)
    with pytest.raises(ValueError, match="auth_date juda eski"):
        validate_telegram_login_widget(data)


def test_jwt_token_roundtrip():
    """
    JWT token yaratish va decode qilish ishlaydi.
    """
    payload = {"sub": "123", "role": "teacher", "center_id": 1}
    token = create_access_token(payload)

    decoded = decode_access_token(token)
    assert decoded["sub"] == "123"
    assert decoded["role"] == "teacher"
    assert decoded["center_id"] == 1


def test_invalid_jwt_token():
    """
    Noto'g'ri JWT token xato beradi.
    """
    with pytest.raises(ValueError, match="Noto'g'ri token"):
        decode_access_token("invalid.token.here")
