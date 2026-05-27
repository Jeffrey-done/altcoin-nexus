"""
配置热加载管理器
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from functools import lru_cache

import yaml

from core.config import get_settings, reload_settings
from core.events import EventType, get_event_bus

logger = logging.getLogger("nexus.config_manager")


class ConfigManager:
    """
    配置管理器
    
    功能：
    1. 监听配置文件变更
    2. 热加载配置
    3. 通知所有服务
    """
    
    def __init__(self):
        self._running = False
        self._watch_task: Optional[asyncio.Task] = None
        self._callbacks: Dict[str, List[Callable]] = {}
        self._last_reload: Optional[datetime] = None
        
        # 配置文件路径
        self._config_dir = Path(__file__).parent.parent.parent / "config"
        self._file_mtimes: Dict[str, float] = {}
    
    async def start(self) -> None:
        """启动配置管理器"""
        if self._running:
            return
        
        self._running = True
        
        # 记录初始文件修改时间
        self._scan_files()
        
        # 启动文件监听
        self._watch_task = asyncio.create_task(self._watch_loop())
        
        # 注册事件监听
        await self._register_listeners()
        
        logger.info("ConfigManager started")
    
    async def stop(self) -> None:
        """停止配置管理器"""
        self._running = False
        
        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
        
        logger.info("ConfigManager stopped")
    
    def _scan_files(self) -> None:
        """扫描配置文件"""
        if not self._config_dir.exists():
            return
        
        for yaml_file in self._config_dir.glob("*.yaml"):
            self._file_mtimes[str(yaml_file)] = yaml_file.stat().st_mtime
    
    async def _watch_loop(self) -> None:
        """文件监听循环"""
        while self._running:
            try:
                await asyncio.sleep(5)  # 每 5 秒检查
                
                changed = self._check_changes()
                if changed:
                    logger.info(f"Config files changed: {changed}")
                    await self._reload_and_notify(changed)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Config watch error: {e}")
    
    def _check_changes(self) -> List[str]:
        """检查文件变更"""
        changed = []
        
        if not self._config_dir.exists():
            return changed
        
        for yaml_file in self._config_dir.glob("*.yaml"):
            file_path = str(yaml_file)
            current_mtime = yaml_file.stat().st_mtime
            last_mtime = self._file_mtimes.get(file_path, 0)
            
            if current_mtime > last_mtime:
                changed.append(yaml_file.name)
                self._file_mtimes[file_path] = current_mtime
        
        return changed
    
    async def _reload_and_notify(self, changed_files: List[str]) -> None:
        """重新加载并通知"""
        try:
            # 重新加载配置
            reload_settings()
            self._last_reload = datetime.now(timezone.utc)
            
            # 发布配置变更事件
            bus = await get_event_bus()
            await bus.publish(EventType.CONFIG_RELOADED, {
                "changed_files": changed_files,
                "timestamp": self._last_reload.isoformat(),
            })
            
            # 调用注册的回调
            for file_name in changed_files:
                for callback in self._callbacks.get(file_name, []):
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback()
                        else:
                            callback()
                    except Exception as e:
                        logger.error(f"Config callback error: {e}")
            
            logger.info(f"Config reloaded: {changed_files}")
        
        except Exception as e:
            logger.error(f"Config reload failed: {e}")
    
    async def _register_listeners(self) -> None:
        """注册事件监听"""
        bus = await get_event_bus()
        
        # 监听手动配置变更
        await bus.subscribe(
            EventType.CONFIG_CHANGED,
            self._on_config_changed,
            "config_manager"
        )
    
    async def _on_config_changed(self, event) -> None:
        """处理手动配置变更"""
        data = event.data
        key = data.get("key", "")
        value = data.get("value")
        
        logger.info(f"Config changed via API: {key} = {value}")
        
        # 这里可以添加持久化逻辑
        # 例如写入 runtime_config.json
    
    def on_change(self, file_name: str, callback: Callable) -> None:
        """注册配置变更回调"""
        if file_name not in self._callbacks:
            self._callbacks[file_name] = []
        self._callbacks[file_name].append(callback)
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "running": self._running,
            "config_dir": str(self._config_dir),
            "watched_files": list(self._file_mtimes.keys()),
            "last_reload": self._last_reload.isoformat() if self._last_reload else None,
        }


# 全局单例
_manager: Optional[ConfigManager] = None


async def get_config_manager() -> ConfigManager:
    """获取全局配置管理器"""
    global _manager
    if _manager is None:
        _manager = ConfigManager()
        await _manager.start()
    return _manager
