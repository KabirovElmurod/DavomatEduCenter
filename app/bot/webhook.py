"""
Bot webhook (roadmap 6.1)

POST /bot/webhook endpoint - Telegram webhook update'larini qabul qiladi.
Secret token bilan himoyalangan.
"""

import redis.asyncio as redis
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Update
from fastapi import APIRouter, Header, HTTPException, Request

from app.bot.handlers import router as handlers_router
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Redis client for idempotency
redis_client = redis.from_url(settings.REDIS_URL)

# Bot instance
bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

# Dispatcher (both webhook and polling use same dispatcher)
dp = Dispatcher()
dp.include_router(handlers_router)


async def get_webhook_bot() -> Bot:
    """Webhook uchun bot instance yaratish"""
    return bot


async def set_webhook(bot: Bot) -> None:
    """Webhookni o'rnatish (to'g'ridan-to'g'ri Telegram API)"""
    webhook_url = f"{settings.PUBLIC_URL}{settings.WEBHOOK_PATH}"
    import aiohttp

    async with aiohttp.ClientSession() as client:
        async with client.post(
            f"https://api.telegram.org/bot{settings.BOT_TOKEN}/setWebhook",
            json={
                "url": webhook_url,
                "secret_token": settings.BOT_WEBHOOK_SECRET,
            },
        ) as resp:
            data = await resp.json()
    if not data.get("ok"):
        logger.error("Webhook o'rnatilmadi", response=data)
        raise RuntimeError(f"setWebhook failed: {data}")
    logger.info("Webhook o'rnatildi", url=webhook_url)


async def delete_webhook(bot: Bot) -> None:
    """Webhookni o'chirish"""
    await bot.delete_webhook()
    logger.info("Webhook o'chirildi")


async def is_update_processed(update_id: int) -> bool:
    """
    Update allaqachon qayta ishlanganmi?

    Redis'da 24 soat saqlanadi.
    """
    key = f"webhook:update:{update_id}"
    return await redis_client.exists(key) > 0


async def mark_update_processed(update_id: int) -> None:
    """
    Update'ni qayta ishlangan deb belgilash.

    Redis'da 24 soat saqlanadi.
    """
    key = f"webhook:update:{update_id}"
    await redis_client.setex(key, 86400, "1")  # 24 hours


@router.post(settings.WEBHOOK_PATH)
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None, alias="X-Telegram-Bot-Api-Secret-Token"),
) -> dict:
    """
    Telegram webhook endpoint.

    1. Secret token tekshiruvi
    2. Idempotency: update_id Redis'da 24 soat
    3. Update'ni dispatcher orqali qayta ishlash
    """
    # Secret token validation
    if x_telegram_bot_api_secret_token != settings.BOT_WEBHOOK_SECRET:
        logger.warning("Noto'g'ri webhook secret token")
        raise HTTPException(status_code=403, detail="Invalid secret token")

    # Parse update
    try:
        update_data = await request.json()
        update = Update(**update_data)
    except Exception as e:
        logger.error("Update parsing xatosi", error=str(e))
        raise HTTPException(status_code=400, detail="Invalid update data")

    # Idempotency check
    if await is_update_processed(update.update_id):
        logger.info("Update allaqachon qayta ishlangan", update_id=update.update_id)
        return {"status": "ok", "message": "Update already processed"}

    # Mark as processed
    await mark_update_processed(update.update_id)

    # Process update
    try:
        await dp.feed_webhook_update(bot, update)
        logger.info("Update qayta ishlandi", update_id=update.update_id)
        return {"status": "ok"}
    except TelegramForbiddenError as e:
        # Bot blocked by user
        logger.warning("Bot bloklangan", error=str(e), update_id=update.update_id)
        # TODO: Update parent_links and notification status
        return {"status": "ok", "message": "Bot blocked"}
    except TelegramBadRequest as e:
        logger.error("Telegram API xatosi", error=str(e))
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error("Update qayta ishlash xatosi", error=str(e))
        return {"status": "error", "message": "Internal error"}


async def start_polling() -> None:
    """
    Bot polling mode'ni boshlash (lokal uchun).
    """
    await bot.delete_webhook()
    logger.info("Polling mode boshlandi")
    await dp.start_polling(bot)
