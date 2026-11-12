"""
Invite servisi (roadmap 5.3)

Ustoz/admin uchun token yaratish va ishlatish (bir martalik, muddatli).
"""
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import UserRole
from app.models.invite import Invite
from app.services.audit import AuditService


class InviteService:
    """Invite token servisi"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    def _generate_token(self) -> str:
        """Xavfsiz token generatsiya qilish (t_ prefix bilan)"""
        return "t_" + secrets.token_urlsafe(32)

    async def create(
        self,
        center_id: int,
        actor_id: int,
        role: UserRole,
        expires_in_hours: int = 168,  # 7 days default
    ) -> Invite:
        """
        Yangi invite token yaratish.

        Args:
            center_id: Markaz ID
            actor_id: Kim yaratmoqda
            role: Taklif qilinayotgan rol (teacher/admin)
            expires_in_hours: Muddat (soat)

        Returns:
            Invite token
        """
        if role not in (UserRole.TEACHER, UserRole.ADMIN):
            raise ValueError("Faqat teacher yoki admin rollari uchun token yaratish mumkin")

        token = self._generate_token()
        expires_at = datetime.now(UTC) + timedelta(hours=expires_in_hours)

        invite = Invite(
            token=token,
            role=role,
            center_id=center_id,
            expires_at=expires_at,
            used_at=None,
        )
        self.session.add(invite)
        await self.session.flush()

        # Audit log
        await self.audit.log_create(
            center_id=center_id,
            actor_id=actor_id,
            entity="invite",
            entity_id=invite.id,
            new={
                "role": role.value,
                "expires_at": expires_at.isoformat(),
            },
        )

        return invite

    async def use(
        self,
        token: str,
        telegram_id: int,
        first_name: str,
        last_name: str | None = None,
        username: str | None = None,
    ) -> tuple[Invite, dict] | None:
        """
        Invite token ishlatish.

        Args:
            token: Invite token
            telegram_id: Telegram ID
            first_name: Ism
            last_name: Familiya
            username: Username

        Returns:
            (Invite, user_data) tuple yoki None agar token noto'g'ri bo'lsa

        user_data: {
            "center_id": int,
            "role": UserRole,
            "telegram_id": int,
            "first_name": str,
            "last_name": Optional[str],
            "username": Optional[str],
        }
        """
        # Find invite
        stmt = select(Invite).where(Invite.token == token)
        result = await self.session.execute(stmt)
        invite = result.scalar_one_or_none()

        if not invite:
            return None

        # Check if already used
        if invite.used_at is not None:
            return None

        # Check if expired
        if datetime.now(UTC) > invite.expires_at:
            return None

        # Mark as used
        invite.used_at = datetime.now(UTC)
        await self.session.flush()

        # Prepare user data
        user_data = {
            "center_id": invite.center_id,
            "role": invite.role,
            "telegram_id": telegram_id,
            "first_name": first_name,
            "last_name": last_name,
            "username": username,
        }

        # Audit log will be written after user creation in the handler
        # (actor_id needs user.id, not telegram_id)

        return invite, user_data

    async def revoke(
        self,
        invite_id: int,
        center_id: int,
        actor_id: int,
    ) -> Invite | None:
        """
        Invite token'ni bekor qilish (delete or expire).

        Args:
            invite_id: Invite ID
            center_id: Markaz ID
            actor_id: Kim bekor qilmoqda

        Returns:
            Bekor qilingan Invite yoki None
        """
        invite = await self.session.get(Invite, invite_id)
        if not invite or invite.center_id != center_id:
            return None

        # Save old values
        old_values = {
            "token": invite.token,
            "role": invite.role.value,
            "expires_at": invite.expires_at.isoformat(),
            "used_at": invite.used_at.isoformat() if invite.used_at else None,
        }

        # Delete invite
        await self.session.delete(invite)
        await self.session.flush()

        # Audit log
        await self.audit.log_delete(
            center_id=center_id,
            actor_id=actor_id,
            entity="invite",
            entity_id=invite_id,
            old=old_values,
        )

        return invite

    async def list_active(self, center_id: int) -> list[Invite]:
        """
        Faol (ishlatilmagan va muddati tugamagan) tokenlar ro'yxati.

        Args:
            center_id: Markaz ID

        Returns:
            Faol tokenlar ro'yxati
        """
        stmt = select(Invite).where(
            Invite.center_id == center_id,
            Invite.used_at.is_(None),
            Invite.expires_at > datetime.now(UTC),
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
