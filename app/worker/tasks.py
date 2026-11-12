"""
ARQ worker task'lari (roadmap 9.1, 9.8)

send_pending_notifications(lesson_id) — dars bo'yicha pending
notification'larni yuborish.
reap_stale_notifications — har daqiha ishga tushadigan reaper.
"""
from app.bot.webhook import bot as webhook_bot
from app.core.db import AsyncSessionLocal
from app.services import notification_sender


async def send_pending_notifications(ctx: dict, lesson_id: int) -> dict:
    """Dars bo'yicha pending notification'larni drain qilish"""
    async with AsyncSessionLocal() as session:
        stats = await notification_sender.process_lesson(
            session, webhook_bot, ctx["redis"], lesson_id
        )
        await session.commit()
    return stats


async def reap_stale_notifications(ctx: dict) -> int:
    """Reaper cron — 2 daqiqadan eski pending'larni qayta ishlash"""
    async with AsyncSessionLocal() as session:
        count = await notification_sender.reap_stale(
            session, ctx["redis"], webhook_bot
        )
        await session.commit()
    return count
