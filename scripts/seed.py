import asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import AsyncSessionLocal
from app.modules import Center, User, Group, Student, Lesson, Attendance


async def seed_db():
    async with AsyncSessionLocal() as session:
        # 1 markaz
        center = Center(
            name="Test Education Center",
            telegram_bot_token="test_bot_token_123"
        )
        session.add(center)
        await session.flush()
        await session.refresh(center)

        # 2 ustoz
        teacher1 = User(
            center_id=center.id,
            telegram_id=1001,
            telegram_username="teacher1",
            full_name="Teacher One",
            role="teacher"
        )
        teacher2 = User(
            center_id=center.id,
            telegram_id=1002,
            telegram_username="teacher2",
            full_name="Teacher Two",
            role="teacher"
        )
        session.add(teacher1)
        session.add(teacher2)
        await session.flush()
        await session.refresh(teacher1)
        await session.refresh(teacher2)

        # 3 guruh
        group1 = Group(
            center_id=center.id,
            teacher_id=teacher1.id,
            name="Math Group A"
        )
        group2 = Group(
            center_id=center.id,
            teacher_id=teacher1.id,
            name="Math Group B"
        )
        group3 = Group(
            center_id=center.id,
            teacher_id=teacher2.id,
            name="Physics Group A"
        )
        session.add(group1)
        session.add(group2)
        session.add(group3)
        await session.flush()
        await session.refresh(group1)
        await session.refresh(group2)
        await session.refresh(group3)

        # 30 o'quvchi (har guruhda 10 tadan)
        students = []
        for i, group in enumerate([group1, group2, group3]):
            for j in range(10):
                student = Student(
                    center_id=center.id,
                    group_id=group.id,
                    full_name=f"Student {i*10 + j + 1}",
                    phone=f"+9989012345{i*10 + j:02d}"
                )
                students.append(student)
                session.add(student)

        await session.flush()

        # Bugungi dars (har guruh uchun)
        today = datetime.now().date()
        lessons = []
        for group in [group1, group2, group3]:
            lesson = Lesson(
                group_id=group.id,
                lesson_date=today,
                topic=f"Daily lesson for {group.name}"
            )
            lessons.append(lesson)
            session.add(lesson)

        await session.flush()

        # Attendance (barcha o'quvchilar uchun)
        for lesson in lessons:
            for student in students:
                if student.group_id == lesson.group_id:
                    attendance = Attendance(
                        lesson_id=lesson.id,
                        student_id=student.id,
                        status="present"
                    )
                    session.add(attendance)

        await session.commit()
        print(f"✅ Seed completed:")
        print(f"   - 1 center: {center.name}")
        print(f"   - 2 teachers")
        print(f"   - 3 groups")
        print(f"   - 30 students")
        print(f"   - 3 lessons (today)")
        print(f"   - 30 attendance records")


if __name__ == "__main__":
    asyncio.run(seed_db())
