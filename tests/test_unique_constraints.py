import pytest
from sqlalchemy.exc import IntegrityError

from app.core.db import AsyncSessionLocal
from app.modules import (
    Attendance,
    AttendanceSubmission,
    Center,
    Group,
    Lesson,
    Notification,
    ParentStudent,
    Student,
    User,
)


@pytest.mark.asyncio
async def test_unique_lesson_student_attendance():
    """Test: bir lesson va student uchun bitta attendance bo'lishi kerak"""
    async with AsyncSessionLocal() as session:
        # Setup
        center = Center(name="Test", telegram_bot_token="token")
        session.add(center)
        await session.flush()
        await session.refresh(center)

        teacher = User(center_id=center.id, telegram_id=1, full_name="T", role="teacher")
        session.add(teacher)
        await session.flush()
        await session.refresh(teacher)

        group = Group(center_id=center.id, teacher_id=teacher.id, name="G1")
        session.add(group)
        await session.flush()
        await session.refresh(group)

        student = Student(center_id=center.id, group_id=group.id, full_name="S1")
        session.add(student)
        await session.flush()
        await session.refresh(student)

        lesson = Lesson(group_id=group.id, lesson_date="2026-10-30")
        session.add(lesson)
        await session.flush()
        await session.refresh(lesson)

        # First attendance
        attendance1 = Attendance(lesson_id=lesson.id, student_id=student.id, status="present")
        session.add(attendance1)
        await session.commit()

        # Second attendance with same lesson_id and student_id should fail
        attendance2 = Attendance(lesson_id=lesson.id, student_id=student.id, status="absent")
        session.add(attendance2)

        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_unique_idempotency_key():
    """Test: bir idempotency_key uchun bitta submission bo'lishi kerak"""
    async with AsyncSessionLocal() as session:
        # Setup
        center = Center(name="Test", telegram_bot_token="token")
        session.add(center)
        await session.flush()
        await session.refresh(center)

        teacher = User(center_id=center.id, telegram_id=1, full_name="T", role="teacher")
        session.add(teacher)
        await session.flush()
        await session.refresh(teacher)

        group = Group(center_id=center.id, teacher_id=teacher.id, name="G1")
        session.add(group)
        await session.flush()
        await session.refresh(group)

        lesson = Lesson(group_id=group.id, lesson_date="2026-10-30")
        session.add(lesson)
        await session.flush()
        await session.refresh(lesson)

        # First submission
        submission1 = AttendanceSubmission(
            idempotency_key="test-key-123",
            teacher_id=teacher.id,
            lesson_id=lesson.id
        )
        session.add(submission1)
        await session.commit()

        # Second submission with same idempotency_key should fail
        submission2 = AttendanceSubmission(
            idempotency_key="test-key-123",
            teacher_id=teacher.id,
            lesson_id=lesson.id
        )
        session.add(submission2)

        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_unique_attendance_parent_notification():
    """Test: bir attendance va parent uchun bitta notification bo'lishi kerak"""
    async with AsyncSessionLocal() as session:
        # Setup
        center = Center(name="Test", telegram_bot_token="token")
        session.add(center)
        await session.flush()
        await session.refresh(center)

        teacher = User(center_id=center.id, telegram_id=1, full_name="T", role="teacher")
        session.add(teacher)
        await session.flush()
        await session.refresh(teacher)

        parent = User(center_id=center.id, telegram_id=2, full_name="P", role="parent")
        session.add(parent)
        await session.flush()
        await session.refresh(parent)

        group = Group(center_id=center.id, teacher_id=teacher.id, name="G1")
        session.add(group)
        await session.flush()
        await session.refresh(group)

        student = Student(center_id=center.id, group_id=group.id, full_name="S1")
        session.add(student)
        await session.flush()
        await session.refresh(student)

        lesson = Lesson(group_id=group.id, lesson_date="2026-10-30")
        session.add(lesson)
        await session.flush()
        await session.refresh(lesson)

        attendance = Attendance(lesson_id=lesson.id, student_id=student.id, status="present")
        session.add(attendance)
        await session.flush()
        await session.refresh(attendance)

        # First notification
        notification1 = Notification(
            attendance_id=attendance.id,
            parent_user_id=parent.id,
            status="pending"
        )
        session.add(notification1)
        await session.commit()

        # Second notification with same attendance_id and parent_user_id should fail
        notification2 = Notification(
            attendance_id=attendance.id,
            parent_user_id=parent.id,
            status="pending"
        )
        session.add(notification2)

        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_unique_parent_student():
    """Test: bir parent va student uchun bitta parent_student bo'lishi kerak"""
    async with AsyncSessionLocal() as session:
        # Setup
        center = Center(name="Test", telegram_bot_token="token")
        session.add(center)
        await session.flush()
        await session.refresh(center)

        parent = User(center_id=center.id, telegram_id=1, full_name="P", role="parent")
        session.add(parent)
        await session.flush()
        await session.refresh(parent)

        group = Group(center_id=center.id, teacher_id=1, name="G1")
        session.add(group)
        await session.flush()
        await session.refresh(group)

        student = Student(center_id=center.id, group_id=group.id, full_name="S1")
        session.add(student)
        await session.flush()
        await session.refresh(student)

        # First parent_student
        ps1 = ParentStudent(parent_user_id=parent.id, student_id=student.id)
        session.add(ps1)
        await session.commit()

        # Second parent_student with same parent_user_id and student_id should fail
        ps2 = ParentStudent(parent_user_id=parent.id, student_id=student.id)
        session.add(ps2)

        with pytest.raises(IntegrityError):
            await session.commit()
