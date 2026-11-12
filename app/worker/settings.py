from urllib.parse import urlparse

from arq import cron, func
from arq.connections import RedisSettings

from app.core.config import settings
from app.worker.tasks import reap_stale_notifications, send_pending_notifications

reaper_cron = cron(
    reap_stale_notifications,
    minute=set(range(60)),
)


def _redis_settings() -> RedisSettings:
    """REDIS_URL (redis://host:port/db) -> arq RedisSettings"""
    u = urlparse(settings.REDIS_URL)
    return RedisSettings(
        host=u.hostname or "localhost",
        port=u.port or 6379,
        database=int(u.path.lstrip("/") or 0),
        password=u.password,
    )


class WorkerSettings:
    functions = [
        func(send_pending_notifications),
        func(reap_stale_notifications),
    ]
    cron_jobs = [reaper_cron]
    redis_settings = _redis_settings()
