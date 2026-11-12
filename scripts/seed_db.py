#!/usr/bin/env python3
"""Seed database with initial data"""
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models import (
    Center, User, Teacher, Group, Student,
    UserRole
)


async def seed():
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Markaz
        center = Center(name="Test Markaz", address="Toshkent", phone="+998901234567")
        session.add(center)
        await session.flush()

        # Owner
        owner = User(
            telegram_id=1001,
            first_name="Admin",
            last_name="User",
            username="admin",
            role=UserRole.OWNER,
            center_id=center.id,
            is_active=True
        )
        session.add(owner)
        await session.flush()

        # Ustozlar
        teacher1 = User(
            telegram_id=2001,
            first_name="Ustoz",
            last_name="Bir",
            username="teacher1",
            role=UserRole.TEACHER,
            center_id=center.id,
            is_active=True
        )
        session.add(teacher1)
        await session.flush()

        teacher1_record = Teacher(user_id=teacher1.id, specialization="Matematika")
        session.add(teacher1_record)

        teacher2 = User(
            telegram_id=2002,
            first_name="Ustoz",
            last_name="Ikki",
            username="teacher2",
            role=UserRole.TEACHER,
            center_id=center.id,
            is_active=True
        )
        session.add(teacher2)
        await session.flush()

        teacher2_record = Teacher(user_id=teacher2.id, specialization="Ingliz tili")
        session.add(teacher2_record)

        # Guruhlar
        group1 = Group(name="Matematika A", center_id=center.id, teacher_id=teacher1_record.id)
        session.add(group1)
        await session.flush()

        group2 = Group(name="Ingliz B", center_id=center.id, teacher_id=teacher2_record.id)
        session.add(group2)
        await session.flush()

        group3 = Group(name="Matematika B", center_id=center.id, teacher_id=teacher1_record.id)
        session.add(group3)
        await session.flush()

        # O'quvchilar (30 ta)
        for i in range(1, 31):
            student = Student(
                name=f"O'quvchi {i}",
                center_id=center.id,
                group_id=group1.id if i <= 10 else (group2.id if i <= 20 else group3.id),
                is_active=True
            )
            session.add(student)

        await session.commit()
        print("✅ Seed completed: 1 markaz, 1 owner, 2 ustoz, 3 guruh, 30 o'quvchi")


if __name__ == "__main__":
    asyncio.run(seed())
