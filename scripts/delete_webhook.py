#!/usr/bin/env python3
"""
Webhook'ni o'chirish uchun skript.
"""
import asyncio
from aiogram import Bot
from app.core.config import settings
from app.core.logging import setup_logging

setup_logging()


async def main():
    bot = Bot(token=settings.BOT_TOKEN)
    await bot.delete_webhook()
    print("Webhook o'chirildi")
    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
