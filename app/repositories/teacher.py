"""
Teacher repository (roadmap 4.7, 4.8)

Teacher CRUD operatsiyalari - tenant va ustoz izolyatsiyasi bilan.
"""

from sqlalchemy import select

from app.models.teacher import Teacher
from app.repositories.base import BaseRepository


class TeacherRepository(BaseRepository):
    """Teacher repository"""

    async def get_by_id(self, teacher_id: int) -> Teacher | None:
        """
        Teacher ma'lumotlarini olish (faqat o'z markazidan).
        """
        stmt = select(Teacher).where(
            Teacher.id == teacher_id,
            Teacher.center_id == self.center_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: int) -> Teacher | None:
        """
        User ID bo'yicha teacher olish (faqat o'z markazidan).

        4.8 - ustoz izolyatsiyasi uchun kerak.
        """
        stmt = select(Teacher).where(
            Teacher.user_id == user_id,
            Teacher.center_id == self.center_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Teacher]:
        """
        Barcha ustozlar ro'yxati (faqat o'z markazidan).
        """
        stmt = select(Teacher).where(
            Teacher.center_id == self.center_id,
            Teacher.is_active,
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_teacher_id_for_user(self, user_id: int) -> int | None:
        """
        User ID bo'yicha teacher ID'ni olish (faqat o'z markazidan).

        4.8 - ustoz izolyatsiyasi uchun kerak.
        Guruhlarni filter qilishda ishlatiladi.
        """
        teacher = await self.get_by_user_id(user_id)
        return teacher.id if teacher else None
