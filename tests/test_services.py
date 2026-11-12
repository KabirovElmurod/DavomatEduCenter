"""
Servis testlari (roadmap 5.12, 5.13, 5.14)

Ko'chirish testlari, rollback testlari, audit testlari.
"""
import pytest


@pytest.mark.asyncio
async def test_transfer_preserves_old_attendance(db_session):
    """
    Ko'chirishdan keyin eski davomat o'zgarmaydi (5.12).

    O'quvchi guruhdan boshqa guruhga ko'chirilganda,
    eski darslardagi davomat o'zgarmaydi.
    """
    # TODO: DB setup:
    # - 2 ta guruh
    # - 1 ta o'quvchi (guruh 1)
    # - Guruh 1 da 2 ta dars
    # - Har darsda davomat yozilgan

    # TODO: TransferService.transfer_student() orqali guruh 2 ga ko'chirish

    # TODO: Eski darslardagi davomatni tekshirish
    # Assert attendance.teacher_id o'zgarmagan

    pass


@pytest.mark.asyncio
async def test_bulk_transfer_rollback_on_error(db_session):
    """
    Ommaviy ko'chirish yarim yo'lda xato bersa rollback (5.13).

    Agar ommaviy ko'chirish jarayonida xato bo'lsa,
    barcha o'zgarishlar bekor bo'ladi (rollback).
    """
    # TODO: DB setup:
    # - 2 ta guruh
    # - 3 ta o'quvchi (guruh 1)

    # TODO: bulk_transfer() chaqirish, lekin bitta noto'g'ri student_id bilan

    # TODO: Assert hech qanday o'quvchi ko'chirilmagan
    # Assert student_group_history'da yangi yozuv yo'q

    pass


@pytest.mark.asyncio
async def test_every_action_creates_audit_log(db_session):
    """
    Har amalda audit yozuvi bor (5.14).

    Create, update, delete amallarida audit_log'ga yozuv tushadi.
    """

    # TODO: DB setup - center, actor user

    # Test create
    # center_service = CenterService(db_session)
    # center, owner = await center_service.create(...)
    # Assert audit_log'da create yozuvi bor

    # Test update
    # await center_service.update(...)
    # Assert audit_log'da update yozuvi bor

    # Test group create
    # group_service = GroupService(db_session)
    # group = await group_service.create(...)
    # Assert audit_log'da create yozuvi bor

    pass


@pytest.mark.asyncio
async def test_cannot_access_other_center_data(db_session):
    """
    Boshqa markaz ma'lumotiga tegib bo'lmaydi (5.14).

    Tenant izolyatsiya ishlaydi.
    """
    # TODO: DB setup - 2 ta markaz, har birida guruhlar

    # TODO: Markaz 1 bilan markaz 2 guruhiga murojaat qilishga harakat
    # Assert 404 qaytaradi

    pass


def test_parse_names_text():
    """
    StudentService.parse_names_text() ishlaydi (5.7).
    """
    from app.services.student import StudentService

    service = StudentService(None)  # session kerak emas

    # Test basic parsing
    text = "Ali\nVali\nHasan"
    names = service.parse_names_text(text)
    assert names == ["Ali", "Vali", "Hasan"]

    # Test empty lines
    text = "Ali\n\n\nVali\n"
    names = service.parse_names_text(text)
    assert names == ["Ali", "Vali"]

    # Test duplicates
    text = "Ali\nVali\nAli\nHasan\nVali"
    names = service.parse_names_text(text)
    assert names == ["Ali", "Vali", "Hasan"]


def test_invite_token_generation():
    """
    InviteService token generatsiyasi ishlaydi (5.3).
    """
    from app.services.invite import InviteService

    service = InviteService(None)  # session kerak emas

    token1 = service._generate_token()
    token2 = service._generate_token()

    # Tokens should be unique
    assert token1 != token2

    # Tokens should start with prefix if defined
    # assert token1.startswith("t_")  # yoki boshqa prefix
