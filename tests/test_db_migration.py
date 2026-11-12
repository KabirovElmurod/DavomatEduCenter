"""Test database migrations and constraints"""
import pytest
from sqlalchemy import text

from app.core.db import engine


@pytest.mark.asyncio
async def test_migration_upgrade():
    """Test that migration upgrade works"""
    async with engine.begin() as conn:
        # Check tables exist
        result = await conn.execute(text("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
        """))
        tables = [row[0] for row in result]
        assert "centers" in tables
        assert "users" in tables
        assert "groups" in tables
        assert "students" in tables
        assert "lessons" in tables
        assert "attendance" in tables


@pytest.mark.asyncio
async def test_unique_constraints():
    """Test that UNIQUE constraints work"""
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.core.config import settings

    # Create separate engine for this test
    test_engine = create_async_engine(settings.DATABASE_URL)

    async with test_engine.begin() as conn:
        # Try to insert duplicate telegram_id - should fail
        with pytest.raises(Exception):
            await conn.execute(text("""
                INSERT INTO users (telegram_id, first_name, role, center_id, is_active)
                VALUES (1001, 'Test', 'owner', 1, true)
            """))

    await test_engine.dispose()
