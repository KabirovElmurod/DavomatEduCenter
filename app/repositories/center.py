"""
Center repository (roadmap 4.7)

Center CRUD operatsiyalari - tenant izolyatsiya bilan.
"""

from sqlalchemy import select

from app.models.center import Center
from app.repositories.base import BaseRepository


class CenterRepository(BaseRepository):
    """Center repository"""

    async def get_by_id(self, center_id: int) -> Center | None:
        """
        Center ma'lumotlarini olish.

        center_id parametri tenant uchun tekshiriladi.
        """
        if center_id != self.center_id:
            return None

        stmt = select(Center).where(Center.id == center_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_current(self) -> Center | None:
        """Hozirgi tenant (center) ma'lumotlarini olish"""
        return await self.get_by_id(self.center_id)
