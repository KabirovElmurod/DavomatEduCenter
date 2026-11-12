"""
Student servisi (roadmap 5.6, 5.7)

O'quvchi yaratish, tahrirlash, arxivlash/tiklash (o'chirish yo'q).
Ommaviy qo'shish: matnni qatorlarga ajratish, tozalash.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.student import Student
from app.services.audit import AuditService


class StudentService:
    """Student servisi"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def create(
        self,
        center_id: int,
        actor_id: int,
        name: str,
        group_id: int | None = None,
    ) -> Student:
        """
        Yangi o'quvchi yaratish.

        Args:
            center_id: Markaz ID
            actor_id: Kim yaratmoqda
            name: O'quvchi ismi
            group_id: Guruh ID (ixtiyoriy)

        Returns:
            Student
        """
        student = Student(
            name=name,
            center_id=center_id,
            group_id=group_id,
            is_active=True,
        )
        self.session.add(student)
        await self.session.flush()

        # Audit log
        await self.audit.log_create(
            center_id=center_id,
            actor_id=actor_id,
            entity="student",
            entity_id=student.id,
            new={
                "name": name,
                "group_id": group_id,
            },
        )

        return student

    async def update(
        self,
        student_id: int,
        center_id: int,
        actor_id: int,
        name: str | None = None,
        group_id: int | None = None,
    ) -> Student | None:
        """
        O'quvchi ma'lumotlarini yangilash.

        Args:
            student_id: O'quvchi ID
            center_id: Markaz ID
            actor_id: Kim yangilamoqda
            name: Yangi ism
            group_id: Yangi guruh ID

        Returns:
            Yangilangan Student yoki None
        """
        student = await self.session.get(Student, student_id)
        if not student or student.center_id != center_id:
            return None

        # Save old values for audit
        old_values = {
            "name": student.name,
            "group_id": student.group_id,
        }

        # Update if provided
        if name is not None:
            student.name = name
        if group_id is not None:
            student.group_id = group_id

        await self.session.flush()

        # Audit log
        new_values = {
            "name": student.name,
            "group_id": student.group_id,
        }

        await self.audit.log_update(
            center_id=center_id,
            actor_id=actor_id,
            entity="student",
            entity_id=student_id,
            old=old_values,
            new=new_values,
        )

        return student

    async def archive(
        self,
        student_id: int,
        center_id: int,
        actor_id: int,
    ) -> Student | None:
        """
        O'quvchini arxivlash (soft delete).

        Args:
            student_id: O'quvchi ID
            center_id: Markaz ID
            actor_id: Kim arxivlayapti

        Returns:
            Arxivlangan Student yoki None
        """
        student = await self.session.get(Student, student_id)
        if not student or student.center_id != center_id:
            return None

        # Save old values for audit
        old_values = {
            "name": student.name,
            "group_id": student.group_id,
            "is_active": student.is_active,
        }

        # Archive
        student.is_active = False
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
                "group_id": student.group_id,
                "is_active": False,
            },
        )

        return student

    async def restore(
        self,
        student_id: int,
        center_id: int,
        actor_id: int,
    ) -> Student | None:
        """
        Arxivlangan o'quvchini tiklash.

        Args:
            student_id: O'quvchi ID
            center_id: Markaz ID
            actor_id: Kim tiklayapti

        Returns:
            Tiklangan Student yoki None
        """
        student = await self.session.get(Student, student_id)
        if not student or student.center_id != center_id:
            return None

        # Save old values for audit
        old_values = {
            "name": student.name,
            "group_id": student.group_id,
            "is_active": student.is_active,
        }

        # Restore
        student.is_active = True
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
                "group_id": student.group_id,
                "is_active": True,
            },
        )

        return student

    async def get_by_id(self, student_id: int) -> Student | None:
        """O'quvchi ma'lumotlarini olish"""
        return await self.session.get(Student, student_id)

    def parse_names_text(self, text: str) -> list[str]:
        """
        Matnni qatorlarga ajratish va tozalash (5.7).

        Args:
            text: O'quvchi ismlari matni (newline bilan ajratilgan)

        Returns:
            To'langan ismlar ro'yxati
        """
        # Split by newline
        lines = text.strip().split("\n")

        # Clean each line: strip whitespace, skip empty
        names = []
        for line in lines:
            name = line.strip()
            if name:  # Skip empty lines
                names.append(name)

        # Remove duplicates while preserving order
        seen = set()
        unique_names = []
        for name in names:
            if name not in seen:
                seen.add(name)
                unique_names.append(name)

        return unique_names

    async def bulk_create(
        self,
        center_id: int,
        actor_id: int,
        names_text: str,
        group_id: int | None = None,
    ) -> list[Student]:
        """
        Ommaviy qo'shish (5.7).

        Args:
            center_id: Markaz ID
            actor_id: Kim qo'shmoqda
            names_text: O'quvchi ismlari matni
            group_id: Guruh ID (ixtiyoriy)

        Returns:
            Yaratilgan o'quvchilar ro'yxati
        """
        names = self.parse_names_text(names_text)
        students = []

        for name in names:
            student = await self.create(
                center_id=center_id,
                actor_id=actor_id,
                name=name,
                group_id=group_id,
            )
            students.append(student)

        return students
