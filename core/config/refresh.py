"""
配置热刷新支持
"""

import logging
from typing import Optional, List

from core.config import get_settings
from core.events import EventType, get_event_bus

logger = logging.getLogger("nexus.config_refresh")


class ConfigRefreshMixin:
    """
    配置热刷新 Mixin
    
    使用方法:
        class MyService(ConfigRefreshMixin):
            def __init__(self):
                self.settings = get_settings()
                self._setup_config_refresh()
    """
    
    _config_refresh_subscriptions: List[str] = []
    
    async def _setup_config_refresh(self) -> None:
        """设置配置刷新监听"""
        bus = await get_event_bus()
        
        sub_id = await bus.subscribe(
            EventType.CONFIG_RELOADED,
            self._on_config_reloaded,
            f"{self.__class__.__name__}_config"
        )
        self._config_refresh_subscriptions.append(sub_id)
        
        logger.debug(f"{self.__class__.__name__} config refresh listener registered")
    
    async def _on_config_reloaded(self, event) -> None:
        """配置重新加载回调"""
        self.settings = get_settings()
        logger.info(f"{self.__class__.__name__} config refreshed")
    
    async def _cleanup_config_refresh(self) -> None:
        """清理配置刷新监听"""
        if hasattr(self, '_config_refresh_subscriptions'):
            bus = await get_event_bus()
            for sub_id in self._config_refresh_subscriptions:
                await bus.unsubscribe(sub_id)
            self._config_refresh_subscriptions.clear()


def with_config_refresh(cls):
    """
    装饰器：为服务类添加配置热刷新支持
    
    使用方法:
        @with_config_refresh
        class MyService:
            def __init__(self):
                self.settings = get_settings()
    """
    original_init = cls.__init__
    original_start = cls.start if hasattr(cls, 'start') else None
    original_stop = cls.stop if hasattr(cls, 'stop') else None
    
    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        # 在初始化时设置配置刷新
        self._config_refresh_subscriptions = []
    
    async def new_start(self, *args, **kwargs):
        # 设置配置刷新监听
        bus = await get_event_bus()
        sub_id = await bus.subscribe(
            EventType.CONFIG_RELOADED,
            lambda event: setattr(self, 'settings', get_settings()),
            f"{cls.__name__}_config"
        )
        self._config_refresh_subscriptions = [sub_id]
        
        if original_start:
            return await original_start(self, *args, **kwargs)
    
    async def new_stop(self, *args, **kwargs):
        # 清理配置刷新监听
        if hasattr(self, '_config_refresh_subscriptions'):
            bus = await get_event_bus()
            for sub_id in self._config_refresh_subscriptions:
                await bus.unsubscribe(sub_id)
        
        if original_stop:
            return await original_stop(self, *args, **kwargs)
    
    cls.__init__ = new_init
    cls.start = new_start
    cls.stop = new_stop
    
    return cls
