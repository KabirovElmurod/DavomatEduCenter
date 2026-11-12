from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware import Middleware
from fastapi.staticfiles import StaticFiles

from app.admin import router_actions, router_auth, router_pages
from app.api.v1 import auth, groups, health, me, teacher
from app.bot.webhook import delete_webhook, get_webhook_bot, set_webhook
from app.bot.webhook import router as webhook_router
from app.core.config import settings
from app.core.deps import AdminAuthError, admin_auth_exception_handler
from app.core.logging import RequestIDMiddleware, setup_logging

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - webhook setup on startup (production)"""
    # Startup
    bot = await get_webhook_bot()
    # Only set webhook if not in polling mode
    if settings.PUBLIC_URL.strip() != "http://localhost:8000":
        await set_webhook(bot)
    yield
    # Shutdown
    if settings.PUBLIC_URL.strip() != "http://localhost:8000":
        await delete_webhook(bot)


app = FastAPI(
    title="Education Center Attendance System",
    description="Davomat tizimi API",
    version="0.1.0",
    middleware=[Middleware(RequestIDMiddleware)],
    lifespan=lifespan,
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(me.router, prefix="/api/v1", tags=["me"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(teacher.router, prefix="/api/v1", tags=["teacher"])
app.include_router(groups.router, prefix="/api/v1", tags=["groups"])
app.include_router(router_auth.router, prefix="/admin", tags=["admin"])
app.include_router(router_pages.router, tags=["admin-ui"])
app.include_router(router_actions.router, tags=["admin-ui-actions"])
app.include_router(webhook_router, tags=["bot"])

# Ustoz WebApp (Vite build -> webapp/dist)
webapp_dist = Path(__file__).resolve().parent.parent / "webapp" / "dist"
if webapp_dist.exists():
    app.mount("/webapp", StaticFiles(directory=webapp_dist, html=True), name="webapp")

app.add_exception_handler(AdminAuthError, admin_auth_exception_handler)
