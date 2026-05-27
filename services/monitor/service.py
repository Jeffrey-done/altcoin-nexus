"""
监控告警服务
系统可观测性、健康检查、自动对账
"""

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from core.config import get_settings
from core.db import TradeRepository, EventRepository, get_db
from core.events import EventType, get_event_bus
from services.datafeed import DataFeedService

logger = logging.getLogger("nexus.monitor")


class MonitoringService:
    """
    监控告警服务
    
    职责:
    - 系统健康检查
    - 自动对账与纠偏
    - 告警通知
    - 指标收集
    """
    
    def __init__(self, datafeed: DataFeedService):
        self.datafeed = datafeed
        self.settings = get_settings()
        self._running = False
        self._health_task: Optional[asyncio.Task] = None
        self._reconciliation_task: Optional[asyncio.Task] = None
        
        # 健康状态缓存
        self._health_status: Dict[str, Any] = {}
        self._last_check: Dict[str, datetime] = {}
        
        # 熔断器状态
        self._circuit_breaker_active = False
        self._circuit_breaker_until: Optional[datetime] = None
    
    async def start(self) -> None:
        """启动监控服务"""
        if self._running:
            return
        
        self._running = True
        self._health_task = asyncio.create_task(self._health_check_loop())
        self._reconciliation_task = asyncio.create_task(self._reconciliation_loop())
        logger.info("MonitoringService started")
    
    async def stop(self) -> None:
        """停止监控服务"""
        self._running = False
        
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
        
        if self._reconciliation_task:
            self._reconciliation_task.cancel()
            try:
                await self._reconciliation_task
            except asyncio.CancelledError:
                pass
        
        logger.info("MonitoringService stopped")
    
    async def _health_check_loop(self) -> None:
        """健康检查循环"""
        interval = self.settings.monitoring.health_check_interval
        
        while self._running:
            try:
                await self._run_health_checks()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}", exc_info=True)
                await asyncio.sleep(30)
    
    async def _run_health_checks(self) -> None:
        """执行健康检查"""
        bus = await get_event_bus()
        
        checks = {
            "database": self._check_database(),
            "datafeed": self.datafeed.health_check(),
            "event_bus": self._check_event_bus(),
        }
        
        results = {}
        all_healthy = True
        
        for name, check_coro in checks.items():
            try:
                result = await check_coro
                results[name] = result
                if not self._is_healthy(result):
                    all_healthy = False
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}
                all_healthy = False
        
        self._health_status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall": "healthy" if all_healthy else "degraded",
            "components": results,
        }
        
        # 发布健康状态
        await bus.publish(EventType.SYSTEM_HEALTH, self._health_status)
        
        # 检查是否需要触发熔断
        if not all_healthy:
            await self._check_circuit_breaker(results)
    
    async def _check_database(self) -> Dict[str, Any]:
        """检查数据库连接"""
        try:
            db = await get_db()
            healthy = await db.health_check()
            return {"status": "healthy" if healthy else "unhealthy"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _check_event_bus(self) -> Dict[str, Any]:
        """检查事件总线"""
        try:
            bus = await get_event_bus()
            return {
                "status": "healthy" if bus.is_running else "unhealthy",
                "subscribers": bus.subscriber_count,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _is_healthy(self, result: Any) -> bool:
        """判断是否健康"""
        if isinstance(result, dict):
            return result.get("status") == "healthy"
        return bool(result)
    
    async def _check_circuit_breaker(self, results: Dict[str, Any]) -> None:
        """检查是否需要触发熔断"""
        bus = await get_event_bus()
        
        # 检查关键组件
        critical_failures = []
        for name, result in results.items():
            if name in ["database", "event_bus"] and not self._is_healthy(result):
                critical_failures.append(name)
        
        if critical_failures and not self._circuit_breaker_active:
            # 触发熔断
            self._circuit_breaker_active = True
            self._circuit_breaker_until = (
                datetime.now(timezone.utc) + timedelta(minutes=5)
            )
            
            await bus.publish(EventType.SYSTEM_PANIC, {
                "reason": "Critical components failed",
                "failed_components": critical_failures,
                "circuit_breaker_until": self._circuit_breaker_until.isoformat(),
            })
            
            logger.critical(f"Circuit breaker triggered: {critical_failures}")
    
    async def _reconciliation_loop(self) -> None:
        """自动对账循环"""
        interval = self.settings.monitoring.reconciliation_interval_minutes * 60
        
        while self._running:
            try:
                await asyncio.sleep(interval)
                await self._run_reconciliation()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Reconciliation error: {e}", exc_info=True)
                await asyncio.sleep(300)
    
    async def _run_reconciliation(self) -> None:
        """执行自动对账"""
        logger.info("Running reconciliation...")
        
        # 获取本地持仓
        local_trades = await TradeRepository.get_open()
        
        # 按交易所分组
        trades_by_exchange: Dict[str, List[Dict]] = {}
        for trade in local_trades:
            exchange = trade.get("exchange", "binance")
            if exchange not in trades_by_exchange:
                trades_by_exchange[exchange] = []
            trades_by_exchange[exchange].append(trade)
        
        # 检查每个交易所的持仓
        for exchange, trades in trades_by_exchange.items():
            try:
                await self._reconcile_exchange(exchange, trades)
            except Exception as e:
                logger.error(f"Reconciliation error for {exchange}: {e}")
    
    async def _reconcile_exchange(
        self,
        exchange: str,
        local_trades: List[Dict[str, Any]],
    ) -> None:
        """对账单个交易所"""
        bus = await get_event_bus()
        
        # 获取交易所持仓
        # 这里需要调用执行路由器获取持仓
        # 简化实现，实际需要从 ExecutionRouter 获取
        
        discrepancies = []
        
        for trade in local_trades:
            symbol = trade.get("symbol", "")
            # 检查交易所是否还有该持仓
            # 如果交易所已平仓但本地还是 open，需要纠正
            
            # 这里简化处理，实际需要查询交易所
            pass
        
        if discrepancies:
            await bus.publish(EventType.RISK_ALERT, {
                "alert_type": "reconciliation_discrepancy",
                "exchange": exchange,
                "discrepancies": discrepancies,
            })
    
    async def recover_from_circuit_breaker(self) -> None:
        """从熔断状态恢复"""
        if not self._circuit_breaker_active:
            return
        
        if self._circuit_breaker_until:
            if datetime.now(timezone.utc) < self._circuit_breaker_until:
                logger.warning("Circuit breaker still active")
                return
        
        self._circuit_breaker_active = False
        self._circuit_breaker_until = None
        
        bus = await get_event_bus()
        await bus.publish(EventType.SYSTEM_RECOVER, {
            "reason": "Circuit breaker timeout expired",
        })
        
        logger.info("Circuit breaker deactivated")
    
    async def get_health_status(self) -> Dict[str, Any]:
        """获取健康状态"""
        return {
            **self._health_status,
            "circuit_breaker": {
                "active": self._circuit_breaker_active,
                "until": self._circuit_breaker_until.isoformat() if self._circuit_breaker_until else None,
            },
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "running": self._running,
            "health_task": self._health_task is not None and not self._health_task.done(),
            "reconciliation_task": self._reconciliation_task is not None and not self._reconciliation_task.done(),
            "circuit_breaker_active": self._circuit_breaker_active,
        }
