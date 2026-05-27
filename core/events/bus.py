"""
异步事件总线实现
基于 Redis Pub/Sub，纯异步
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set
from fnmatch import fnmatch

import redis.asyncio as aioredis

from core.config import get_settings

logger = logging.getLogger("nexus.events")


@dataclass
class Event:
    """结构化事件"""
    channel: str
    data: Dict[str, Any]
    timestamp: str = ""
    source: str = ""
    event_id: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.event_id:
            import hashlib
            raw = f"{self.channel}:{self.timestamp}:{id(self.data)}"
            self.event_id = hashlib.md5(raw.encode()).hexdigest()[:12]
    
    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, default=str)
    
    @classmethod
    def from_json(cls, raw: str) -> "Event":
        d = json.loads(raw)
        return cls(**d)


@dataclass
class Subscription:
    """订阅"""
    pattern: str
    callback: Callable[[Event], Any]
    subscriber_id: str = ""
    
    def matches(self, channel: str) -> bool:
        return fnmatch(channel, self.pattern)


class AsyncEventBus:
    """异步事件总线 - 基于 Redis Pub/Sub"""
    
    def __init__(self, url: Optional[str] = None, prefix: str = "nexus:event:"):
        self._settings = get_settings()
        self._url = url or self._settings.redis.url
        self._prefix = prefix
        
        self._redis: Optional[aioredis.Redis] = None
        self._pubsub: Optional[aioredis.client.PubSub] = None
        self._subscriptions: Dict[str, Subscription] = {}
        self._sub_counter: int = 0
        self._running: bool = False
        self._listener_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
    
    async def connect(self) -> bool:
        """连接 Redis"""
        try:
            self._redis = aioredis.from_url(
                self._url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=10,
            )
            await self._redis.ping()
            self._pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
            logger.info(f"EventBus connected to Redis: {self._url}")
            return True
        except Exception as e:
            logger.error(f"EventBus Redis connection failed: {e}")
            return False
    
    async def start(self) -> None:
        """启动事件总线"""
        if self._running:
            return
        
        if not await self.connect():
            logger.warning("EventBus starting without Redis connection")
        
        self._running = True
        self._listener_task = asyncio.create_task(self._listen_loop())
        logger.info("EventBus started")
    
    async def stop(self) -> None:
        """停止事件总线"""
        self._running = False
        
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        
        if self._pubsub:
            await self._pubsub.close()
        
        if self._redis:
            await self._redis.close()
        
        logger.info("EventBus stopped")
    
    async def publish(self, channel: str, data: Dict[str, Any] = None) -> bool:
        """发布事件"""
        if not self._running:
            await self.start()
        
        event = Event(
            channel=channel,
            data=data or {},
            source=f"pid_{os.getpid()}",
        )
        
        if self._redis:
            try:
                full_channel = f"{self._prefix}{channel}"
                await self._redis.publish(full_channel, event.to_json())
                logger.debug(f"Published event: {channel}")
                return True
            except Exception as e:
                logger.warning(f"Failed to publish event: {e}")
                return False
        
        logger.warning("No Redis connection, event not published")
        return False
    
    async def subscribe(
        self,
        pattern: str,
        callback: Callable[[Event], Any],
        subscriber_id: str = "",
    ) -> str:
        """订阅事件"""
        async with self._lock:
            self._sub_counter += 1
            sub_id = subscriber_id or f"sub_{self._sub_counter}"
            self._subscriptions[sub_id] = Subscription(
                pattern=pattern,
                callback=callback,
                subscriber_id=sub_id,
            )
        
        # 在 Redis 订阅
        if self._pubsub:
            try:
                full_pattern = f"{self._prefix}{pattern}"
                if "*" in pattern or "?" in pattern:
                    await self._pubsub.psubscribe(full_pattern)
                else:
                    await self._pubsub.subscribe(full_pattern)
                logger.debug(f"Subscribed: {sub_id} -> {pattern}")
            except Exception as e:
                logger.warning(f"Failed to subscribe: {e}")
        
        return sub_id
    
    async def unsubscribe(self, subscription_id: str) -> bool:
        """取消订阅"""
        async with self._lock:
            if subscription_id in self._subscriptions:
                sub = self._subscriptions.pop(subscription_id)
                
                if self._pubsub:
                    try:
                        full_pattern = f"{self._prefix}{sub.pattern}"
                        if "*" in sub.pattern or "?" in sub.pattern:
                            await self._pubsub.punsubscribe(full_pattern)
                        else:
                            await self._pubsub.unsubscribe(full_pattern)
                    except Exception:
                        pass
                
                return True
        return False
    
    async def _listen_loop(self) -> None:
        """消息监听循环"""
        reconnect_attempts = 0
        max_delay = 30.0
        
        while self._running:
            try:
                if not self._pubsub:
                    if not await self.connect():
                        delay = min(2 ** reconnect_attempts, max_delay)
                        reconnect_attempts += 1
                        await asyncio.sleep(delay)
                        continue
                    reconnect_attempts = 0
                    
                    # 重新订阅
                    async with self._lock:
                        for sub in self._subscriptions.values():
                            full_pattern = f"{self._prefix}{sub.pattern}"
                            if "*" in sub.pattern or "?" in sub.pattern:
                                await self._pubsub.psubscribe(full_pattern)
                            else:
                                await self._pubsub.subscribe(full_pattern)
                
                # 获取消息
                message = await self._pubsub.get_message(timeout=1.0)
                if message and message["type"] in ("message", "pmessage"):
                    await self._handle_message(message)
                else:
                    await asyncio.sleep(0.01)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._running:
                    logger.warning(f"EventBus listener error: {e}")
                    self._pubsub = None
                    await asyncio.sleep(1)
    
    async def _handle_message(self, message: Dict[str, Any]) -> None:
        """处理收到的消息"""
        try:
            data = message.get("data", "")
            if not isinstance(data, str):
                return
            
            event = Event.from_json(data)
            
            # 分发到本地订阅者
            async with self._lock:
                subs = list(self._subscriptions.values())
            
            for sub in subs:
                if sub.matches(event.channel):
                    try:
                        if asyncio.iscoroutinefunction(sub.callback):
                            await sub.callback(event)
                        else:
                            sub.callback(event)
                    except Exception as e:
                        logger.error(
                            f"Event callback error [{sub.subscriber_id}] "
                            f"channel={event.channel}: {e}",
                            exc_info=True,
                        )
        
        except (json.JSONDecodeError, TypeError) as e:
            logger.debug(f"Failed to parse message: {e}")
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    @property
    def subscriber_count(self) -> int:
        return len(self._subscriptions)


# 全局事件总线实例
_bus: Optional[AsyncEventBus] = None


async def get_event_bus() -> AsyncEventBus:
    """获取全局事件总线实例"""
    global _bus
    if _bus is None:
        _bus = AsyncEventBus()
        await _bus.start()
    return _bus


async def close_event_bus() -> None:
    """关闭全局事件总线"""
    global _bus
    if _bus:
        await _bus.stop()
        _bus = None
