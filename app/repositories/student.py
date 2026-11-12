"""
Student repository (roadmap 4.7)

Student CRUD operatsiyalari - tenant izolyatsiya bilan.
"""

from sqlalchemy import select

from app.models.student import Student
from app.repositories.base import BaseRepository


class StudentRepository(BaseRepository):
    """Student repository"""

    async def get_by_id(self, student_id: int) -> Student | None:
        """
        Student ma'lumotlarini olish (faqat o'z markazidan).
        Guruh orqali tekshirish - student.group_id -> group.center_id.
        """
        stmt = select(Student).where(Student.id == student_id)
        result = await self.session.execute(stmt)
        student = result.scalar_one_or_none()

        if not student:
            return None

        # Check if student belongs to current center via group
        from app.models.group import Group
        group_stmt = select(Group).where(
            Group.id == student.group_id,
            Group.center_id == self.center_id,
        )
        group_result = await self.session.execute(group_stmt)
        group = group_result.scalar_one_or_none()

        if not group:
            return None

        return student

    async def list_by_group(self, group_id: int) -> list[Student]:
        """
        Guruh bo'yicha o'quvchilar ro'yxati (faqat o'z markazidan).
        """
        # Avval guruh markazga tegishli ekanligini tekshirish
        from app.models.group import Group
        group_stmt = select(Group).where(
            Group.id == group_id,
            Group.center_id == self.center_id,
        )
        group_result = await self.session.execute(group_stmt)
        group = group_result.scalar_one_or_none()

        if not group:
            return []

        stmt = select(Student).where(
            Student.group_id == group_id,
            Student.is_active,
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_all(self) -> list[Student]:
        """
        Barcha o'quvchilar ro'yxati (faqat o'z markazidan).
        """
        # Join with groups to filter by center
        from app.models.group import Group
        stmt = (
            select(Student)
            .join(Group, Student.group_id == Group.id)
            .where(
                Group.center_id == self.center_id,
                Student.is_active,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
