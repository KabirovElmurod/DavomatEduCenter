#!/usr/bin/env python3
"""
Invite token yaratish uchun skript (bot sinash uchun).
"""
import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import AsyncSessionLocal
from app.models.invite import Invite
from app.models.center import Center
from app.models.user import User
from app.models.base import UserRole
import secrets


async def create_invite():
    async with AsyncSessionLocal() as session:
        # Center topish yoki yaratish
        stmt = select(Center).limit(1)
        result = await session.execute(stmt)
        center = result.scalar_one_or_none()

        if not center:
            print("Markaz topilmadi. Yangi markaz yaratamiz...")
            center = Center(name="Test Center")
            session.add(center)
            await session.flush()
            await session.refresh(center)
            print(f"Markaz yaratildi: {center.name} (ID: {center.id})")

        # Teacher invite token yaratish
        token = "t_" + secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        invite = Invite(
            token=token,
            role=UserRole.TEACHER,
            center_id=center.id,
            expires_at=expires_at,
            used_at=None,
        )
        session.add(invite)
        await session.commit()

        print(f"\nInvite token yaratildi:")
        print(f"Token: {token}")
        print(f"Role: teacher")
        print(f"Center ID: {center.id}")
        print(f"Expires: {expires_at}")
        print(f"\nTelegramda sinash uchun: /start {token}")


if __name__ == "__main__":
    asyncio.run(create_invite())
