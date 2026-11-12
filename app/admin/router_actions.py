"""
Admin UI action routeri (roadmap 7-bosqich)

HTMX POST endpoint'lari: guruhlar, o'quvchilar, ustozlar, ota-onalar.
Barcha endpoint'lar CSRF + cookie sessiya + tenant izolyatsiyasi bilan.
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.common import get_admin_context, render, telegram_link
from app.core.db import get_db
from app.core.deps import get_current_admin, verify_csrf
from app.models.base import AttendanceStatus, UserRole
from app.models.center import Center
from app.models.group import Group
from app.models.lesson import Lesson
from app.models.parent_link import ParentLink
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.user import User
from app.services.attendance import (
    correct_lesson_attendance,
    enqueue_lesson_notifications,
)
from app.services.audit import AuditService
from app.services.group import GroupService
from app.services.invite import InviteService
from app.services.parent_link import ParentLinkService
from app.services.student import StudentService
from app.services.teacher import TeacherService
from app.services.transfer import TransferService

router = APIRouter(prefix="/admin", tags=["admin-ui-actions"])


def _ok(**extra):
    return JSONResponse({"success": True, **extra})


def _err(detail: str, code: int = 400):
    return JSONResponse({"success": False, "detail": detail}, status_code=code)


async def _center_group(db: AsyncSession, group_id: int, center_id: int) -> Group | None:
    g = await db.get(Group, group_id)
    if not g or g.center_id != center_id:
        return None
    return g


async def _center_student(db: AsyncSession, student_id: int, center_id: int) -> Student | None:
    s = await db.get(Student, student_id)
    if not s or s.center_id != center_id:
        return None
    return s


async def _center_teacher_id(db: AsyncSession, teacher_id: int, center_id: int) -> int | None:
    """Ustoz markazga tegishli bo'lsa Teacher.id qaytaradi"""
    t = await db.get(Teacher, teacher_id)
    if not t:
        return None
    u = await db.get(User, t.user_id)
    if not u or u.center_id != center_id:
        return None
    return t.id


# --------------------------------------------------------------------------
# Guruhlar
# --------------------------------------------------------------------------
@router.post("/groups")
async def group_create(
    name: str = Form(...),
    teacher_id: str = Form(""),
    admin: dict = Depends(get_current_admin),
    _: None = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
):
    """Yangi guruh yaratish"""
    name = name.strip()
    if not name:
        return _err("Guruh nomi bo'sh")

    tid = None
    if teacher_id:
        tid = await _center_teacher_id(db, int(teacher_id), admin["center_id"])
        if tid is None:
            return _err("Ustoz topilmadi", 404)

    svc = GroupService(db)
    await svc.create(
        center_id=admin["center_id"],
        actor_id=admin["user_id"],
        name=name,
        teacher_id=tid,
    )
    await db.commit()
    return _ok()


@router.post("/groups/{group_id}")
async def group_update(
    group_id: int,
    name: str = Form(...),
    teacher_id: str = Form(""),
    admin: dict = Depends(get_current_admin),
    _: None = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
):
    """Guruhni tahrirlash (nom + ustoz)"""
    group = await _center_group(db, group_id, admin["center_id"])
    if not group:
        return _err("Guruh topilmadi", 404)

    tid = None
    if teacher_id:
        tid = await _center_teacher_id(db, int(teacher_id), admin["center_id"])
        if tid is None:
            return _err("Ustoz topilmadi", 404)

    svc = GroupService(db)
    updated = await svc.update(
        group_id=group_id,
        center_id=admin["center_id"],
        actor_id=admin["user_id"],
        name=name.strip() or None,
        teacher_id=tid,
        clear_teacher=(teacher_id == ""),
    )
    if not updated:
        return _err("Guruh topilmadi", 404)
    await db.commit()
    return _ok()


@router.post("/groups/{group_id}/archive")
async def group_archive(
    group_id: int,
    admin: dict = Depends(get_current_admin),
    _: None = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
):
    """Guruhni arxivlash"""
    svc = GroupService(db)
    group = await svc.archive(
        group_id=group_id,
        center_id=admin["center_id"],
        actor_id=admin["user_id"],
    )
    if not group:
        return _err("Guruh topilmadi", 404)
    await db.commit()
    return _ok()


@router.post("/groups/merge")
async def groups_merge(
    source_id: int = Form(...),
    target_id: int = Form(...),
    admin: dict = Depends(get_current_admin),
    _: None = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
):
    """Guruhlarni birlashtirish (manba -> maqsad, manba arxivlanadi)"""
    if source_id == target_id:
        return _err("Manba va maqsad guruh bir xil bo'lishi mumkin emas")

    if not await _center_group(db, source_id, admin["center_id"]):
        return _err("Manba guruh topilmadi", 404)
    if not await _center_group(db, target_id, admin["center_id"]):
        return _err("Maqsad guruh topilmadi", 404)

    svc = TransferService(db)
    moved = await svc.merge_groups(
        source_group_id=source_id,
        target_group_id=target_id,
        center_id=admin["center_id"],
        actor_id=admin["user_id"],
    )
    await db.commit()
    return _ok(moved=len(moved))


# --------------------------------------------------------------------------
# O'quvchilar
# --------------------------------------------------------------------------
@router.post("/students")
async def student_create(
    name: str = Form(...),
    group_id: str = Form(""),
    admin: dict = Depends(get_current_admin),
    _: None = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
):
    """Yakka o'quvchi qo'shish"""
    name = name.strip()
    if not name:
        return _err("Ism bo'sh")

    gid = int(group_id) if group_id else None
    if gid and not await _center_group(db, gid, admin["center_id"]):
        return _err("Guruh topilmadi", 404)

    svc = StudentService(db)
    await svc.create(
        center_id=admin["center_id"],
        actor_id=admin["user_id"],
        name=name,
        group_id=gid,
    )
    await db.commit()
    return _ok()


@router.post("/students/bulk")
async def students_bulk_create(
    names: str = Form(...),
    group_id: str = Form(""),
    admin: dict = Depends(get_current_admin),
    _: None = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
):
    """Ommaviy qo'shish (har qatorga bitta ism)"""
    gid = int(group_id) if group_id else None
    if gid and not await _center_group(db, gid, admin["center_id"]):
        return _err("Guruh topilmadi", 404)

    svc = StudentService(db)
    names_list = svc.parse_names_text(names)
    if not names_list:
        return _err("Ismlar topilmadi")

    created = await svc.bulk_create(
        center_id=admin["center_id"],
        actor_id=admin["user_id"],
        names_text=names,
        group_id=gid,
    )
    await db.commit()
    return _ok(created=len(created))


@router.post("/students/{student_id}")
async def student_update(
    student_id: int,
    request: Request,
    name: str = Form(...),
    group_id: str = Form(""),
    admin: dict = Depends(get_current_admin),
    _: None = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
):
    """O'quvchini tahrirlash: ism + guruh (ko'chirish tarixi bilan)"""
    student = await _center_student(db, student_id, admin["center_id"])
    if not student:
        return _err("O'quvchi topilmadi", 404)

    name = name.strip()
    if not name:
        return _err("Ism bo'sh")

    new_gid = int(group_id) if group_id else None
    old_gid = student.group_id

    if new_gid and new_gid != old_gid:
        if not await _center_group(db, new_gid, admin["center_id"]):
            return _err("Guruh topilmadi", 404)

    # Ism yangilash
    svc = StudentService(db)
    await svc.update(
        student_id=student_id,
        center_id=admin["center_id"],
        actor_id=admin["user_id"],
        name=name,
    )

    # Guruh o'zgarishi
    if new_gid and new_gid != old_gid:
        transfer = TransferService(db)
        await transfer.transfer_student(
            student_id=student_id,
            center_id=admin["center_id"],
            actor_id=admin["user_id"],
            new_group_id=new_gid,
        )
    elif new_gid is None and old_gid is not None:
        # Guruhsiz qilish (tarix yozilmaydi - guruh yo'q)
        old = {"name": student.name, "group_id": old_gid}
        student.group_id = None
        await db.flush()
        audit = AuditService(db)
        await audit.log_update(
            center_id=admin["center_id"],
            actor_id=admin["user_id"],
            entity="student",
            entity_id=student_id,
            old=old,
            new={"name": name, "group_id": None},
        )

    await db.commit()
    return RedirectResponse("/admin/students", status_code=303)


@router.post("/students/{student_id}/archive")
async def student_archive(
    student_id: int,
    request: Request,
    q: str = Form(""),
    group_id: str = Form(""),
    parent_status: str = Form(""),
    status: str = Form("active"),
    admin: dict = Depends(get_current_admin),
    _: None = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
):
    """O'quvchini arxivlash -> yangilangan jadval fragmenti"""
    student = await _center_student(db, student_id, admin["center_id"])
    if not student:
        return _err("O'quvchi topilmadi", 404)

    svc = StudentService(db)
    await svc.archive(
        student_id=student_id,
        center_id=admin["center_id"],
        actor_id=admin["user_id"],
    )
    await db.commit()
    return await _students_table_response(request, db, admin, q, group_id, parent_status, status)


@router.post("/students/{student_id}/restore")
async def student_restore(
    student_id: int,
    request: Request,
    q: str = Form(""),
    group_id: str = Form(""),
    parent_status: str = Form(""),
    status: str = Form("active"),
    admin: dict = Depends(get_current_admin),
    _: None = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
):
    """Arxivlangan o'quvchini tiklash -> yangilangan jadval fragmenti"""
    student = await _center_student(db, student_id, admin["center_id"])
    if not student:
        return _err("O'quvchi topilmadi", 404)

    svc = StudentService(db)
    await svc.restore(
        student_id=student_id,
        center_id=admin["center_id"],
        actor_id=admin["user_id"],
    )
    await db.commit()
    return await _students_table_response(request, db, admin, q, group_id, parent_status, status)


async def _students_table_response(
    request: Request,
    db: AsyncSession,
    admin: dict,
    q: str,
    group_id: str,
    parent_status: str,
    status: str,
):
    """Jadval fragmentini qayta render qilish"""
    from app.admin.router_pages import _students_select

    gid = int(group_id) if group_id else None
    center_id = admin["center_id"]
    rows = (await db.execute(_students_select(center_id, q, gid, parent_status, status))).all()
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
    ctx = await get_admin_context(db, admin)
    return render(request, "_students_table.html", {**ctx, "students": students})


@router.post("/students/bulk-transfer")
async def students_bulk_transfer(
    student_ids: list[int] = Form(default=[]),
    group_id: int = Form(...),
    admin: dict = Depends(get_current_admin),
    _: None = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
):
    """Belgilangan o'quvchilarni ommaviy ko'chirish (bitta tranzaksiya)"""
    if not student_ids:
        return _err("O'quvchilar tanlanmagan")

    if not await _center_group(db, group_id, admin["center_id"]):
        return _err("Guruh topilmadi", 404)

    svc = TransferService(db)
    moved = await svc.bulk_transfer(
        student_ids=student_ids,
        center_id=admin["center_id"],
        actor_id=admin["user_id"],
        new_group_id=group_id,
    )
    await db.commit()
    return _ok(moved=len(moved))


# --------------------------------------------------------------------------
# Platforma admin: markaz yaratish (faqat super_admin)
# --------------------------------------------------------------------------
@router.post("/centers")
async def center_create(
    name: str = Form(...),
    subdomain: str = Form(""),
    owner_telegram_id: int = Form(...),
    owner_first_name: str = Form(...),
    owner_last_name: str = Form(""),
    owner_username: str = Form(""),
    admin: dict = Depends(get_current_admin),
    _: None = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
):
    """Yangi markaz + owner yaratish (super_admin)"""
    if admin.get("role") != "super_admin":
        return _err("Faqat super_admin", 403)

    name = name.strip()
    owner_first_name = owner_first_name.strip()
    if not name or not owner_first_name:
        return _err("Markaz nomi va owner ismi majburiy")

    from app.core.urls import normalize_subdomain

    slug = normalize_subdomain(subdomain)
    if subdomain.strip() and slug is None:
        return _err("Subdomain noto'g'ri (faqat a-z, 0-9, -, 50 belgigacha)")
    if slug:
        dup = await db.execute(select(Center.id).where(Center.subdomain == slug))
        if dup.scalar_one_or_none():
            return _err("Bu subdomain band", 409)

    # Owner telegram_id band emasligi kerak
    existing = await db.execute(select(User).where(User.telegram_id == owner_telegram_id))
    if existing.scalar_one_or_none():
        return _err("Bu telegram_id bilan user allaqachon mavjud", 409)

    center = Center(name=name, subdomain=slug, is_active=True)
    db.add(center)
    await db.flush()

    owner = User(
        telegram_id=owner_telegram_id,
        first_name=owner_first_name,
        last_name=owner_last_name.strip() or None,
        username=owner_username.strip() or None,
        role=UserRole.OWNER,
        center_id=center.id,
        is_active=True,
    )
    db.add(owner)
    await db.flush()

    audit = AuditService(db)
    await audit.log_create(
        center_id=center.id,
        actor_id=admin["user_id"],
        entity="center",
        entity_id=center.id,
        new={"name": name, "subdomain": slug, "owner_telegram_id": owner_telegram_id},
    )
    await db.commit()
    return _ok(center_id=center.id)


# --------------------------------------------------------------------------
# Ustozlar
# --------------------------------------------------------------------------
@router.post("/teachers/invite")
async def teacher_invite(
    request: Request,
    role: str = Form("teacher"),
    admin: dict = Depends(get_current_admin),
    _: None = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
):
    """Ustoz/admin uchun taklif havolasi yaratish -> fragment"""
    try:
        user_role = UserRole(role)
    except ValueError:
        return _err("Noto'g'ri rol")
    if user_role not in (UserRole.TEACHER, UserRole.ADMIN):
        return _err("Faqat ustoz yoki admin uchun")

    svc = InviteService(db)
    invite = await svc.create(
        center_id=admin["center_id"],
        actor_id=admin["user_id"],
        role=user_role,
    )
    await db.commit()

    ctx = await get_admin_context(db, admin)
    return render(
        request,
        "_invite_link.html",
        {
            **ctx,
            "url": await telegram_link(invite.token),
            "role": user_role.value,
        },
    )


@router.post("/teachers/{teacher_id}/deactivate")
async def teacher_deactivate(
    teacher_id: int,
    admin: dict = Depends(get_current_admin),
    _: None = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
):
    """Ustozni nofaol qilish (guruhlar 'ustozsiz' bo'ladi)"""
    svc = TeacherService(db)
    teacher = await svc.deactivate(
        teacher_id=teacher_id,
        center_id=admin["center_id"],
        actor_id=admin["user_id"],
    )
    if not teacher:
        return _err("Ustoz topilmadi", 404)
    await db.commit()
    return _ok()


@router.post("/teachers/{teacher_id}/activate")
async def teacher_activate(
    teacher_id: int,
    admin: dict = Depends(get_current_admin),
    _: None = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
):
    """Nofaol ustozni faollashtirish"""
    svc = TeacherService(db)
    teacher = await svc.activate(
        teacher_id=teacher_id,
        center_id=admin["center_id"],
        actor_id=admin["user_id"],
    )
    if not teacher:
        return _err("Ustoz topilmadi", 404)
    await db.commit()
    return _ok()


# --------------------------------------------------------------------------
# Davomat tuzatish (roadmap 10-bosqich)
# --------------------------------------------------------------------------
@router.post("/attendance/{lesson_id}")
async def attendance_correct(
    lesson_id: int,
    request: Request,
    notify: str = Form(""),
    admin: dict = Depends(get_current_admin),
    _: None = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
):
    """Dars davomati: statuslarni tuzatish + ixtiyoriy ota-ona xabari"""
    lesson = await db.get(Lesson, lesson_id)
    if not lesson:
        return _err("Dars topilmadi", 404)
    group = await db.get(Group, lesson.group_id)
    if not group or group.center_id != admin["center_id"]:
        return _err("Dars topilmadi", 404)

    # Dinamik maydonlar: status_{attendance_id}
    form = await request.form()
    updates: dict[int, AttendanceStatus] = {}
    for key, value in form.items():
        if not key.startswith("status_"):
            continue
        try:
            updates[int(key[len("status_") :])] = AttendanceStatus(value)
        except (ValueError, KeyError):
            return _err("Noto'g'ri holat")
    if not updates:
        return _err("O'zgarishlar yuborilmagan")

    result = await correct_lesson_attendance(
        db,
        lesson=lesson,
        updates=updates,
        actor_id=admin["user_id"],
        center_id=admin["center_id"],
        notify_parents=bool(notify),
    )
    await db.commit()

    # Yangi pending notification'lar bo'lsa ARQ'ga enqueue
    if result["notifications"]:
        await enqueue_lesson_notifications(lesson.id)

    return RedirectResponse(f"/admin/attendance/{lesson_id}", status_code=303)


# --------------------------------------------------------------------------
# Ota-onalar
# --------------------------------------------------------------------------
@router.post("/parents/create")
async def parent_link_create(
    student_id: int = Form(...),
    admin: dict = Depends(get_current_admin),
    _: None = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
):
    """O'quvchi uchun ota-ona havolasi yaratish"""
    if not await _center_student(db, student_id, admin["center_id"]):
        return _err("O'quvchi topilmadi", 404)

    svc = ParentLinkService(db)
    link = await svc.create(
        student_id=student_id,
        center_id=admin["center_id"],
        actor_id=admin["user_id"],
    )
    if not link:
        return _err("Havola yaratib bo'lmadi", 500)
    await db.commit()
    return _ok(url=await telegram_link(link.invite_token))


@router.post("/parents/bulk-create")
async def parent_links_bulk_create(
    request: Request,
    admin: dict = Depends(get_current_admin),
    _: None = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
):
    """Barcha ulanmagan o'quvchilar uchun havola yaratish -> fragment"""
    from app.admin.router_pages import _students_select  # noqa: F401  (izolyatsiya uchun)

    center_id = admin["center_id"]

    has_active_link = (
        select(ParentLink.id)
        .where(ParentLink.student_id == Student.id, ParentLink.revoked_at.is_(None))
        .exists()
    )
    stmt = (
        select(Student)
        .where(
            Student.center_id == center_id,
            Student.is_active == True,  # noqa: E712
            ~has_active_link,
        )
        .order_by(Student.name)
    )
    students = (await db.execute(stmt)).scalars().all()

    svc = ParentLinkService(db)
    links = []
    for s in students:
        link = await svc.create(
            student_id=s.id,
            center_id=center_id,
            actor_id=admin["user_id"],
        )
        if link:
            links.append({"name": s.name, "url": await telegram_link(link.invite_token)})
    await db.commit()

    ctx = await get_admin_context(db, admin)
    return render(request, "_parent_links.html", {**ctx, "links": links})


@router.post("/parents/{link_id}/regenerate")
async def parent_link_regenerate(
    link_id: int,
    admin: dict = Depends(get_current_admin),
    _: None = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
):
    """Ota-ona havolasini qayta generatsiya qilish"""
    svc = ParentLinkService(db)
    link = await svc.regenerate(
        parent_link_id=link_id,
        center_id=admin["center_id"],
        actor_id=admin["user_id"],
    )
    if not link:
        return _err("Havola topilmadi", 404)
    await db.commit()
    return _ok(url=await telegram_link(link.invite_token))


@router.post("/parents/{link_id}/revoke")
async def parent_link_revoke(
    link_id: int,
    admin: dict = Depends(get_current_admin),
    _: None = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
):
    """Ota-ona bog'lanishini uzish"""
    svc = ParentLinkService(db)
    link = await svc.revoke(
        parent_link_id=link_id,
        center_id=admin["center_id"],
        actor_id=admin["user_id"],
    )
    if not link:
        return _err("Havola topilmadi", 404)
    await db.commit()
    return _ok()
