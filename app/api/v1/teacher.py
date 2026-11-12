"""GET /api/v1/teacher/groups — ustozning guruhlari + bugungi darslar"""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_teacher_context
from app.core.db import get_db
from app.core.timezone import tashkent_day_bounds_utc, today_tashkent
from app.models.attendance import Attendance
from app.models.group import Group
from app.models.lesson import Lesson
from app.models.student import Student

router = APIRouter()


@router.get("/teacher/groups")
async def teacher_groups(
    ctx: dict = Depends(get_teacher_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Ustozning guruhlari ro'yxati.

    teacher: faqat o'z guruhlari; owner/admin: markazdagi barcha guruhlar.
    Har bir guruh uchun bugungi dars (mavjud bo'lsa) va belgilangan
    davomat statistikasi qaytariladi.
    """
    today = today_tashkent()
    day_start, day_end = tashkent_day_bounds_utc(today)

    if ctx["role"] == "teacher":
        stmt = select(Group).where(
            Group.teacher_id == ctx["teacher"].id,
            Group.is_active.is_(True),
        )
    else:
        stmt = select(Group).where(
            Group.center_id == ctx["center_id"],
            Group.is_active.is_(True),
        )
    groups = (await db.execute(stmt.order_by(Group.name))).scalars().all()

    result = []
    for g in groups:
        lesson = (
            await db.execute(
                select(Lesson).where(
                    Lesson.group_id == g.id,
                    Lesson.lesson_date >= day_start,
                    Lesson.lesson_date < day_end,
                )
            )
        ).scalar_one_or_none()

        students_count = (
            await db.execute(
                select(func.count(Student.id)).where(
                    Student.group_id == g.id, Student.is_active.is_(True)
                )
            )
        ).scalar_one()

        marked = 0
        if lesson is not None:
            marked = (
                await db.execute(
                    select(func.count(Attendance.id)).where(
                        Attendance.lesson_id == lesson.id
                    )
                )
            ).scalar_one()

        result.append(
            {
                "id": g.id,
                "name": g.name,
                "students_count": students_count,
                "lesson": (
                    {
                        "id": lesson.id,
                        "date": today.isoformat(),
                        "submitted": students_count > 0 and marked >= students_count,
                        "marked_count": marked,
                    }
                    if lesson
                    else None
                ),
            }
        )

    return {"date": today.isoformat(), "groups": result}
