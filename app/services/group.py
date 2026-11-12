"""
Group servisi (roadmap 5.4)

Guruh yaratish, tahrirlash, arxivlash.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.group import Group
from app.services.audit import AuditService


class GroupService:
    """Group servisi"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def create(
        self,
        center_id: int,
        actor_id: int,
        name: str,
        teacher_id: int | None = None,
    ) -> Group:
        """
        Yangi guruh yaratish.

        Args:
            center_id: Markaz ID
            actor_id: Kim yaratmoqda
            name: Guruh nomi
            teacher_id: Ustoz ID (ixtiyoriy)

        Returns:
            Group
        """
        group = Group(
            name=name,
            center_id=center_id,
            teacher_id=teacher_id,
            is_active=True,
        )
        self.session.add(group)
        await self.session.flush()

        # Audit log
        await self.audit.log_create(
            center_id=center_id,
            actor_id=actor_id,
            entity="group",
            entity_id=group.id,
            new={
                "name": name,
                "teacher_id": teacher_id,
            },
        )

        return group

    async def update(
        self,
        group_id: int,
        center_id: int,
        actor_id: int,
        name: str | None = None,
        teacher_id: int | None = None,
        clear_teacher: bool = False,
    ) -> Group | None:
        """
        Guruh ma'lumotlarini yangilash.

        Args:
            group_id: Guruh ID
            center_id: Markaz ID
            actor_id: Kim yangilamoqda
            name: Yangi nom
            teacher_id: Yangi ustoz ID
            clear_teacher: True bo'lsa ustozni olib tashlaydi (ustozsiz)

        Returns:
            Yangilangan Group yoki None
        """
        group = await self.session.get(Group, group_id)
        if not group or group.center_id != center_id:
            return None

        # Save old values for audit
        old_values = {
            "name": group.name,
            "teacher_id": group.teacher_id,
        }

        # Update if provided
        if name is not None:
            group.name = name
        if teacher_id is not None:
            group.teacher_id = teacher_id
        if clear_teacher:
            group.teacher_id = None

        await self.session.flush()

        # Audit log
        new_values = {
            "name": group.name,
            "teacher_id": group.teacher_id,
        }

        await self.audit.log_update(
            center_id=center_id,
            actor_id=actor_id,
            entity="group",
            entity_id=group_id,
            old=old_values,
            new=new_values,
        )

        return group

    async def archive(
        self,
        group_id: int,
        center_id: int,
        actor_id: int,
    ) -> Group | None:
        """
        Guruhni arxivlash (soft delete).

        Args:
            group_id: Guruh ID
            center_id: Markaz ID
            actor_id: Kim arxivlayapti

        Returns:
            Arxivlangan Group yoki None
        """
        group = await self.session.get(Group, group_id)
        if not group or group.center_id != center_id:
            return None

        # Save old values for audit
        old_values = {
            "name": group.name,
            "teacher_id": group.teacher_id,
            "is_active": group.is_active,
        }

        # Archive
        group.is_active = False
        await self.session.flush()

        # Audit log
        await self.audit.log_update(
            center_id=center_id,
            actor_id=actor_id,
            entity="group",
            entity_id=group_id,
            old=old_values,
            new={
                "name": group.name,
                "teacher_id": group.teacher_id,
                "is_active": False,
            },
        )

        return group

    async def get_by_id(self, group_id: int) -> Group | None:
        """Guruh ma'lumotlarini olish"""
        return await self.session.get(Group, group_id)

    async def change_teacher(
        self,
        group_id: int,
        center_id: int,
        actor_id: int,
        new_teacher_id: int,
    ) -> Group | None:
        """
        Guruh ustozini almashtirish (5.5).

        Eski darslar eski ustoz nomida qoladi (Lesson.teacher_id o'zgarmaydi).
        Faqat Group.teacher_id o'zgaradi.

        Args:
            group_id: Guruh ID
            center_id: Markaz ID
            actor_id: Kim o'zgartirmoqda
            new_teacher_id: Yangi ustoz ID

        Returns:
            Yangilangan Group yoki None
        """
        group = await self.session.get(Group, group_id)
        if not group or group.center_id != center_id:
            return None

        # Save old values for audit
        old_values = {
            "name": group.name,
            "teacher_id": group.teacher_id,
        }

        # Change teacher
        group.teacher_id = new_teacher_id
        await self.session.flush()

        # Audit log
        await self.audit.log_update(
            center_id=center_id,
            actor_id=actor_id,
            entity="group",
            entity_id=group_id,
            old=old_values,
            new={
                "name": group.name,
                "teacher_id": new_teacher_id,
            },
        )

        return group
