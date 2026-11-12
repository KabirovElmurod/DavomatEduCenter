"""
Center servisi (roadmap 5.2)

Markaz yaratish - yaratuvchi avtomatik owner bo'ladi.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import UserRole
from app.models.center import Center
from app.models.user import User
from app.services.audit import AuditService


class CenterService:
    """Center servisi"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def create(
        self,
        name: str,
        creator_telegram_id: int,
        creator_first_name: str,
        address: str | None = None,
        phone: str | None = None,
        creator_last_name: str | None = None,
        creator_username: str | None = None,
    ) -> tuple[Center, User]:
        """
        Yangi markaz yaratish va yaratuvchini owner qilish.

        Args:
            name: Markaz nomi
            address: Manzil
            phone: Telefon
            creator_telegram_id: Yaratuvchi Telegram ID
            creator_first_name: Yaratuvchi ismi
            creator_last_name: Yaratuvchi familiyasi
            creator_username: Yaratuvchi username

        Returns:
            (Center, User) tuple
        """
        # Create center
        center = Center(
            name=name,
            address=address,
            phone=phone,
        )
        self.session.add(center)
        await self.session.flush()

        # Create owner user
        owner = User(
            telegram_id=creator_telegram_id,
            first_name=creator_first_name,
            last_name=creator_last_name,
            username=creator_username,
            role=UserRole.OWNER,
            center_id=center.id,
            is_active=True,
        )
        self.session.add(owner)
        await self.session.flush()

        # Audit log
        await self.audit.log_create(
            center_id=center.id,
            actor_id=owner.id,
            entity="center",
            entity_id=center.id,
            new={
                "name": name,
                "address": address,
                "phone": phone,
            },
        )

        await self.audit.log_create(
            center_id=center.id,
            actor_id=owner.id,
            entity="user",
            entity_id=owner.id,
            new={
                "telegram_id": creator_telegram_id,
                "role": "owner",
                "first_name": creator_first_name,
            },
        )

        return center, owner

    async def get_by_id(self, center_id: int) -> Center | None:
        """Markaz ma'lumotlarini olish"""
        return await self.session.get(Center, center_id)

    async def update(
        self,
        center_id: int,
        actor_id: int,
        name: str | None = None,
        address: str | None = None,
        phone: str | None = None,
    ) -> Center | None:
        """
        Markaz ma'lumotlarini yangilash.

        Args:
            center_id: Markaz ID
            actor_id: Kim yangilamoqda
            name: Yangi nom
            address: Yangi manzil
            phone: Yangi telefon

        Returns:
            Yangilangan Center yoki None
        """
        center = await self.get_by_id(center_id)
        if not center:
            return None

        # Save old values for audit
        old_values = {
            "name": center.name,
            "address": center.address,
            "phone": center.phone,
        }

        # Update if provided
        if name is not None:
            center.name = name
        if address is not None:
            center.address = address
        if phone is not None:
            center.phone = phone

        await self.session.flush()

        # Audit log
        new_values = {
            "name": center.name,
            "address": center.address,
            "phone": center.phone,
        }

        await self.audit.log_update(
            center_id=center_id,
            actor_id=actor_id,
            entity="center",
            entity_id=center_id,
            old=old_values,
            new=new_values,
        )

        return center
