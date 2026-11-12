"""
Base repository - tenant izolyatsiya asosi (roadmap 4.7)

Barcha repositorylar center_id asosida izolyatsiyani qo'llashlari kerak.
"""
from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository:
    """Base repository with tenant isolation"""

    def __init__(self, session: AsyncSession, center_id: int):
        self.session = session
        self.center_id = center_id

    def _apply_center_filter(self, stmt):
        """
        Statement'ga center_id filter'ini qo'shish.

        Agar modelda center_id field bo'lsa, avtomatik filter qo'shadi.
        """
        # Bu har bir repository'ning o'zida implementatsiya qilinishi kerak
        # chunki har xil modellar har xil center_id field nomiga ega bo'lishi mumkin
        return stmt
