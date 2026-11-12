"""
Admin login link tokenlari (bot orqali bir martalik kirish).

Bot owner/admin/super_admin user'ga bir martalik link beradi;
link ochilganda token Redis'dan GETDEL bilan olinadi (qayta ishlatilmaydi).
"""
import secrets

import redis.asyncio as aioredis

from app.core.config import settings

LOGIN_TOKEN_TTL = 600  # 10 daqiqa
_PREFIX = "admin_login:"


def _client() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL)


async def create_login_token(user_id: int, redis: aioredis.Redis | None = None) -> str:
    """Bir martalik login token yaratish (10 daqiqa TTL)"""
    token = "lg_" + secrets.token_urlsafe(32)
    r = redis or _client()
    try:
        await r.set(f"{_PREFIX}{token}", str(user_id), ex=LOGIN_TOKEN_TTL)
    finally:
        if redis is None:
            await r.aclose()
    return token


async def consume_login_token(
    token: str, redis: aioredis.Redis | None = None
) -> int | None:
    """
    Tokenni ishlatish — bir martalik (GETDEL).

    Returns: user_id yoki None (topilmadi/ muddati o'tgan/ allaqachon ishlatilgan)
    """
    r = redis or _client()
    try:
        raw = await r.getdel(f"{_PREFIX}{token}")
    finally:
        if redis is None:
            await r.aclose()
    if raw is None:
        return None
    return int(raw)
