"""
Group repository (roadmap 4.7, 4.8)

Group CRUD operatsiyalari - tenant va ustoz izolyatsiyasi bilan.
"""

from sqlalchemy import select

from app.models.group import Group
from app.repositories.base import BaseRepository


class GroupRepository(BaseRepository):
    """Group repository"""

    async def get_by_id(self, group_id: int) -> Group | None:
        """
        Group ma'lumotlarini olish (faqat o'z markazidan).
        """
        stmt = select(Group).where(
            Group.id == group_id,
            Group.center_id == self.center_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Group]:
        """
        Barcha guruhlar ro'yxati (faqat o'z markazidan).
        """
        stmt = select(Group).where(
            Group.center_id == self.center_id,
            Group.is_active,
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_by_teacher(self, teacher_id: int) -> list[Group]:
        """
        Ustozning guruhlari ro'yxati (4.8 - ustoz izolyatsiyasi).

        Faqat o'z markazidan va berilgan ustoznikigina.
        """
        stmt = select(Group).where(
            Group.teacher_id == teacher_id,
            Group.center_id == self.center_id,
            Group.is_active,
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
