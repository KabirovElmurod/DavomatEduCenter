"""
Authentifikatsiya va xavfsizlik funksiyalari (roadmap 4-bosqich)

Telegram WebApp initData validatsiyasi, JWT tokenlari,
Telegram Login Widget hash tekshiruvi, CSRF token.
"""

import hashlib
import hmac
import secrets
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, unquote

from jose import JWTError, jwt

from app.core.config import settings


# --------------------------------------------------------------------------
# Telegram WebApp initData validatsiyasi
# --------------------------------------------------------------------------
def validate_telegram_init_data(init_data: str) -> dict:
    """
    Telegram WebApp initData'ni validatsiya qiladi.

    Args:
        init_data: Telegram WebApp'dan kelgan query string

    Returns:
        dict: parse qilingan ma'lumotlar (user, auth_date, hash, etc.)

    Raises:
        ValueError: validatsiya xatosi bo'lsa
    """
    if not init_data:
        raise ValueError("init_data bo'sh")

    # Parse query string
    data = parse_qs(init_data)
    # Extract hash
    hash_val = data.pop("hash", [None])[0]
    if not hash_val:
        raise ValueError("hash topilmadi")

    # Sort keys alphabetically
    data_check_arr = []
    for key in sorted(data.keys()):
        # Decode and join multiple values with newline
        value = "\n".join(unquote(v) for v in data[key])
        data_check_arr.append(f"{key}={value}")

    # Join with \n
    data_check_string = "\n".join(data_check_arr)

    # Create HMAC-SHA256
    # Bot token is the key (web_app_data)
    secret_key = hmac.new(
        key=b"WebAppData", msg=settings.BOT_TOKEN.encode(), digestmod=hashlib.sha256
    ).digest()

    _hash = hmac.new(
        key=secret_key, msg=data_check_string.encode(), digestmod=hashlib.sha256
    ).hexdigest()

    # Compare hashes to prevent timing attacks
    if not secrets.compare_digest(_hash, hash_val):
        raise ValueError("hash validatsiya xatosi")

    # Check auth_date (must be within 1 hour)
    auth_date = data.get("auth_date", [None])[0]
    if not auth_date:
        raise ValueError("auth_date topilmadi")

    try:
        auth_timestamp = int(auth_date)
    except (ValueError, TypeError):
        raise ValueError("auth_date noto'g'ri format")

    current_timestamp = int(time.time())
    if current_timestamp - auth_timestamp > 3600:  # 1 hour
        raise ValueError("auth_date juda eski")

    # Return parsed data (decode values)
    result = {}
    for key, values in data.items():
        result[key] = unquote(values[0]) if values else None

    return result


# --------------------------------------------------------------------------
# JWT tokenlar
# --------------------------------------------------------------------------
def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """JWT access token yaratish."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(hours=24)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm="HS256")
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """JWT tokenni decode qilish."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        return payload
    except JWTError:
        raise ValueError("Noto'g'ri token")


# --------------------------------------------------------------------------
# Telegram Login Widget hash tekshiruvi
# --------------------------------------------------------------------------
def validate_telegram_login_widget(data: dict) -> bool:
    """
    Telegram Login Widget hash'ni validatsiya qiladi.

    Telegram docs: secret = SHA256(bot_token), key esa WebAppData emas.

    Args:
        data: Telegram Login Widget'dan kelgan data dict
              (id, first_name, auth_date, hash, etc.)

    Returns:
        bool: valid bo'lsa True

    Raises:
        ValueError: validatsiya xatosi bo'lsa
    """
    hash_val = data.pop("hash", None)
    if not hash_val:
        raise ValueError("hash topilmadi")

    # auth_date yangiligi (1 soat)
    auth_date = data.get("auth_date")
    try:
        auth_timestamp = int(auth_date)
    except (ValueError, TypeError):
        raise ValueError("auth_date noto'g'ri format")
    if int(time.time()) - auth_timestamp > 3600:
        raise ValueError("auth_date juda eski")

    # Sort keys alphabetically
    data_check_arr = []
    for key in sorted(data.keys()):
        value = data[key]
        if value is not None:
            data_check_arr.append(f"{key}={value}")

    data_check_string = "\n".join(data_check_arr)

    # Login Widget: secret = SHA256(bot_token) (WebAppData emas!)
    secret_key = hashlib.sha256(settings.BOT_TOKEN.encode()).digest()

    _hash = hmac.new(
        key=secret_key, msg=data_check_string.encode(), digestmod=hashlib.sha256
    ).hexdigest()

    if not secrets.compare_digest(_hash, hash_val):
        raise ValueError("hash validatsiya xatosi")

    return True


# --------------------------------------------------------------------------
# CSRF token
# --------------------------------------------------------------------------
def generate_csrf_token() -> str:
    """CSRF token yaratish."""
    return secrets.token_urlsafe(32)


def validate_csrf_token(token: str, session_token: str) -> bool:
    """CSRF token validatsiyasi."""
    return secrets.compare_digest(token, session_token)
