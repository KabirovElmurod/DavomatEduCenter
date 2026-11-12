"""Ustoz API uchun umumiy dependency'lar (roadmap 4.8, 8-bosqich)"""
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.group import Group
from app.models.teacher import Teacher

ALLOWED_ROLES = {"teacher", "owner", "admin"}


async def get_teacher_context(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Ustoz/owner/admin konteksti.

    teacher uchun Teacher yozuvi topiladi; owner/admin uchun teacher=None.
    """
    if current_user.get("role") not in ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")

    teacher = None
    if current_user["role"] == "teacher":
        stmt = select(Teacher).where(
            Teacher.user_id == current_user["user_id"],
            Teacher.is_active.is_(True),
        )
        teacher = (await db.execute(stmt)).scalar_one_or_none()
        if teacher is None:
            raise HTTPException(status_code=403, detail="Ustoz profili topilmadi")

    return {**current_user, "teacher": teacher}


async def get_accessible_group(
    group_id: int,
    ctx: dict = Depends(get_teacher_context),
    db: AsyncSession = Depends(get_db),
) -> Group:
    """
    Guruhga kirish huquqini tekshirish.

    teacher: faqat o'z guruhlari (group.teacher_id == teacher.id)
    owner/admin: o'z markazidagi istalgan guruh
    """
    group = await db.get(Group, group_id)
    if group is None or not group.is_active:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")

    if ctx["role"] == "teacher":
        if group.teacher_id != ctx["teacher"].id:
            raise HTTPException(status_code=403, detail="Bu guruh sizga tegishli emas")
    else:
        if group.center_id != ctx["center_id"]:
            raise HTTPException(status_code=404, detail="Guruh topilmadi")

    return group
