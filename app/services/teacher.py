"""
Teacher servisi (roadmap 5.11)

Ustozni nofaol qilish - guruhlari 'ustozsiz' holatga o'tadi.
"""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.group import Group
from app.models.teacher import Teacher
from app.services.audit import AuditService


class TeacherService:
    """Teacher servisi"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def deactivate(
        self,
        teacher_id: int,
        center_id: int,
        actor_id: int,
    ) -> Teacher | None:
        """
        Ustozni nofaol qilish (5.11).

        Guruhlari 'ustozsiz' holatga o'tadi (teacher_id = None).

        Args:
            teacher_id: Ustoz ID
            center_id: Markaz ID
            actor_id: Kim nofaol qilmoqda

        Returns:
            Nofaol qilingan Teacher yoki None
        """
        teacher = await self.session.get(Teacher, teacher_id)
        if not teacher:
            return None

        # Check center ownership via user
        from app.models.user import User
        user = await self.session.get(User, teacher.user_id)
        if not user or user.center_id != center_id:
            return None

        # Save old values for audit
        old_values = {
            "user_id": teacher.user_id,
            "specialization": teacher.specialization,
            "is_active": teacher.is_active,
        }

        # Deactivate teacher
        teacher.is_active = False
        await self.session.flush()

        # Set all teacher's groups to teacherless (teacher_id = None)
        stmt = (
            update(Group)
            .where(Group.teacher_id == teacher_id)
            .values(teacher_id=None)
        )
        await self.session.execute(stmt)
        await self.session.flush()

        # Audit log for teacher
        await self.audit.log_update(
            center_id=center_id,
            actor_id=actor_id,
            entity="teacher",
            entity_id=teacher_id,
            old=old_values,
            new={
                "user_id": teacher.user_id,
                "specialization": teacher.specialization,
                "is_active": False,
            },
        )

        return teacher

    async def activate(
        self,
        teacher_id: int,
        center_id: int,
        actor_id: int,
    ) -> Teacher | None:
        """
        Nofaol ustozni qayta faollashtirish.

        Args:
            teacher_id: Ustoz ID
            center_id: Markaz ID
            actor_id: Kim faollashtirmoqda

        Returns:
            Faollashtirilgan Teacher yoki None
        """
        teacher = await self.session.get(Teacher, teacher_id)
        if not teacher:
            return None

        # Check center ownership via user
        from app.models.user import User
        user = await self.session.get(User, teacher.user_id)
        if not user or user.center_id != center_id:
            return None

        # Save old values for audit
        old_values = {
            "user_id": teacher.user_id,
            "specialization": teacher.specialization,
            "is_active": teacher.is_active,
        }

        # Activate teacher
        teacher.is_active = True
        await self.session.flush()

        # Audit log
        await self.audit.log_update(
            center_id=center_id,
            actor_id=actor_id,
            entity="teacher",
            entity_id=teacher_id,
            old=old_values,
            new={
                "user_id": teacher.user_id,
                "specialization": teacher.specialization,
                "is_active": True,
            },
        )

        return teacher

    async def get_by_id(self, teacher_id: int) -> Teacher | None:
        """Ustoz ma'lumotlarini olish"""
        return await self.session.get(Teacher, teacher_id)

    async def get_by_user_id(self, user_id: int) -> Teacher | None:
        """User ID bo'yicha ustoz olish"""
        stmt = select(Teacher).where(Teacher.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
