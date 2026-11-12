"""
Guruh API endpoint'lari (roadmap 8.3-8.7)

GET  /api/v1/groups/{id}/lesson/today   — bugungi dars + o'quvchilar
GET  /api/v1/groups/{id}/attendance     — davomatni ko'rish (?date=YYYY-MM-DD)
POST /api/v1/groups/{id}/attendance     — davomat yuborish (Idempotency-Key)
"""
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_accessible_group, get_teacher_context
from app.core.db import get_db
from app.core.timezone import today_tashkent
from app.models.attendance import Attendance
from app.models.base import AttendanceStatus
from app.models.student import Student
from app.services.attendance import (
    AttendanceError,
    enqueue_lesson_notifications,
    get_lesson_for_day,
    get_or_create_lesson,
    list_group_students,
    submit_attendance,
)

router = APIRouter()


class AttendanceItem(BaseModel):
    student_id: int
    status: AttendanceStatus


class AttendanceSubmitRequest(BaseModel):
    items: list[AttendanceItem] = Field(min_length=1)


def _student_out(s: Student, status: str | None = None) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "status": status,
    }


@router.get("/groups/{group_id}/lesson/today")
async def lesson_today(
    group_id: int,
    ctx: dict = Depends(get_teacher_context),
    db: AsyncSession = Depends(get_db),
    group=Depends(get_accessible_group),
):
    """
    Bugungi dars + o'quvchilar bitta so'rovda.

    Dars mavjud bo'lmasa get-or-create qilinadi (idempotent).
    Har bir o'quvchi uchun avval belgilangan status qaytariladi.
    """
    day = today_tashkent()
    lesson = await get_or_create_lesson(db, group.id, day)
    await db.commit()

    students = await list_group_students(db, group.id)

    att_stmt = select(Attendance).where(Attendance.lesson_id == lesson.id)
    att_rows = (await db.execute(att_stmt)).scalars().all()
    status_by_student = {a.student_id: a.status.value for a in att_rows}

    return {
        "lesson": {
            "id": lesson.id,
            "group_id": group.id,
            "group_name": group.name,
            "date": day.isoformat(),
        },
        "students": [
            _student_out(s, status_by_student.get(s.id)) for s in students
        ],
    }


@router.get("/groups/{group_id}/attendance")
async def get_attendance(
    group_id: int,
    day: date | None = None,
    ctx: dict = Depends(get_teacher_context),
    db: AsyncSession = Depends(get_db),
    group=Depends(get_accessible_group),
):
    """Davomatni ko'rish (?date=YYYY-MM-DD, default: bugun)"""
    target_day = day or today_tashkent()
    lesson = await get_lesson_for_day(db, group.id, target_day)
    if lesson is None:
        return {"date": target_day.isoformat(), "lesson": None, "records": []}

    stmt = (
        select(Attendance, Student.name)
        .join(Student, Attendance.student_id == Student.id)
        .where(Attendance.lesson_id == lesson.id)
        .order_by(Student.name)
    )
    rows = (await db.execute(stmt)).all()

    return {
        "date": target_day.isoformat(),
        "lesson": {"id": lesson.id, "group_id": group.id, "group_name": group.name},
        "records": [
            {
                "student_id": att.student_id,
                "student_name": name,
                "status": att.status.value,
            }
            for att, name in rows
        ],
    }


@router.post("/groups/{group_id}/attendance")
async def post_attendance(
    group_id: int,
    payload: AttendanceSubmitRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    ctx: dict = Depends(get_teacher_context),
    db: AsyncSession = Depends(get_db),
    group=Depends(get_accessible_group),
):
    """
    Davomat yuborish.

    Idempotency-Key: bir xil key bilan qayta so'rov bazaga
    yangi yozuv qo'shmaydi, mavjud submission qaytariladi.
    """
    if not idempotency_key or len(idempotency_key) > 255:
        raise HTTPException(status_code=400, detail="Idempotency-Key noto'g'ri")

    items = [{"student_id": i.student_id, "status": i.status.value} for i in payload.items]

    try:
        result = await submit_attendance(
            db,
            group,
            today_tashkent(),
            items,
            submitted_by=ctx["user_id"],
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except AttendanceError as e:
        await db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except IntegrityError:
        # Parallel so'rov: boshqa transaction allaqachon yozgan
        await db.rollback()
        from app.services.attendance import find_submission

        sub = await find_submission(db, idempotency_key)
        if sub is None:
            raise
        return {
            "status": "submitted",
            "duplicate": True,
            "lesson_id": sub.lesson_id,
            "students": 0,
            "notifications_queued": 0,
        }
    except Exception:
        await db.rollback()
        raise

    # Tranzaksiyadan keyin ARQ'ga enqueue (request ichida Telegram yo'q)
    if not result["duplicate"]:
        await enqueue_lesson_notifications(result["lesson_id"])

    return {
        "status": "submitted",
        "duplicate": result["duplicate"],
        "lesson_id": result["lesson_id"],
        "students": result["students"],
        "notifications_queued": result["notifications"],
    }
