"""
Auth API endpoint'lari (roadmap 4-bosqich, 8-bosqich)

POST /api/v1/auth/telegram - Telegram WebApp initData orqali auth
"""
import json
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import create_access_token, validate_telegram_init_data
from app.models.user import User

router = APIRouter()

# WebApp'dan foydalana oladigan rollar
WEBAPP_ROLES = {"teacher", "owner", "admin"}


class TelegramAuthRequest(BaseModel):
    """Telegram WebApp auth request"""
    init_data: str


class AuthResponse(BaseModel):
    """Auth response"""
    access_token: str
    token_type: str = "bearer"
    user_id: int
    role: str
    center_id: int


@router.post("/telegram", response_model=AuthResponse)
async def auth_telegram(
    request: TelegramAuthRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Telegram WebApp initData orqali auth qilish.

    initData'ni validatsiya qiladi, user'ni DB'dan topadi,
    JWT token yaratadi. Faqat teacher/owner/admin rollar.
    """
    try:
        telegram_data = validate_telegram_init_data(request.init_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"InitData validatsiya xatosi: {str(e)}",
        )

    user_str = telegram_data.get("user")
    if not user_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user ma'lumoti topilmadi",
        )

    try:
        user_data = json.loads(unquote(user_str))
        telegram_id = int(user_data["id"])
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"user ma'lumotini parse qilib bo'lmadi: {str(e)}",
        )

    stmt = select(User).where(User.telegram_id == telegram_id)
    user = (await db.execute(stmt)).scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User ro'yxatda yo'q. Iltimos, taklif havolasini bosing.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User nofaol",
        )
    if user.role.value not in WEBAPP_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu ilovaga kirish ruxsati yo'q",
        )
    if user.center_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Markazga biriktirilmagan user",
        )

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "role": user.role.value,
            "center_id": user.center_id,
        }
    )

    return AuthResponse(
        access_token=access_token,
        user_id=user.id,
        role=user.role.value,
        center_id=user.center_id,
    )
