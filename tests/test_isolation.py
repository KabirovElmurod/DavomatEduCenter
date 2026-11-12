"""
Tenant izolyatsiya testlari (roadmap 4.9)

Boshqa markaz ma'lumotiga kirish 404/403 qaytarishi kerak.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_user_cannot_access_other_center(client: AsyncClient):
    """
    Foydalanuvchi boshqa markaz ma'lumotiga kirishga harakat qilganda 404 qaytaradi.

    User center_id=1 bo'lsa, center_id=2 ma'lumotiga kirish taqiqlanadi.
    """
    # TODO: DB setup - 2 ta markaz, har birida foydalanuvchilar
    # TODO: Auth token olish (center_id=1 user)
    # TODO: center_id=2 guruhiga yoki o'quvchisiga murojaat qilish
    # TODO: Assert 404 qaytaradi

    pass


@pytest.mark.asyncio
async def test_admin_cannot_access_other_center(client: AsyncClient):
    """
    Admin ham boshqa markaz ma'lumotiga kirishga harakat qilganda 404 qaytaradi.
    """
    # TODO: DB setup - 2 ta markaz, har birida admin
    # TODO: Auth token olish (center_id=1 admin)
    # TODO: center_id=2 guruhiga murojaat qilish
    # TODO: Assert 404 qaytaradi

    pass


@pytest.mark.asyncio
async def test_teacher_cannot_access_other_center_group(client: AsyncClient):
    """
    Ustoz boshqa markaz guruhiga kirishga harakat qilganda 404 qaytaradi.
    """
    # TODO: DB setup - 2 ta markaz, har birida ustoz va guruh
    # TODO: Auth token olish (center_id=1 ustoz)
    # TODO: center_id=2 guruhiga murojaat qilish
    # TODO: Assert 404 qaytaradi

    pass


@pytest.mark.asyncio
async def test_repository_enforces_center_id():
    """
    Repository funksiyalari center_id'ni majburiy tekshiradi.
    """
    # TODO: AsyncSession yaratish
    # TODO: UserRepository(center_id=1) yaratish
    # TODO: center_id=2 user'ni olishga harakat qilish
    # TODO: Assert None qaytaradi

    pass
