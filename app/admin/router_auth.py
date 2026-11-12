"""
Admin auth router (roadmap 4.3, 4.4, 7.1)

Telegram Login Widget orqali admin login:
- GET /admin/login - login sahifasi
- POST /admin/login - hash validatsiya + cookie sessiya + CSRF token
- POST /admin/logout - cookie'larni o'chirish
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.common import SESSION_MAX_AGE, get_bot_username, render
from app.core.config import settings
from app.core.db import get_db
from app.core.deps import (
    ADMIN_SESSION_COOKIE,
    CSRF_COOKIE,
    AdminAuthError,
    get_current_admin,
    verify_csrf,
)
from app.core.security import (
    create_access_token,
    generate_csrf_token,
    validate_telegram_login_widget,
)
from app.models.base import UserRole
from app.models.user import User
from app.services.login_token import consume_login_token

router = APIRouter()


def _dev_login_allowed() -> bool:
    """Dev-login faqat DEV_MODE + localhost PUBLIC_URL'da (public URL'da xavfli)"""
    return settings.DEV_MODE and settings.PUBLIC_URL.startswith("http://localhost")


def _post_login_redirect(user: User) -> str:
    """super_admin markazsiz — /admin/centers'ga, qolganlar guruhlarga"""
    if user.role == UserRole.SUPER_ADMIN:
        return "/admin/centers"
    return "/admin/groups"


class TelegramLoginRequest(BaseModel):
    """Telegram Login Widget auth request"""

    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


class LoginResponse(BaseModel):
    """Login response"""

    success: bool
    message: str
    redirect: str | None = None


@router.get("/login")
async def login_page(request: Request, db: AsyncSession = Depends(get_db), error: str = ""):
    """Login sahifasi (Telegram Login Widget)"""
    # Agar allaqachon kirmagan bo'lsa - admin ga redirect
    try:
        admin = await get_current_admin(request)
        target = "/admin/centers" if admin.get("role") == "super_admin" else "/admin/groups"
        return RedirectResponse(target, status_code=303)
    except AdminAuthError:
        pass

    dev_users = []
    if _dev_login_allowed():
        result = await db.execute(
            select(User).where(
                User.role.in_([UserRole.SUPER_ADMIN, UserRole.OWNER, UserRole.ADMIN]),
                User.is_active == True,  # noqa: E712
            )
        )
        dev_users = [
            {"telegram_id": u.telegram_id, "name": f"{u.first_name} {u.last_name or ''}".strip()}
            for u in result.scalars().all()
        ]

    return render(
        request,
        "login.html",
        {
            "bot_username": await get_bot_username(),
            "dev_mode": _dev_login_allowed(),
            "dev_users": dev_users,
            "error": error or None,
        },
    )


@router.post("/login", response_model=LoginResponse)
async def admin_login(
    request: TelegramLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Telegram Login Widget orqali admin login.

    Hash'ni validatsiya qiladi, DB'dan user'ni tekshiradi (owner/admin),
    JWT'ni HttpOnly cookie'ga yozadi, CSRF token cookie'sini o'rnatadi.
    """
    data = request.model_dump()

    try:
        validate_telegram_login_widget(dict(data))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Hash validatsiya xatosi: {str(e)}",
        )

    # DB'dan user'ni olish
    result = await db.execute(select(User).where(User.telegram_id == request.id))
    user = result.scalar_one_or_none()

    if not user or user.role.value not in ("owner", "admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin ruxsati yo'q",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User nofaol",
        )

    _set_session_cookies(response, user)

    return LoginResponse(
        success=True,
        message="Login muvaffaqiyatli",
        redirect=_post_login_redirect(user),
    )


def _set_session_cookies(response: Response, user: User) -> None:
    """Sessiya + CSRF cookie'larini o'rnatish"""
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value, "center_id": user.center_id}
    )
    secure = settings.PUBLIC_URL.startswith("https")

    response.set_cookie(
        key=ADMIN_SESSION_COOKIE,
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=secure,
        max_age=SESSION_MAX_AGE,
    )
    response.set_cookie(
        key=CSRF_COOKIE,
        value=generate_csrf_token(),
        httponly=False,
        samesite="lax",
        secure=secure,
        max_age=SESSION_MAX_AGE,
    )


@router.get("/login-link")
async def login_link(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Bot orqali bir martalik login linki.

    Token Redis'da saqlanadi (10 daqiqa, GETDEL — bir martalik).
    Faqat owner/admin/super_admin kira oladi.
    """
    user_id = await consume_login_token(token)
    if user_id is None:
        return RedirectResponse("/admin/login?error=Havola+eskirgan+yoki+noto'g'ri", status_code=303)

    user = await db.get(User, user_id)
    if (
        not user
        or user.role.value not in ("owner", "admin", "super_admin")
        or not user.is_active
    ):
        return RedirectResponse("/admin/login?error=Ruxsat+yo'q", status_code=303)

    redirect = RedirectResponse(_post_login_redirect(user), status_code=303)
    _set_session_cookies(redirect, user)
    return redirect


@router.get("/dev-login")
async def dev_login(
    telegram_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Local dev login (faqat DEV_MODE=true bo'lganda).

    Telegram'siz: /admin/dev-login?telegram_id=<id> -> owner/admin bo'lsa kiradi.
    """
    if not _dev_login_allowed():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()

    if not user or user.role.value not in ("owner", "admin", "super_admin") or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner/admin user topilmadi",
        )

    redirect = RedirectResponse(_post_login_redirect(user), status_code=303)
    _set_session_cookies(redirect, user)
    return redirect


@router.post("/logout")
async def admin_logout(
    admin: dict = Depends(get_current_admin),
    _: None = Depends(verify_csrf),
):
    """Admin logout - cookie'larni o'chirish"""
    redirect = RedirectResponse("/admin/login", status_code=303)
    redirect.delete_cookie(ADMIN_SESSION_COOKIE)
    redirect.delete_cookie(CSRF_COOKIE)
    return redirect
