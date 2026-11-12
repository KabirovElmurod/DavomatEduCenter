#!/usr/bin/env python3
"""
Bot polling mode'ni boshlash uchun skript.

Lokal rivojlanish uchun webhook o'rniga polling ishlatiladi.
"""
import asyncio
import sys
from app.bot.webhook import start_polling
from app.core.config import settings
from app.core.logging import setup_logging

setup_logging()


async def main():
    # Check if BOT_TOKEN is set
    if not settings.BOT_TOKEN or settings.BOT_TOKEN == "your_bot_token_here":
        print("❌ BOT_TOKEN not set in .env file")
        print("Please add: BOT_TOKEN=your_actual_bot_token")
        sys.exit(1)

    await start_polling()


if __name__ == "__main__":
    asyncio.run(main())
