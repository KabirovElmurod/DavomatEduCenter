"""
Admin UI umumiy yordamchilar (roadmap 7-bosqich)

Jinja2Templates, render wrapper, Telegram deep link, admin context.
"""

from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import CSRF_COOKIE
from app.models.center import Center
from app.models.user import User

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

SESSION_MAX_AGE = 12 * 3600  # 12 soat

_bot_username_cache: str | None = None


async def get_bot_username() -> str:
    """
    Bot username'ni aniqlash.

    `BOT_USERNAME` sozlangan bo'lsa uni ishlatadi, aks holda
    Bot API `getMe` orqali oladi (natija keshlangan).
    """
    global _bot_username_cache
    if settings.BOT_USERNAME:
        return settings.BOT_USERNAME
    if _bot_username_cache is not None:
        return _bot_username_cache
    try:
        from app.bot.webhook import bot

        me = await bot.get_me()
        _bot_username_cache = me.username or ""
    except Exception:
        _bot_username_cache = ""
    return _bot_username_cache


async def telegram_link(token: str) -> str:
    """Bot deep link: https://t.me/<bot>?start=<token>"""
    username = await get_bot_username()
    return f"https://t.me/{username}?start={token}"


async def get_admin_context(db: AsyncSession, admin: dict) -> dict:
    """
    Har sahifa uchun umumiy context: user, center, csrf, bot_username.
    """
    user = await db.get(User, admin["user_id"])
    center = (
        await db.get(Center, admin["center_id"])
        if admin.get("center_id") is not None
        else None
    )
    return {
        "admin": admin,
        "user": user,
        "center": center,
        "bot_username": await get_bot_username(),
    }


def render(request: Request, template: str, ctx: dict):
    """Template render + CSRF token inject (hx-headers uchun)."""
    ctx = dict(ctx)
    ctx["csrf_token"] = request.cookies.get(CSRF_COOKIE, "")
    ctx["request"] = request
    return templates.TemplateResponse(request, template, ctx)
