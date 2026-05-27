"""
系统自愈模块
自动对账 + 异常熔断
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass

from core.config import get_settings
from core.db import TradeRepository, EventRepository, get_db
from core.events import EventType, get_event_bus

logger = logging.getLogger("nexus.healing")


class CircuitState(str, Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常
    OPEN = "open"          # 熔断
    HALF_OPEN = "half_open"  # 半开（试探）


@dataclass
class CircuitBreaker:
    """熔断器"""
    exchange: str
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure: Optional[datetime] = None
    open_until: Optional[datetime] = None
    
    # 配置
    failure_threshold: int = 5
    recovery_timeout: int = 300  # 5分钟


class SelfHealingService:
    """
    系统自愈服务
    
    功能：
    1. 自动对账 - 定期对比数据库和交易所持仓
    2. 异常熔断 - 交易所异常时自动熔断
    3. 自动恢复 - 尝试自动恢复连接
    """
    
    def __init__(self, execution_router=None):
        self.settings = get_settings()
        self.execution_router = execution_router
        self._running = False
        
        # 任务
        self._reconciliation_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None
        
        # 熔断器
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # 对账统计
        self._reconciliation_stats = {
            "total_checks": 0,
            "discrepancies_found": 0,
            "auto_corrections": 0,
            "last_check": None,
        }
    
    async def start(self) -> None:
        """启动自愈服务"""
        if self._running:
            return
        
        self._running = True
        
        # 启动自动对账
        self._reconciliation_task = asyncio.create_task(self._reconciliation_loop())
        
        # 启动健康检查
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        
        logger.info("SelfHealingService started")
    
    async def stop(self) -> None:
        """停止自愈服务"""
        self._running = False
        
        for task in [self._reconciliation_task, self._health_check_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        logger.info("SelfHealingService stopped")
    
    # ==================== 自动对账 ====================
    
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
    
    async def _run_reconciliation(self) -> Dict[str, Any]:
        """执行自动对账"""
        logger.info("Running reconciliation...")
        
        self._reconciliation_stats["total_checks"] += 1
        self._reconciliation_stats["last_check"] = datetime.now(timezone.utc).isoformat()
        
        bus = await get_event_bus()
        discrepancies = []
        
        # 获取本地持仓
        local_trades = await TradeRepository.get_open()
        
        # 按交易所分组
        trades_by_exchange: Dict[str, List[Dict]] = {}
        for trade in local_trades:
            exchange = trade.get("exchange", "binance")
            if exchange not in trades_by_exchange:
                trades_by_exchange[exchange] = []
            trades_by_exchange[exchange].append(trade)
        
        # 检查每个交易所
        for exchange, trades in trades_by_exchange.items():
            if not self.execution_router:
                continue
            
            # 跳过熔断的交易所
            if self._is_circuit_open(exchange):
                logger.warning(f"Skipping reconciliation for {exchange} (circuit open)")
                continue
            
            try:
                # 获取交易所持仓
                exchange_positions = await self._get_exchange_positions(exchange)
                
                # 对比
                disc = await self._compare_positions(exchange, trades, exchange_positions)
                discrepancies.extend(disc)
            
            except Exception as e:
                logger.error(f"Reconciliation error for {exchange}: {e}")
                self._record_failure(exchange)
        
        # 处理差异
        if discrepancies:
            self._reconciliation_stats["discrepancies_found"] += len(discrepancies)
            
            # 发布告警
            await bus.publish(EventType.RISK_ALERT, {
                "alert_type": "reconciliation_discrepancy",
                "discrepancies": discrepancies,
            })
            
            # 尝试自动纠正
            await self._auto_correct(discrepancies)
        
        logger.info(f"Reconciliation completed: {len(discrepancies)} discrepancies found")
        
        return {
            "discrepancies": discrepancies,
            "stats": self._reconciliation_stats,
        }
    
    async def _get_exchange_positions(self, exchange: str) -> List[Dict[str, Any]]:
        """
        获取交易所真实持仓
        
        通过 ExecutionRouter 调用交易所 API 获取当前持仓
        """
        if not self.execution_router:
            logger.error("execution_router not available, cannot get positions")
            raise RuntimeError("execution_router not available")
        
        try:
            ex = self.execution_router._exchanges.get(exchange)
            if not ex:
                logger.warning(f"Exchange {exchange} not connected")
                return []
            
            # 调用交易所 API 获取持仓
            raw_positions = await ex.fetch_positions()
            
            positions = []
            for pos in raw_positions:
                contracts = float(pos.get("contracts", 0))
                if contracts != 0:
                    positions.append({
                        "symbol": pos["symbol"],
                        "direction": "LONG" if pos.get("side") == "long" else "SHORT",
                        "amount": abs(contracts),
                        "entry_price": float(pos.get("entryPrice", 0)),
                        "unrealized_pnl": float(pos.get("unrealizedPnl", 0)),
                        "leverage": int(pos.get("leverage", 1)),
                        "exchange": exchange,
                    })
            
            return positions
        
        except Exception as e:
            logger.error(f"Failed to get positions from {exchange}: {e}")
            raise
    
    async def _compare_positions(
        self,
        exchange: str,
        local_trades: List[Dict[str, Any]],
        exchange_positions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        对比持仓 - 发布 POSITION_MISMATCH 事件
        """
        bus = await get_event_bus()
        discrepancies = []
        
        # 本地持仓的 symbol 集合
        local_symbols = {t.get("symbol") for t in local_trades}
        
        # 交易所持仓的 symbol 集合
        exchange_symbols = {p.get("symbol") for p in exchange_positions}
        
        # 检查：本地有但交易所没有（可能已手动平仓）
        for trade in local_trades:
            symbol = trade.get("symbol")
            if symbol not in exchange_symbols:
                discrepancies.append({
                    "type": "local_only",
                    "exchange": exchange,
                    "symbol": symbol,
                    "trade_id": trade.get("id"),
                    "action": "close_local",
                })
                # 发布持仓不一致事件
                await bus.publish(EventType.POSITION_MISMATCH, {
                    "type": "local_only",
                    "exchange": exchange,
                    "symbol": symbol,
                    "trade_id": trade.get("id"),
                    "local_direction": trade.get("direction"),
                    "local_amount": trade.get("shares", 0),
                    "message": f"Local has {symbol} but exchange doesn't",
                })
        
        # 检查：交易所有但本地没有（需要调查）
        for pos in exchange_positions:
            symbol = pos.get("symbol")
            if symbol not in local_symbols:
                discrepancies.append({
                    "type": "exchange_only",
                    "exchange": exchange,
                    "symbol": symbol,
                    "position": pos,
                    "action": "investigate",
                })
                # 发布持仓不一致事件
                await bus.publish(EventType.POSITION_MISMATCH, {
                    "type": "exchange_only",
                    "exchange": exchange,
                    "symbol": symbol,
                    "exchange_direction": pos.get("direction"),
                    "exchange_amount": pos.get("amount", 0),
                    "message": f"Exchange has {symbol} but local doesn't",
                })
        
        return discrepancies
    
    async def _auto_correct(self, discrepancies: List[Dict[str, Any]]) -> None:
        """自动纠正"""
        bus = await get_event_bus()
        
        for disc in discrepancies:
            if disc["action"] == "close_local":
                # 自动关闭本地持仓
                trade_id = disc.get("trade_id")
                if trade_id:
                    try:
                        await TradeRepository.close_trade(
                            trade_id=trade_id,
                            pnl=0,
                            close_price=0,
                            close_reason="Auto-closed by reconciliation",
                            close_type="reconciliation",
                        )
                        self._reconciliation_stats["auto_corrections"] += 1
                        logger.info(f"Auto-closed trade {trade_id} by reconciliation")
                    except Exception as e:
                        logger.error(f"Failed to auto-close trade {trade_id}: {e}")
    
    # ==================== 熔断器 ====================
    
    async def _health_check_loop(self) -> None:
        """健康检查循环"""
        while self._running:
            try:
                await self._check_exchange_health()
                await asyncio.sleep(60)  # 每分钟检查
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(30)
    
    async def _check_exchange_health(self) -> None:
        """检查交易所健康状态"""
        if not self.execution_router:
            return
        
        for exchange in self._circuit_breakers:
            breaker = self._circuit_breakers[exchange]
            
            # 检查是否应该恢复
            if breaker.state == CircuitState.OPEN:
                if breaker.open_until and datetime.now(timezone.utc) > breaker.open_until:
                    breaker.state = CircuitState.HALF_OPEN
                    logger.info(f"Circuit breaker {exchange} -> HALF_OPEN")
            
            # 半开状态：尝试恢复
            if breaker.state == CircuitState.HALF_OPEN:
                try:
                    health = await self.execution_router.health_check()
                    if health.get("exchanges", {}).get(exchange) == "connected":
                        breaker.state = CircuitState.CLOSED
                        breaker.failure_count = 0
                        logger.info(f"Circuit breaker {exchange} -> CLOSED (recovered)")
                        
                        bus = await get_event_bus()
                        await bus.publish(EventType.SYSTEM_RECOVER, {
                            "exchange": exchange,
                            "reason": "Health check passed",
                        })
                except Exception:
                    pass
    
    def _record_failure(self, exchange: str) -> None:
        """记录失败"""
        if exchange not in self._circuit_breakers:
            self._circuit_breakers[exchange] = CircuitBreaker(exchange=exchange)
        
        breaker = self._circuit_breakers[exchange]
        breaker.failure_count += 1
        breaker.last_failure = datetime.now(timezone.utc)
        
        # 检查是否需要熔断
        if breaker.failure_count >= breaker.failure_threshold:
            breaker.state = CircuitState.OPEN
            breaker.open_until = datetime.now(timezone.utc) + timedelta(seconds=breaker.recovery_timeout)
            logger.warning(f"Circuit breaker {exchange} -> OPEN (failures: {breaker.failure_count})")
    
    def _is_circuit_open(self, exchange: str) -> bool:
        """检查熔断器是否打开"""
        breaker = self._circuit_breakers.get(exchange)
        if not breaker:
            return False
        
        if breaker.state == CircuitState.OPEN:
            # 检查是否已过期
            if breaker.open_until and datetime.now(timezone.utc) > breaker.open_until:
                breaker.state = CircuitState.HALF_OPEN
                return False
            return True
        
        return False
    
    def get_circuit_breakers(self) -> Dict[str, Dict[str, Any]]:
        """获取熔断器状态"""
        return {
            exchange: {
                "state": breaker.state.value,
                "failure_count": breaker.failure_count,
                "last_failure": breaker.last_failure.isoformat() if breaker.last_failure else None,
                "open_until": breaker.open_until.isoformat() if breaker.open_until else None,
            }
            for exchange, breaker in self._circuit_breakers.items()
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "running": self._running,
            "reconciliation_task": self._reconciliation_task is not None and not self._reconciliation_task.done(),
            "health_check_task": self._health_check_task is not None and not self._health_check_task.done(),
            "circuit_breakers": self.get_circuit_breakers(),
            "stats": self._reconciliation_stats,
        }


# 全局单例
_healing_service: Optional[SelfHealingService] = None


def get_healing_service(execution_router=None) -> SelfHealingService:
    """获取全局自愈服务实例"""
    global _healing_service
    if _healing_service is None:
        _healing_service = SelfHealingService(execution_router)
    return _healing_service
