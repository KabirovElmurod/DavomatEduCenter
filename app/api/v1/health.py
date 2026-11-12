import redis.asyncio as redis
from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/health")
async def health_check():
    db_healthy = False
    redis_healthy = False

    # Check database
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
            db_healthy = True
    except Exception as e:
        logger.error("database health check failed", error=str(e))

    # Check redis
    try:
        r = redis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.close()
        redis_healthy = True
    except Exception as e:
        logger.error("redis health check failed", error=str(e))

    health_status = {
        "status": "healthy" if db_healthy and redis_healthy else "unhealthy",
        "database": "ok" if db_healthy else "error",
        "redis": "ok" if redis_healthy else "error",
    }

    logger.info("health_check", **health_status)
    return health_status
