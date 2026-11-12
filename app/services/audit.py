"""
Audit servisi (roadmap 5.1)

Har yozuvchi amal old/new qiymat bilan audit_log'ga yozadi.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.base import AuditAction


class AuditService:
    """Audit log servisi"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log(
        self,
        center_id: int,
        actor_id: int,
        action: AuditAction,
        entity: str,
        entity_id: int,
        old: dict | None = None,
        new: dict | None = None,
    ) -> AuditLog:
        """
        Audit log yozish.

        Args:
            center_id: Markaz ID
            actor_id: Kim bajargan (user ID)
            action: Amal turi (create, update, delete, etc.)
            entity: Entity nomi (user, group, student, etc.)
            entity_id: Entity ID
            old: Eski qiymatlar (update/delete uchun)
            new: Yangi qiymatlar (create/update uchun)

        Returns:
            AuditLog yozuvi
        """
        audit_log = AuditLog(
            center_id=center_id,
            actor_id=actor_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            old=old,
            new=new,
        )
        self.session.add(audit_log)
        await self.session.flush()
        return audit_log

    async def log_create(
        self,
        center_id: int,
        actor_id: int,
        entity: str,
        entity_id: int,
        new: dict,
    ) -> AuditLog:
        """Create amalini log qilish"""
        return await self.log(
            center_id=center_id,
            actor_id=actor_id,
            action=AuditAction.CREATE,
            entity=entity,
            entity_id=entity_id,
            new=new,
        )

    async def log_update(
        self,
        center_id: int,
        actor_id: int,
        entity: str,
        entity_id: int,
        old: dict,
        new: dict,
    ) -> AuditLog:
        """Update amalini log qilish"""
        return await self.log(
            center_id=center_id,
            actor_id=actor_id,
            action=AuditAction.UPDATE,
            entity=entity,
            entity_id=entity_id,
            old=old,
            new=new,
        )

    async def log_delete(
        self,
        center_id: int,
        actor_id: int,
        entity: str,
        entity_id: int,
        old: dict,
    ) -> AuditLog:
        """Delete amalini log qilish"""
        return await self.log(
            center_id=center_id,
            actor_id=actor_id,
            action=AuditAction.DELETE,
            entity=entity,
            entity_id=entity_id,
            old=old,
        )
