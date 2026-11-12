"""
Transfer servisi (roadmap 5.8, 5.9)

O'quvchini guruhga ko'chirish - student_group_history + students.group_id.
Ommaviy ko'chirish va guruhlarni birlashtirish.
"""
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.student import Student
from app.models.student_group_history import StudentGroupHistory
from app.services.audit import AuditService


class TransferService:
    """Transfer servisi"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def transfer_student(
        self,
        student_id: int,
        center_id: int,
        actor_id: int,
        new_group_id: int,
    ) -> Student | None:
        """
        O'quvchini boshqa guruhga ko'chirish (5.8).

        Bitta tranzaksiyada:
        1. Eski guruh tarixini yopish (to_date)
        2. Yangi guruh tarixini ochish (from_date)
        3. Student.group_id'ni yangilash

        Args:
            student_id: O'quvchi ID
            center_id: Markaz ID
            actor_id: Kim ko'chirmoqda
            new_group_id: Yangi guruh ID

        Returns:
            Yangilangan Student yoki None
        """
        student = await self.session.get(Student, student_id)
        if not student or student.center_id != center_id:
            return None

        old_group_id = student.group_id

        # Save old values for audit
        old_values = {
            "name": student.name,
            "group_id": old_group_id,
        }

        # Close old history record if exists
        if old_group_id:
            stmt = select(StudentGroupHistory).where(
                StudentGroupHistory.student_id == student_id,
                StudentGroupHistory.group_id == old_group_id,
                StudentGroupHistory.to_date.is_(None),
            )
            result = await self.session.execute(stmt)
            old_history = result.scalar_one_or_none()

            if old_history:
                old_history.to_date = datetime.now(UTC)
                await self.session.flush()

        # Create new history record
        new_history = StudentGroupHistory(
            student_id=student_id,
            group_id=new_group_id,
            from_date=datetime.now(UTC),
            to_date=None,
            changed_by=actor_id,
        )
        self.session.add(new_history)
        await self.session.flush()

        # Update student's current group
        student.group_id = new_group_id
        await self.session.flush()

        # Audit log
        await self.audit.log_update(
            center_id=center_id,
            actor_id=actor_id,
            entity="student",
            entity_id=student_id,
            old=old_values,
            new={
                "name": student.name,
                "group_id": new_group_id,
            },
        )

        return student

    async def bulk_transfer(
        self,
        student_ids: list[int],
        center_id: int,
        actor_id: int,
        new_group_id: int,
    ) -> list[Student]:
        """
        Ommaviy ko'chirish (5.9).

        Barcha o'quvchilar bitta tranzaksiyada ko'chiriladi.
        Agar xato bo'lsa, rollback bo'ladi.

        Args:
            student_ids: O'quvchi ID'lari ro'yxati
            center_id: Markaz ID
            actor_id: Kim ko'chirmoqda
            new_group_id: Yangi guruh ID

        Returns:
            Ko'chirilgan o'quvchilar ro'yxati
        """
        transferred = []

        for student_id in student_ids:
            student = await self.transfer_student(
                student_id=student_id,
                center_id=center_id,
                actor_id=actor_id,
                new_group_id=new_group_id,
            )
            if student:
                transferred.append(student)

        return transferred

    async def merge_groups(
        self,
        source_group_id: int,
        target_group_id: int,
        center_id: int,
        actor_id: int,
    ) -> list[Student]:
        """
        Guruhlarni birlashtirish (5.9).

        Manba guruhdagi barcha o'quvchilar maqsad guruhga ko'chiriladi.
        Manba guruh arxivlanadi.

        Args:
            source_group_id: Manba guruh ID
            target_group_id: Maqsad guruh ID
            center_id: Markaz ID
            actor_id: Kim birlashtirmoqda

        Returns:
            Ko'chirilgan o'quvchilar ro'yxati
        """
        from app.models.group import Group

        # Get source group
        source_group = await self.session.get(Group, source_group_id)
        if not source_group or source_group.center_id != center_id:
            return []

        # Get target group
        target_group = await self.session.get(Group, target_group_id)
        if not target_group or target_group.center_id != center_id:
            return []

        # Get all students in source group
        stmt = select(Student).where(
            Student.group_id == source_group_id,
            Student.is_active,
        )
        result = await self.session.execute(stmt)
        students = result.scalars().all()

        # Transfer all students
        student_ids = [s.id for s in students]
        transferred = await self.bulk_transfer(
            student_ids=student_ids,
            center_id=center_id,
            actor_id=actor_id,
            new_group_id=target_group_id,
        )

        # Archive source group
        from app.services.group import GroupService
        group_service = GroupService(self.session)
        await group_service.archive(
            group_id=source_group_id,
            center_id=center_id,
            actor_id=actor_id,
        )

        return transferred
