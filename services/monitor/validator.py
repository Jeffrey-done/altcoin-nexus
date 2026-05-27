"""
事件闭环验证器
监控信号→风控→下单的完整链路延迟
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict

from core.events import EventType, get_event_bus

logger = logging.getLogger("nexus.event_validator")


@dataclass
class EventChain:
    """事件链"""
    signal_id: str
    symbol: str
    direction: str
    
    # 时间戳
    signal_generated: float = 0.0
    risk_check_start: float = 0.0
    risk_check_passed: float = 0.0
    order_placed: float = 0.0
    order_filled: float = 0.0
    
    # 状态
    status: str = "pending"  # pending / completed / failed / timeout
    
    # 延迟统计
    risk_check_latency_ms: float = 0.0
    execution_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    
    def is_complete(self) -> bool:
        return self.order_filled > 0
    
    def is_timeout(self, timeout_ms: float = 500) -> bool:
        if self.signal_generated == 0:
            return False
        elapsed = (time.time() - self.signal_generated) * 1000
        return elapsed > timeout_ms and not self.is_complete()


@dataclass
class ValidationResult:
    """验证结果"""
    timestamp: str
    total_chains: int
    completed_chains: int
    timeout_chains: int
    failed_chains: int
    
    # 延迟统计
    avg_risk_latency_ms: float
    avg_execution_latency_ms: float
    avg_total_latency_ms: float
    p95_total_latency_ms: float
    p99_total_latency_ms: float
    
    # 健康状态
    is_healthy: bool
    health_score: float  # 0-100
    
    def summary(self) -> str:
        lines = [
            "=" * 60,
            "  事件闭环验证报告",
            f"  时间: {self.timestamp}",
            "=" * 60,
            "",
            f"  事件链统计:",
            f"    总数: {self.total_chains}",
            f"    完成: {self.completed_chains}",
            f"    超时: {self.timeout_chains}",
            f"    失败: {self.failed_chains}",
            "",
            f"  延迟统计:",
            f"    风控检查: {self.avg_risk_latency_ms:.1f}ms",
            f"    订单执行: {self.avg_execution_latency_ms:.1f}ms",
            f"    总延迟: {self.avg_total_latency_ms:.1f}ms",
            f"    P95: {self.p95_total_latency_ms:.1f}ms",
            f"    P99: {self.p99_total_latency_ms:.1f}ms",
            "",
            f"  健康状态: {'✅ 健康' if self.is_healthy else '❌ 异常'}",
            f"  健康评分: {self.health_score:.0f}/100",
            "=" * 60,
        ]
        return "\n".join(lines)


class EventChainValidator:
    """
    事件闭环验证器
    
    监控信号→风控→下单的完整链路
    """
    
    def __init__(self, timeout_ms: float = 500):
        self.timeout_ms = timeout_ms
        self._chains: Dict[str, EventChain] = {}
        self._completed_chains: List[EventChain] = []
        self._running = False
        self._subscriptions: List[str] = []
        
        # 统计
        self._stats = {
            "total_signals": 0,
            "completed": 0,
            "timeout": 0,
            "failed": 0,
        }
    
    async def start(self) -> None:
        """启动验证器"""
        if self._running:
            return
        
        self._running = True
        await self._register_listeners()
        
        # 启动超时检查
        asyncio.create_task(self._timeout_checker())
        
        logger.info("EventChainValidator started")
    
    async def stop(self) -> None:
        """停止验证器"""
        self._running = False
        
        bus = await get_event_bus()
        for sub_id in self._subscriptions:
            await bus.unsubscribe(sub_id)
        
        logger.info("EventChainValidator stopped")
    
    async def _register_listeners(self) -> None:
        """注册事件监听"""
        bus = await get_event_bus()
        
        # 监听信号生成
        sub_id = await bus.subscribe(
            EventType.SIGNAL_TRIGGERED,
            self._on_signal_generated,
            "validator_signal"
        )
        self._subscriptions.append(sub_id)
        
        # 监听风控检查
        sub_id = await bus.subscribe(
            EventType.RISK_STATE_CHANGED,
            self._on_risk_check,
            "validator_risk"
        )
        self._subscriptions.append(sub_id)
        
        # 监听订单下单
        sub_id = await bus.subscribe(
            EventType.EXECUTION_ORDER_SENT,
            self._on_order_placed,
            "validator_order_sent"
        )
        self._subscriptions.append(sub_id)
        
        # 监听订单成交
        sub_id = await bus.subscribe(
            EventType.EXECUTION_ORDER_FILLED,
            self._on_order_filled,
            "validator_order_filled"
        )
        self._subscriptions.append(sub_id)
        
        # 监听订单失败
        sub_id = await bus.subscribe(
            EventType.EXECUTION_ORDER_FAILED,
            self._on_order_failed,
            "validator_order_failed"
        )
        self._subscriptions.append(sub_id)
    
    async def _on_signal_generated(self, event) -> None:
        """信号生成"""
        data = event.data
        signal_id = data.get("signal_id", event.event_id)
        symbol = data.get("symbol", "")
        direction = data.get("direction", "")
        
        self._chains[signal_id] = EventChain(
            signal_id=signal_id,
            symbol=symbol,
            direction=direction,
            signal_generated=time.time(),
        )
        
        self._stats["total_signals"] += 1
    
    async def _on_risk_check(self, event) -> None:
        """风控检查"""
        data = event.data
        signal_id = data.get("signal_id", "")
        
        chain = self._chains.get(signal_id)
        if chain:
            if chain.risk_check_start == 0:
                chain.risk_check_start = time.time()
            
            # 检查是否通过
            if not data.get("blocked", False):
                chain.risk_check_passed = time.time()
                chain.risk_check_latency_ms = (chain.risk_check_passed - chain.risk_check_start) * 1000
    
    async def _on_order_placed(self, event) -> None:
        """订单下单"""
        data = event.data
        signal_id = data.get("signal_id", "")
        
        chain = self._chains.get(signal_id)
        if chain:
            chain.order_placed = time.time()
    
    async def _on_order_filled(self, event) -> None:
        """订单成交"""
        data = event.data
        signal_id = data.get("signal_id", "")
        
        chain = self._chains.get(signal_id)
        if chain:
            chain.order_filled = time.time()
            chain.status = "completed"
            
            # 计算延迟
            chain.execution_latency_ms = (chain.order_filled - chain.order_placed) * 1000
            chain.total_latency_ms = (chain.order_filled - chain.signal_generated) * 1000
            
            self._stats["completed"] += 1
            self._completed_chains.append(chain)
            
            # 检查是否超时
            if chain.total_latency_ms > self.timeout_ms:
                logger.warning(
                    f"Event chain TIMEOUT: {chain.symbol} {chain.direction} "
                    f"total={chain.total_latency_ms:.1f}ms"
                )
    
    async def _on_order_failed(self, event) -> None:
        """订单失败"""
        data = event.data
        signal_id = data.get("signal_id", "")
        
        chain = self._chains.get(signal_id)
        if chain:
            chain.status = "failed"
            self._stats["failed"] += 1
    
    async def _timeout_checker(self) -> None:
        """超时检查"""
        while self._running:
            try:
                await asyncio.sleep(1)
                
                timeout_chains = []
                for signal_id, chain in self._chains.items():
                    if chain.is_timeout(self.timeout_ms) and chain.status == "pending":
                        chain.status = "timeout"
                        timeout_chains.append(chain)
                        self._stats["timeout"] += 1
                
                if timeout_chains:
                    logger.warning(f"Event chain timeouts: {len(timeout_chains)}")
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Timeout checker error: {e}")
    
    def validate(self) -> ValidationResult:
        """执行验证"""
        import numpy as np
        
        # 获取最近的完成链
        recent_chains = self._completed_chains[-100:]
        
        if not recent_chains:
            return ValidationResult(
                timestamp=datetime.now(timezone.utc).isoformat(),
                total_chains=self._stats["total_signals"],
                completed_chains=0,
                timeout_chains=self._stats["timeout"],
                failed_chains=self._stats["failed"],
                avg_risk_latency_ms=0,
                avg_execution_latency_ms=0,
                avg_total_latency_ms=0,
                p95_total_latency_ms=0,
                p99_total_latency_ms=0,
                is_healthy=True,
                health_score=100,
            )
        
        # 计算延迟统计
        risk_latencies = [c.risk_check_latency_ms for c in recent_chains if c.risk_check_latency_ms > 0]
        exec_latencies = [c.execution_latency_ms for c in recent_chains if c.execution_latency_ms > 0]
        total_latencies = [c.total_latency_ms for c in recent_chains if c.total_latency_ms > 0]
        
        avg_risk = np.mean(risk_latencies) if risk_latencies else 0
        avg_exec = np.mean(exec_latencies) if exec_latencies else 0
        avg_total = np.mean(total_latencies) if total_latencies else 0
        p95_total = np.percentile(total_latencies, 95) if total_latencies else 0
        p99_total = np.percentile(total_latencies, 99) if total_latencies else 0
        
        # 计算健康评分
        timeout_rate = self._stats["timeout"] / max(self._stats["total_signals"], 1)
        completion_rate = self._stats["completed"] / max(self._stats["total_signals"], 1)
        
        health_score = 100
        health_score -= timeout_rate * 50  # 超时扣分
        health_score -= (1 - completion_rate) * 30  # 未完成扣分
        if avg_total > self.timeout_ms:
            health_score -= 20  # 平均延迟过高扣分
        
        health_score = max(health_score, 0)
        
        is_healthy = health_score >= 70 and timeout_rate < 0.1
        
        return ValidationResult(
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_chains=self._stats["total_signals"],
            completed_chains=self._stats["completed"],
            timeout_chains=self._stats["timeout"],
            failed_chains=self._stats["failed"],
            avg_risk_latency_ms=avg_risk,
            avg_execution_latency_ms=avg_exec,
            avg_total_latency_ms=avg_total,
            p95_total_latency_ms=p95_total,
            p99_total_latency_ms=p99_total,
            is_healthy=is_healthy,
            health_score=health_score,
        )


# 全局单例
_validator: Optional[EventChainValidator] = None


async def get_validator() -> EventChainValidator:
    """获取全局验证器"""
    global _validator
    if _validator is None:
        _validator = EventChainValidator()
        await _validator.start()
    return _validator
