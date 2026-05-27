"""
异步数据库连接管理
使用 SQLAlchemy asyncio + asyncpg
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text

from core.config import get_settings


class AsyncDatabase:
    """异步数据库管理器"""
    
    def __init__(self, url: Optional[str] = None):
        self._settings = get_settings()
        self._url = url or self._settings.database.url
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker] = None
        # Guard async initialization to avoid duplicate pools under concurrency.
        self._init_lock = asyncio.Lock()
    
    async def initialize(self) -> None:
        """初始化数据库连接"""
        if self._engine is not None:
            return

        async with self._init_lock:
            if self._engine is not None:
                return

            self._engine = create_async_engine(
                self._url,
                echo=self._settings.database.echo,
                pool_size=self._settings.database.pool_size,
                max_overflow=self._settings.database.max_overflow,
                pool_timeout=self._settings.database.pool_timeout,
                pool_recycle=self._settings.database.pool_recycle,
                pool_pre_ping=True,
            )

            self._session_factory = async_sessionmaker(
                bind=self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
    
    async def close(self) -> None:
        """关闭数据库连接"""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取异步会话上下文管理器"""
        if self._session_factory is None:
            await self.initialize()
        
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    
    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncSession, None]:
        """获取事务上下文管理器（手动控制事务）"""
        if self._session_factory is None:
            await self.initialize()
        
        async with self._session_factory() as session:
            async with session.begin():
                yield session
    
    async def create_all(self) -> None:
        """创建所有表（开发/测试用）"""
        from .models import Base
        
        if self._engine is None:
            await self.initialize()
        
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def drop_all(self) -> None:
        """删除所有表（仅测试用）"""
        from .models import Base
        
        if self._engine is None:
            await self.initialize()
        
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    
    @property
    def engine(self) -> Optional[AsyncEngine]:
        return self._engine
    
    async def health_check(self) -> bool:
        """数据库健康检查"""
        try:
            if self._engine is None:
                await self.initialize()
            
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False


# 全局数据库实例
_db: Optional[AsyncDatabase] = None
_db_lock: asyncio.Lock = asyncio.Lock()


async def get_db() -> AsyncDatabase:
    """获取全局数据库实例（线程安全）"""
    global _db
    if _db is not None:
        return _db
    
    async with _db_lock:
        # Double-check: 可能在等待锁期间已被其他协程初始化
        if _db is None:
            _db = AsyncDatabase()
            await _db.initialize()
        return _db


async def close_db() -> None:
    """关闭全局数据库连接"""
    global _db
    async with _db_lock:
        if _db:
            await _db.close()
            _db = None
