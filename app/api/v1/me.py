"""GET /api/v1/me — joriy foydalanuvchi profili"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/me")
async def get_me(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """JWT token egasining DB'dagi dolzarb ma'lumotlari"""
    user = await db.get(User, current_user["user_id"])
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User topilmadi yoki nofaol")

    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "username": user.username,
        "role": user.role.value,
        "center_id": user.center_id,
    }
