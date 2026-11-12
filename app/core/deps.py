"""
FastAPI dependency funksiyalari (roadmap 4-bosqich)

get_current_user, require_role va boshqa auth dependency'lari.
"""

import secrets

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token

security = HTTPBearer()

# Admin UI cookie nomlari
ADMIN_SESSION_COOKIE = "admin_session"
CSRF_COOKIE = "csrf_token"


class AdminAuthError(Exception):
    """Admin sessiya yo'q yoki eskirgan"""


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    JWT tokendan foydalanuvchi ma'lumotlarini olish.

    Returns:
        dict: {user_id, role, center_id}

    Raises:
        HTTPException: token noto'g'ri bo'lsa
    """
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Noto'g'ri token",
            )

        return {
            "user_id": int(user_id),
            "role": payload.get("role"),
            "center_id": payload.get("center_id"),
        }
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Noto'g'ri token",
        )


def require_role(*allowed_roles: str):
    """
    Rolga asoslangan access control.

    Args:
        *allowed_roles: ruxsat etilgan rollar (teacher, admin, owner)

    Returns:
        dependency function
    """

    async def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        user_role = current_user.get("role")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Ruxsat yo'q. Kerak: {allowed_roles}, Sizda: {user_role}",
            )
        return current_user

    return role_checker


# Owner-only access (adminlar qo'sha olmaydi)
def require_owner():
    """
    Faqat owner uchun access control.

    Adminlar faqat owner qo'sha oladi (4.6).
    """
    return require_role("owner")


# Admin UI uchun cookie-based sessiya (roadmap 4.4, 7-bosqich)
async def get_current_admin(request: Request) -> dict:
    """
    Admin UI uchun cookie sessiya orqali foydalanuvchi olish.

    `admin_session` cookie ichidagi JWT decode qilinadi.
    Faqat owner/admin/super_admin rollar ruxsat etilgan.
    Sahifa so'rovlarida login sahifasiga redirect, HTMX so'rovlarida 401.

    Returns:
        dict: {user_id, role, center_id}  # center_id super_admin'da None bo'lishi mumkin
    """
    token = request.cookies.get(ADMIN_SESSION_COOKIE)
    if not token:
        raise AdminAuthError()

    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        role = payload.get("role")
        center_id = payload.get("center_id")
        if user_id is None or role not in ("owner", "admin", "super_admin"):
            raise AdminAuthError()
    except ValueError:
        raise AdminAuthError()

    return {
        "user_id": int(user_id),
        "role": role,
        "center_id": int(center_id) if center_id is not None else None,
    }


async def verify_csrf(request: Request) -> None:
    """
    CSRF tekshiruvi (roadmap 4.4).

    `X-CSRF-Token` header `csrf_token` cookie bilan solishtiriladi.
    Barcha admin POST endpoint'larida qo'llaniladi.
    """
    cookie_token = request.cookies.get(CSRF_COOKIE)
    header_token = request.headers.get("X-CSRF-Token")
    if not cookie_token or not header_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token topilmadi",
        )
    if not secrets.compare_digest(cookie_token, header_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token mos kelmadi",
        )


async def admin_auth_exception_handler(request: Request, exc: AdminAuthError):
    """AdminAuthError exception handler - login sahifasiga redirect"""
    is_htmx = request.headers.get("HX-Request") == "true"
    if request.method == "GET" and not is_htmx:
        return RedirectResponse("/admin/login", status_code=303)
    return JSONResponse({"detail": "Unauthorized"}, status_code=401)


# Ustoz izolyatsiyasi uchun dependency (roadmap 4.8)
async def get_current_teacher_user(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Hozirgi ustoz user'ni olish va teacher role'ni tekshirish.

    Ustoz faqat o'z guruhlarini ko'ra oladi.
    """
    if current_user.get("role") != "teacher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Faqat ustozlar uchun",
        )
    return current_user
