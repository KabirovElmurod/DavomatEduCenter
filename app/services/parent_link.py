"""
Parent link servisi (roadmap 5.10)

Ota-ona havolasi: yaratish, qayta generatsiya, bog'lanishni uzish.
"""
import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parent_link import ParentLink
from app.services.audit import AuditService


class ParentLinkService:
    """Parent link servisi"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    def _generate_token(self) -> str:
        """Xavfsiz token generatsiya qilish (p_ prefix bilan)"""
        return "p_" + secrets.token_urlsafe(32)

    async def create(
        self,
        student_id: int,
        center_id: int,
        actor_id: int,
    ) -> ParentLink | None:
        """
        Ota-ona havolasi yaratish.

        Args:
            student_id: O'quvchi ID
            center_id: Markaz ID
            actor_id: Kim yaratmoqda

        Returns:
            ParentLink yoki None
        """
        # Check if student exists and belongs to center
        from app.models.student import Student
        student = await self.session.get(Student, student_id)
        if not student or student.center_id != center_id:
            return None

        # Generate token
        token = self._generate_token()

        # Create parent link
        parent_link = ParentLink(
            student_id=student_id,
            user_id=None,  # Will be set when parent connects
            invite_token=token,
            revoked_at=None,
        )
        self.session.add(parent_link)
        await self.session.flush()

        # Audit log
        await self.audit.log_create(
            center_id=center_id,
            actor_id=actor_id,
            entity="parent_link",
            entity_id=parent_link.id,
            new={
                "student_id": student_id,
                "token": token,
            },
        )

        return parent_link

    async def regenerate(
        self,
        parent_link_id: int,
        center_id: int,
        actor_id: int,
    ) -> ParentLink | None:
        """
        Ota-ona havolasini qayta generatsiya qilish.

        Eski token revoked_at bo'ladi, yangi token yaratiladi.

        Args:
            parent_link_id: Parent link ID
            center_id: Markaz ID
            actor_id: Kim qayta generatsiya qilmoqda

        Returns:
            Yangilangan ParentLink yoki None
        """
        parent_link = await self.session.get(ParentLink, parent_link_id)
        if not parent_link:
            return None

        # Check center ownership via student
        from app.models.student import Student
        student = await self.session.get(Student, parent_link.student_id)
        if not student or student.center_id != center_id:
            return None

        # Save old values for audit
        old_values = {
            "student_id": parent_link.student_id,
            "token": parent_link.invite_token,
            "revoked_at": parent_link.revoked_at.isoformat() if parent_link.revoked_at else None,
        }

        # Revoke old token
        parent_link.revoked_at = datetime.now(UTC)

        # Generate new token
        new_token = self._generate_token()
        parent_link.invite_token = new_token

        await self.session.flush()

        # Audit log
        await self.audit.log_update(
            center_id=center_id,
            actor_id=actor_id,
            entity="parent_link",
            entity_id=parent_link_id,
            old=old_values,
            new={
                "student_id": parent_link.student_id,
                "token": new_token,
                "revoked_at": parent_link.revoked_at.isoformat(),
            },
        )

        return parent_link

    async def revoke(
        self,
        parent_link_id: int,
        center_id: int,
        actor_id: int,
    ) -> ParentLink | None:
        """
        Ota-ona bog'lanishini uzish (revoke).

        Args:
            parent_link_id: Parent link ID
            center_id: Markaz ID
            actor_id: Kim uzmoqda

        Returns:
            Bekor qilingan ParentLink yoki None
        """
        parent_link = await self.session.get(ParentLink, parent_link_id)
        if not parent_link:
            return None

        # Check center ownership via student
        from app.models.student import Student
        student = await self.session.get(Student, parent_link.student_id)
        if not student or student.center_id != center_id:
            return None

        # Save old values for audit
        old_values = {
            "student_id": parent_link.student_id,
            "token": parent_link.invite_token,
            "revoked_at": parent_link.revoked_at.isoformat() if parent_link.revoked_at else None,
        }

        # Revoke
        parent_link.revoked_at = datetime.now(UTC)
        await self.session.flush()

        # Audit log
        await self.audit.log_update(
            center_id=center_id,
            actor_id=actor_id,
            entity="parent_link",
            entity_id=parent_link_id,
            old=old_values,
            new={
                "student_id": parent_link.student_id,
                "token": parent_link.invite_token,
                "revoked_at": parent_link.revoked_at.isoformat(),
            },
        )

        return parent_link

    async def connect_parent(
        self,
        token: str,
    ) -> ParentLink | None:
        """
        Ota-ona bog'lash tokenini tekshirish.

        Token tekshiruvdan o'tsa, link qaytariladi — user_id
        bog'lash handler'da user topilgach o'rnatiladi.
        """
        stmt = select(ParentLink).where(ParentLink.invite_token == token)
        result = await self.session.execute(stmt)
        parent_link = result.scalar_one_or_none()

        if not parent_link:
            return None

        if parent_link.revoked_at is not None:
            return None

        if parent_link.user_id is not None:
            return None

        return parent_link

    async def get_by_student(self, student_id: int) -> ParentLink | None:
        """O'quvchi bo'yicha parent link olish"""
        stmt = select(ParentLink).where(ParentLink.student_id == student_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
