"""
Admin UI sahifa routeri (roadmap 7-bosqich)

GET sahifalar: groups, group detail, students, student detail, teachers, parents.
Barcha so'rovlar center_id bo'yicha tenant izolyatsiyalangan.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.admin.common import get_admin_context, render, telegram_link
from app.core.db import get_db
from app.core.deps import get_current_admin
from app.core.timezone import TASHKENT_TZ
from app.models.attendance import Attendance
from app.models.base import AttendanceStatus, UserRole
from app.models.center import Center
from app.models.group import Group
from app.models.lesson import Lesson
from app.models.notification import Notification
from app.models.parent_link import ParentLink
from app.models.student import Student
from app.models.student_group_history import StudentGroupHistory
from app.models.teacher import Teacher
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["admin-ui"])


def _not_found():
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topilmadi")


async def _admin_ctx(db: AsyncSession, admin: dict) -> dict:
    return await get_admin_context(db, admin)


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------
@router.get("")
@router.get("/")
async def admin_home():
    from fastapi.responses import RedirectResponse

    return RedirectResponse("/admin/groups", status_code=303)


# --------------------------------------------------------------------------
# Guruhlar
# --------------------------------------------------------------------------
@router.get("/groups")
async def groups_page(
    request: Request,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Guruhlar ro'yxati + yaratish + birlashtirish"""
    center_id = admin["center_id"]

    teacher_user = aliased(User)
    student_count = (
        select(func.count(Student.id))
        .where(Student.group_id == Group.id, Student.is_active == True)  # noqa: E712
        .scalar_subquery()
    )
    stmt = (
        select(
            Group.id,
            Group.name,
            Group.teacher_id,
            teacher_user.first_name,
            teacher_user.last_name,
            student_count.label("student_count"),
        )
        .outerjoin(Teacher, Group.teacher_id == Teacher.id)
        .outerjoin(teacher_user, Teacher.user_id == teacher_user.id)
        .where(Group.center_id == center_id, Group.is_active == True)  # noqa: E712
        .order_by(Group.name)
    )
    rows = (await db.execute(stmt)).all()

    groups = [
        {
            "id": r.id,
            "name": r.name,
            "teacher_id": r.teacher_id,
            "teacher_name": " ".join(x for x in [r.first_name, r.last_name] if x) or None,
            "student_count": r.student_count,
        }
        for r in rows
    ]

    # Faol ustozlar (guruh yaratish/biriktirish uchun)
    t_stmt = (
        select(Teacher.id, User.first_name, User.last_name)
        .join(User, Teacher.user_id == User.id)
        .where(User.center_id == center_id, Teacher.is_active == True)  # noqa: E712
        .order_by(User.first_name)
    )
    teachers = [
        {
            "id": r.id,
            "name": " ".join(x for x in [r.first_name, r.last_name] if x),
        }
        for r in (await db.execute(t_stmt)).all()
    ]

    ctx = await _admin_ctx(db, admin)
    return render(request, "groups.html", {**ctx, "groups": groups, "teachers": teachers})


@router.get("/groups/{group_id}")
async def group_detail_page(
    request: Request,
    group_id: int,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Guruh sahifasi: o'quvchilar, ustoz, oxirgi 10 dars"""
    center_id = admin["center_id"]

    group = await db.get(Group, group_id)
    if not group or group.center_id != center_id:
        raise _not_found()

    # Ustoz nomi
    teacher_name = None
    if group.teacher_id:
        teacher = await db.get(Teacher, group.teacher_id)
        if teacher:
            u = await db.get(User, teacher.user_id)
            if u:
                teacher_name = " ".join(x for x in [u.first_name, u.last_name] if x)
    group.teacher_name = teacher_name

    # Aktiv ustozlar (almashtirish uchun)
    t_stmt = (
        select(Teacher.id, User.first_name, User.last_name)
        .join(User, Teacher.user_id == User.id)
        .where(User.center_id == center_id, Teacher.is_active == True)  # noqa: E712
        .order_by(User.first_name)
    )
    teachers = [
        {"id": r.id, "name": " ".join(x for x in [r.first_name, r.last_name] if x)}
        for r in (await db.execute(t_stmt)).all()
    ]

    # Guruhdagi faol o'quvchilar + ota-ona holati
    students = await _students_in_group(db, group_id, center_id)

    # Oxirgi 10 dars + davomat
    lessons = await _last_lessons(db, group_id)

    ctx = await _admin_ctx(db, admin)
    return render(
        request,
        "group_detail.html",
        {
            **ctx,
            "group": group,
            "teachers": teachers,
            "students": students,
            "lessons": lessons,
        },
    )


async def _students_in_group(db: AsyncSession, group_id: int, center_id: int) -> list[dict]:
    """Guruhdagi o'quvchilar (parent_linked bilan)"""
    linked = (
        select(ParentLink.id)
        .where(ParentLink.student_id == Student.id, ParentLink.revoked_at.is_(None))
        .exists()
    )
    stmt = (
        select(Student.id, Student.name, linked.label("parent_linked"))
        .where(
            Student.group_id == group_id,
            Student.center_id == center_id,
            Student.is_active == True,  # noqa: E712
        )
        .order_by(Student.name)
    )
    return [
        {"id": r.id, "name": r.name, "parent_linked": r.parent_linked}
        for r in (await db.execute(stmt)).all()
    ]


async def _last_lessons(db: AsyncSession, group_id: int, limit: int = 10) -> list[dict]:
    """Oxirgi N dars + davomat statistikasi"""
    l_stmt = (
        select(Lesson)
        .where(Lesson.group_id == group_id)
        .order_by(Lesson.lesson_date.desc())
        .limit(limit)
    )
    lessons = (await db.execute(l_stmt)).scalars().all()

    out = []
    for lesson in lessons:
        counts = {s: 0 for s in AttendanceStatus}
        a_stmt = (
            select(Attendance.status, func.count())
            .where(Attendance.lesson_id == lesson.id)
            .group_by(Attendance.status)
        )
        for status_val, cnt in (await db.execute(a_stmt)).all():
            counts[status_val] = cnt
        total = sum(counts.values())
        attended = counts[AttendanceStatus.PRESENT] + counts[AttendanceStatus.LATE]
        percent = round(attended * 100 / total) if total else 0
        out.append(
            {
                "lesson_date": lesson.lesson_date,
                "present": counts[AttendanceStatus.PRESENT],
                "absent": counts[AttendanceStatus.ABSENT],
                "late": counts[AttendanceStatus.LATE],
                "percent": percent,
            }
        )
    return out


# --------------------------------------------------------------------------
# O'quvchilar
# --------------------------------------------------------------------------
def _students_select(
    center_id: int,
    q: str = "",
    group_id: int | None = None,
    parent_status: str = "",
    status: str = "active",
) -> Select:
    """O'quvchilar (filtrlar bilan)"""
    group = aliased(Group)
    linked = (
        select(ParentLink.id)
        .where(ParentLink.student_id == Student.id, ParentLink.revoked_at.is_(None))
        .exists()
    )
    stmt = (
        select(
            Student.id,
            Student.name,
            Student.is_active,
            Student.group_id,
            group.name.label("group_name"),
            linked.label("parent_linked"),
        )
        .outerjoin(group, Student.group_id == group.id)
        .where(Student.center_id == center_id)
    )
    if q:
        stmt = stmt.where(Student.name.ilike(f"%{q}%"))
    if group_id:
        stmt = stmt.where(Student.group_id == group_id)
    if parent_status == "linked":
        stmt = stmt.where(linked)
    elif parent_status == "unlinked":
        stmt = stmt.where(~linked)
    if status == "active":
        stmt = stmt.where(Student.is_active == True)  # noqa: E712
    elif status == "archived":
        stmt = stmt.where(Student.is_active == False)  # noqa: E712
    return stmt.order_by(Student.name)


async def _groups_options(db: AsyncSession, center_id: int) -> list[dict]:
    stmt = (
        select(Group.id, Group.name)
        .where(Group.center_id == center_id, Group.is_active == True)  # noqa: E712
        .order_by(Group.name)
    )
    return [{"id": r.id, "name": r.name} for r in (await db.execute(stmt)).all()]


async def _render_students_table(
    request: Request,
    db: AsyncSession,
    admin: dict,
    q: str,
    group_id: int | None,
    parent_status: str,
    status: str,
):
    center_id = admin["center_id"]
    rows = (await db.execute(_students_select(center_id, q, group_id, parent_status, status))).all()
    students = [
        {
            "id": r.id,
            "name": r.name,
            "is_active": r.is_active,
            "group_name": r.group_name,
            "parent_linked": r.parent_linked,
        }
        for r in rows
    ]
    ctx = await _admin_ctx(db, admin)
    return render(
        request,
        "_students_table.html",
        {
            **ctx,
            "students": students,
        },
    )


@router.get("/students")
async def students_page(
    request: Request,
    q: str = "",
    group_id: int | None = None,
    parent_status: str = "",
    status: str = "active",
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """O'quvchilar jadvali (jonli qidiruv + filtrlar)"""
    groups = await _groups_options(db, admin["center_id"])
    ctx = await _admin_ctx(db, admin)
    filters = {"q": q, "group_id": group_id, "parent_status": parent_status, "status": status}

    center_id = admin["center_id"]
    rows = (await db.execute(_students_select(center_id, q, group_id, parent_status, status))).all()
    students = [
        {
            "id": r.id,
            "name": r.name,
            "is_active": r.is_active,
            "group_name": r.group_name,
            "parent_linked": r.parent_linked,
        }
        for r in rows
    ]

    return render(
        request,
        "students.html",
        {
            **ctx,
            "groups": groups,
            "students": students,
            "f": filters,
        },
    )


@router.get("/partials/students-table")
async def students_table_partial(
    request: Request,
    q: str = "",
    group_id: int | None = None,
    parent_status: str = "",
    status: str = "active",
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """HTMX: filtrlangan o'quvchilar jadvali"""
    return await _render_students_table(request, db, admin, q, group_id, parent_status, status)


@router.get("/students/{student_id}")
async def student_detail_page(
    request: Request,
    student_id: int,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """O'quvchi sahifasi: tahrirlash, guruh, ota-ona, tarix"""
    center_id = admin["center_id"]

    student = await db.get(Student, student_id)
    if not student or student.center_id != center_id:
        raise _not_found()

    groups = await _groups_options(db, center_id)

    # Parent link (oxirgi)
    pl_stmt = (
        select(ParentLink)
        .where(ParentLink.student_id == student_id)
        .order_by(ParentLink.created_at.desc())
        .limit(1)
    )
    parent_link = (await db.execute(pl_stmt)).scalar_one_or_none()
    if parent_link:
        parent_link.url = await telegram_link(parent_link.invite_token)
        if parent_link.user_id:
            pu = await db.get(User, parent_link.user_id)
            parent_link.parent_name = (
                " ".join(x for x in [pu.first_name, pu.last_name] if x) if pu else None
            )
        else:
            parent_link.parent_name = None

    # Guruh tarixi
    h_stmt = (
        select(StudentGroupHistory, Group.name)
        .join(Group, StudentGroupHistory.group_id == Group.id)
        .where(StudentGroupHistory.student_id == student_id)
        .order_by(StudentGroupHistory.from_date.desc())
    )
    history = [
        {"group_name": name, "from_date": h.from_date, "to_date": h.to_date}
        for h, name in (await db.execute(h_stmt)).all()
    ]

    ctx = await _admin_ctx(db, admin)
    return render(
        request,
        "student_detail.html",
        {
            **ctx,
            "student": student,
            "groups": groups,
            "parent_link": parent_link,
            "history": history,
        },
    )


# --------------------------------------------------------------------------
# Ustozlar
# --------------------------------------------------------------------------
@router.get("/teachers")
async def teachers_page(
    request: Request,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Ustozlar ro'yxati + taklif havolasi"""
    center_id = admin["center_id"]

    group_count = (
        select(func.count(Group.id)).where(Group.teacher_id == Teacher.id).scalar_subquery()
    )
    stmt = (
        select(
            Teacher.id,
            Teacher.is_active,
            Teacher.specialization,
            User.first_name,
            User.last_name,
            User.username,
            group_count.label("group_count"),
        )
        .join(User, Teacher.user_id == User.id)
        .where(User.center_id == center_id)
        .order_by(User.first_name)
    )
    teachers = [
        {
            "id": r.id,
            "name": " ".join(x for x in [r.first_name, r.last_name] if x),
            "username": r.username,
            "specialization": r.specialization,
            "is_active": r.is_active,
            "group_count": r.group_count,
        }
        for r in (await db.execute(stmt)).all()
    ]

    ctx = await _admin_ctx(db, admin)
    return render(request, "teachers.html", {**ctx, "teachers": teachers})


# --------------------------------------------------------------------------
# Platforma admin: markazlar (faqat super_admin)
# --------------------------------------------------------------------------
def _require_super_admin(admin: dict) -> None:
    if admin.get("role") != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Faqat super_admin")


@router.get("/centers")
async def centers_page(
    request: Request,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Barcha markazlar ro'yxati + yaratish (super_admin)"""
    _require_super_admin(admin)

    owner_user = aliased(User)
    group_count = (
        select(func.count(Group.id))
        .where(Group.center_id == Center.id, Group.is_active == True)  # noqa: E712
        .scalar_subquery()
    )
    student_count = (
        select(func.count(Student.id))
        .where(Student.center_id == Center.id, Student.is_active == True)  # noqa: E712
        .scalar_subquery()
    )
    stmt = (
        select(
            Center.id,
            Center.name,
            Center.subdomain,
            Center.is_active,
            owner_user.telegram_id,
            owner_user.first_name,
            owner_user.last_name,
            owner_user.username,
            group_count.label("group_count"),
            student_count.label("student_count"),
        )
        .outerjoin(
            owner_user,
            (owner_user.center_id == Center.id) & (owner_user.role == UserRole.OWNER),
        )
        .order_by(Center.id)
    )
    centers = [
        {
            "id": r.id,
            "name": r.name,
            "subdomain": r.subdomain,
            "is_active": r.is_active,
            "owner_name": " ".join(x for x in [r.first_name, r.last_name] if x) or None,
            "owner_telegram_id": r.telegram_id,
            "owner_username": r.username,
            "group_count": r.group_count,
            "student_count": r.student_count,
        }
        for r in (await db.execute(stmt)).all()
    ]

    ctx = await _admin_ctx(db, admin)
    return render(request, "centers.html", {**ctx, "centers": centers})


# --------------------------------------------------------------------------
# Ota-onalar
# --------------------------------------------------------------------------
@router.get("/parents")
async def parents_page(
    request: Request,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Ota-onalar: ulangan + ulanmagan o'quvchilar"""
    center_id = admin["center_id"]

    # Aktiv parent link'lar (user_id NULL emas)
    parent_user = aliased(User)
    linked_stmt = (
        select(
            ParentLink.id,
            ParentLink.student_id,
            ParentLink.revoked_at,
            Student.name.label("student_name"),
            parent_user.first_name,
            parent_user.last_name,
            parent_user.username,
        )
        .join(Student, ParentLink.student_id == Student.id)
        .join(parent_user, ParentLink.user_id == parent_user.id)
        .where(Student.center_id == center_id, ParentLink.user_id.isnot(None))
        .order_by(Student.name)
    )
    linked = [
        {
            "id": r.id,
            "student_id": r.student_id,
            "student_name": r.student_name,
            "parent_name": " ".join(x for x in [r.first_name, r.last_name] if x) or None,
            "parent_username": r.username,
            "revoked_at": r.revoked_at,
        }
        for r in (await db.execute(linked_stmt)).all()
    ]

    # Ulanmagan faol o'quvchilar (aktiv link yo'q)
    has_active_link = (
        select(ParentLink.id)
        .where(ParentLink.student_id == Student.id, ParentLink.revoked_at.is_(None))
        .exists()
    )
    group = aliased(Group)
    unlinked_stmt = (
        select(Student.id, Student.name, group.name.label("group_name"))
        .outerjoin(group, Student.group_id == group.id)
        .where(
            Student.center_id == center_id,
            Student.is_active == True,  # noqa: E712
            ~has_active_link,
        )
        .order_by(Student.name)
    )
    unlinked_rows = (await db.execute(unlinked_stmt)).all()

    # Har biri uchun oxirgi link (agar revoked bo'lsa url yo'q)
    unlinked = []
    for r in unlinked_rows:
        pl_stmt = (
            select(ParentLink)
            .where(ParentLink.student_id == r.id)
            .order_by(ParentLink.created_at.desc())
            .limit(1)
        )
        pl = (await db.execute(pl_stmt)).scalar_one_or_none()
        unlinked.append(
            {
                "id": r.id,
                "name": r.name,
                "group_name": r.group_name,
                "parent_url": await telegram_link(pl.invite_token)
                if pl and pl.revoked_at is None
                else None,
            }
        )

    ctx = await _admin_ctx(db, admin)
    return render(
        request,
        "parents.html",
        {
            **ctx,
            "linked": linked,
            "unlinked": unlinked,
        },
    )


# --------------------------------------------------------------------------
# Davomat (roadmap 10-bosqich)
# --------------------------------------------------------------------------
def _lesson_day(lesson_date) -> str:
    """lesson_date'ni Tashkent sanasiga o'tkazib formatlash"""
    dt = lesson_date
    if dt.tzinfo is not None:
        dt = dt.astimezone(TASHKENT_TZ)
    return dt.strftime("%d.%m.%Y")


@router.get("/attendance")
async def attendance_page(
    request: Request,
    group_id: int | None = None,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """O'tgan darslar ro'yxati + guruh bo'yicha davomat foizi"""
    center_id = admin["center_id"]
    groups = await _groups_options(db, center_id)

    # Darslar (sana bo'yicha, oxirgi 200)
    l_stmt = (
        select(
            Lesson.id,
            Lesson.lesson_date,
            Group.id.label("group_id"),
            Group.name.label("group_name"),
        )
        .join(Group, Lesson.group_id == Group.id)
        .where(Group.center_id == center_id)
        .order_by(Lesson.lesson_date.desc())
        .limit(200)
    )
    if group_id:
        l_stmt = l_stmt.where(Lesson.group_id == group_id)
    lesson_rows = (await db.execute(l_stmt)).all()

    # Har bir dars bo'yicha statuslar soni
    counts: dict[int, dict] = {}
    lesson_ids = [r.id for r in lesson_rows]
    if lesson_ids:
        c_stmt = (
            select(Attendance.lesson_id, Attendance.status, func.count())
            .where(Attendance.lesson_id.in_(lesson_ids))
            .group_by(Attendance.lesson_id, Attendance.status)
        )
        for lid, st, cnt in (await db.execute(c_stmt)).all():
            counts.setdefault(lid, {})[st] = cnt

    lessons = []
    for r in lesson_rows:
        c = counts.get(r.id, {})
        present = c.get(AttendanceStatus.PRESENT, 0)
        absent = c.get(AttendanceStatus.ABSENT, 0)
        late = c.get(AttendanceStatus.LATE, 0)
        total = present + absent + late
        lessons.append(
            {
                "id": r.id,
                "day": _lesson_day(r.lesson_date),
                "group_id": r.group_id,
                "group_name": r.group_name,
                "present": present,
                "absent": absent,
                "late": late,
                "percent": round((present + late) * 100 / total) if total else 0,
            }
        )

    # Guruhlar bo'yicha umumiy davomat foizi
    g_stmt = (
        select(Group.id, Group.name, Attendance.status, func.count())
        .join(Lesson, Lesson.group_id == Group.id)
        .join(Attendance, Attendance.lesson_id == Lesson.id)
        .where(Group.center_id == center_id, Group.is_active == True)  # noqa: E712
        .group_by(Group.id, Group.name, Attendance.status)
    )
    stats: dict[int, dict] = {}
    for gid, gname, st, cnt in (await db.execute(g_stmt)).all():
        d = stats.setdefault(
            gid, {"name": gname, "present": 0, "absent": 0, "late": 0, "total": 0}
        )
        d[st.value] = d.get(st.value, 0) + cnt
        d["total"] += cnt
    group_stats = []
    for d in stats.values():
        attended = d["present"] + d["late"]
        group_stats.append(
            {
                "name": d["name"],
                "present": d["present"],
                "absent": d["absent"],
                "late": d["late"],
                "percent": round(attended * 100 / d["total"]) if d["total"] else 0,
            }
        )
    group_stats.sort(key=lambda x: x["name"])

    ctx = await _admin_ctx(db, admin)
    return render(
        request,
        "attendance.html",
        {
            **ctx,
            "groups": groups,
            "lessons": lessons,
            "group_stats": group_stats,
            "f_group_id": group_id,
        },
    )


@router.get("/attendance/{lesson_id}")
async def attendance_detail_page(
    request: Request,
    lesson_id: int,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Dars davomati: tuzatish formasi + ota-ona xabarlari holati"""
    center_id = admin["center_id"]

    lesson = await db.get(Lesson, lesson_id)
    if not lesson:
        raise _not_found()
    group = await db.get(Group, lesson.group_id)
    if not group or group.center_id != center_id:
        raise _not_found()

    stmt = (
        select(Attendance, Student.name)
        .join(Student, Attendance.student_id == Student.id)
        .where(Attendance.lesson_id == lesson.id)
        .order_by(Student.name)
    )
    records = [
        {
            "id": att.id,
            "student_id": att.student_id,
            "name": name,
            "status": att.status.value,
        }
        for att, name in (await db.execute(stmt)).all()
    ]

    n_stmt = (
        select(
            Notification.status,
            Notification.attempts,
            Student.name.label("student_name"),
            User.first_name,
            User.last_name,
        )
        .join(Attendance, Notification.attendance_id == Attendance.id)
        .join(Student, Attendance.student_id == Student.id)
        .join(User, Notification.parent_user_id == User.id)
        .where(Attendance.lesson_id == lesson.id)
        .order_by(Student.name, User.first_name)
    )
    notifications = [
        {
            "student_name": r.student_name,
            "parent_name": " ".join(x for x in [r.first_name, r.last_name] if x) or None,
            "status": r.status.value,
            "attempts": r.attempts,
        }
        for r in (await db.execute(n_stmt)).all()
    ]

    ctx = await _admin_ctx(db, admin)
    return render(
        request,
        "attendance_detail.html",
        {
            **ctx,
            "lesson": lesson,
            "lesson_day": _lesson_day(lesson.lesson_date),
            "group": group,
            "records": records,
            "notifications": notifications,
        },
    )
