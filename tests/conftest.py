"""
测试配置
"""

import asyncio
import pytest
from typing import AsyncGenerator

from core.config import Settings
from core.db import AsyncDatabase, Base


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_settings() -> Settings:
    """测试配置"""
    return Settings(
        database_url="sqlite+aiosqlite:///./test.db",
        redis_url="redis://localhost:6379/1",
        environment="testing",
    )


@pytest.fixture(scope="session")
async def test_db(test_settings) -> AsyncGenerator[AsyncDatabase, None]:
    """测试数据库"""
    db = AsyncDatabase(url=test_settings.database_url)
    await db.initialize()
    await db.create_all()
    yield db
    await db.drop_all()
    await db.close()


@pytest.fixture
async def db_session(test_db):
    """数据库会话"""
    async with test_db.session() as session:
        yield session
