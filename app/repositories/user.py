"""
User repository (roadmap 4.7)

User CRUD operatsiyalari - tenant izolyatsiya bilan.
"""

from sqlalchemy import select

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    """User repository"""

    async def get_by_id(self, user_id: int) -> User | None:
        """
        User ma'lumotlarini olish (faqat o'z markazidan).
        """
        stmt = select(User).where(
            User.id == user_id,
            User.center_id == self.center_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """
        Telegram ID bo'yicha user olish (faqat o'z markazidan).
        """
        stmt = select(User).where(
            User.telegram_id == telegram_id,
            User.center_id == self.center_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_role(self, role: str) -> list[User]:
        """
        Rolga qarab userlar ro'yxati (faqat o'z markazidan).
        """
        stmt = select(User).where(
            User.role == role,
            User.center_id == self.center_id,
            User.is_active,
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_teachers(self) -> list[User]:
        """Ustozlar ro'yxati"""
        return await self.list_by_role("teacher")

    async def list_admins(self) -> list[User]:
        """Adminlar ro'yxati"""
        return await self.list_by_role("admin")
