"""
智能订单执行器
TWAP / VWAP / Iceberg 算法单
"""

import asyncio
import logging
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger("nexus.smart_order")


class OrderAlgo(str, Enum):
    """订单算法"""
    MARKET = "market"        # 市价单
    TWAP = "twap"            # 时间加权
    VWAP = "vwap"            # 成交量加权
    ICEBERG = "iceberg"      # 冰山单


@dataclass
class SmartOrderConfig:
    """智能订单配置"""
    algo: OrderAlgo = OrderAlgo.MARKET
    
    # TWAP 参数
    twap_intervals: int = 5          # 分割份数
    twap_interval_sec: int = 10      # 每份间隔（秒）
    
    # VWAP 参数
    vwap_participation_rate: float = 0.1  # 参与率 (10%)
    vwap_max_duration_sec: int = 300      # 最大持续时间
    
    # Iceberg 参数
    iceberg_display_size: float = 0.1     # 显示比例 (10%)
    iceberg_variance: float = 0.2         # 数量随机波动
    
    # 通用参数
    max_slippage_pct: float = 1.0         # 最大滑点
    timeout_sec: int = 600                # 超时时间


@dataclass
class SmartOrderResult:
    """智能订单结果"""
    order_id: str
    algo: OrderAlgo
    status: str  # filled / partial / failed / timeout
    
    # 成交详情
    filled_amount: float = 0.0
    avg_price: float = 0.0
    total_cost: float = 0.0
    
    # 滑点
    expected_price: float = 0.0
    slippage_pct: float = 0.0
    
    # 子单统计
    child_orders: int = 0
    filled_orders: int = 0
    
    # 时间
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_sec: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "algo": self.algo.value,
            "status": self.status,
            "filled_amount": self.filled_amount,
            "avg_price": self.avg_price,
            "slippage_pct": self.slippage_pct,
            "child_orders": self.child_orders,
            "filled_orders": self.filled_orders,
            "duration_sec": self.duration_sec,
        }


class SmartOrderEngine:
    """
    智能订单引擎
    
    根据订单大小和市场条件，自动选择最优执行算法：
    - 小单: 直接市价
    - 中单: TWAP
    - 大单: VWAP
    - 超大单: Iceberg
    """
    
    def __init__(self, exchange=None):
        self.exchange = exchange
        
        # 阈值配置
        self._thresholds = {
            "small_order": 1000,      # 小单阈值 (USDT)
            "medium_order": 10000,    # 中单阈值
            "large_order": 50000,     # 大单阈值
        }
    
    async def execute(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        algo: Optional[OrderAlgo] = None,
        config: Optional[SmartOrderConfig] = None,
    ) -> SmartOrderResult:
        """
        执行智能订单
        
        Args:
            symbol: 交易对
            side: 方向 (buy/sell)
            amount: 数量
            price: 参考价格
            algo: 指定算法 (None=自动选择)
            config: 算法配置
        
        Returns:
            执行结果
        """
        order_id = f"smart_{uuid.uuid4().hex[:12]}"
        start_time = datetime.now(timezone.utc)
        
        # 计算订单金额
        notional = amount * price
        
        # 自动选择算法
        if algo is None:
            algo = self._select_algo(notional)
        
        config = config or SmartOrderConfig(algo=algo)
        
        logger.info(f"SmartOrder {order_id}: {algo.value} {side} {amount} {symbol} @ {price}")
        
        try:
            if algo == OrderAlgo.MARKET:
                result = await self._execute_market(order_id, symbol, side, amount, price)
            elif algo == OrderAlgo.TWAP:
                result = await self._execute_twap(order_id, symbol, side, amount, price, config)
            elif algo == OrderAlgo.VWAP:
                result = await self._execute_vwap(order_id, symbol, side, amount, price, config)
            elif algo == OrderAlgo.ICEBERG:
                result = await self._execute_iceberg(order_id, symbol, side, amount, price, config)
            else:
                result = SmartOrderResult(order_id=order_id, algo=algo, status="failed")
        
        except Exception as e:
            logger.error(f"SmartOrder {order_id} failed: {e}")
            result = SmartOrderResult(
                order_id=order_id,
                algo=algo,
                status="failed",
            )
        
        result.start_time = start_time
        result.end_time = datetime.now(timezone.utc)
        result.duration_sec = (result.end_time - start_time).total_seconds()
        result.expected_price = price
        
        if result.avg_price > 0:
            result.slippage_pct = abs(result.avg_price - price) / price * 100
        
        logger.info(f"SmartOrder {order_id} completed: {result.status} slippage={result.slippage_pct:.3f}%")
        
        return result
    
    def _select_algo(self, notional: float) -> OrderAlgo:
        """自动选择算法"""
        if notional < self._thresholds["small_order"]:
            return OrderAlgo.MARKET
        elif notional < self._thresholds["medium_order"]:
            return OrderAlgo.TWAP
        elif notional < self._thresholds["large_order"]:
            return OrderAlgo.VWAP
        else:
            return OrderAlgo.ICEBERG
    
    async def _execute_market(
        self,
        order_id: str,
        symbol: str,
        side: str,
        amount: float,
        price: float,
    ) -> SmartOrderResult:
        """市价单执行"""
        if not self.exchange:
            return SmartOrderResult(order_id=order_id, algo=OrderAlgo.MARKET, status="no_exchange")
        
        try:
            order = await self.exchange.create_order(
                symbol=symbol,
                type="market",
                side=side,
                amount=amount,
            )
            
            return SmartOrderResult(
                order_id=order_id,
                algo=OrderAlgo.MARKET,
                status="filled",
                filled_amount=order.get("filled", amount),
                avg_price=order.get("average", order.get("price", price)),
                child_orders=1,
                filled_orders=1,
            )
        
        except Exception as e:
            logger.error(f"Market order failed: {e}")
            return SmartOrderResult(order_id=order_id, algo=OrderAlgo.MARKET, status="failed")
    
    async def _execute_twap(
        self,
        order_id: str,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        config: SmartOrderConfig,
    ) -> SmartOrderResult:
        """
        TWAP 执行
        
        将订单分成 N 份，每间隔一段时间执行一份
        """
        intervals = config.twap_intervals
        interval_sec = config.twap_interval_sec
        chunk_size = amount / intervals
        
        filled_amount = 0.0
        total_cost = 0.0
        filled_orders = 0
        
        for i in range(intervals):
            try:
                # 最后一份用剩余数量
                if i == intervals - 1:
                    chunk = amount - filled_amount
                else:
                    chunk = chunk_size
                
                if self.exchange:
                    order = await self.exchange.create_order(
                        symbol=symbol,
                        type="market",
                        side=side,
                        amount=chunk,
                    )
                    
                    fill_price = order.get("average", order.get("price", price))
                    fill_amount = order.get("filled", chunk)
                    
                    filled_amount += fill_amount
                    total_cost += fill_amount * fill_price
                    filled_orders += 1
                
                # 等待间隔
                if i < intervals - 1:
                    await asyncio.sleep(interval_sec)
            
            except Exception as e:
                logger.warning(f"TWAP chunk {i+1}/{intervals} failed: {e}")
                continue
        
        avg_price = total_cost / filled_amount if filled_amount > 0 else price
        
        return SmartOrderResult(
            order_id=order_id,
            algo=OrderAlgo.TWAP,
            status="filled" if filled_amount >= amount * 0.99 else "partial",
            filled_amount=filled_amount,
            avg_price=avg_price,
            total_cost=total_cost,
            child_orders=intervals,
            filled_orders=filled_orders,
        )
    
    async def _execute_vwap(
        self,
        order_id: str,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        config: SmartOrderConfig,
    ) -> SmartOrderResult:
        """
        VWAP 执行
        
        根据市场成交量动态调整执行速度
        """
        max_duration = config.vwap_max_duration_sec
        participation_rate = config.vwap_participation_rate
        
        filled_amount = 0.0
        total_cost = 0.0
        filled_orders = 0
        start_time = datetime.now(timezone.utc)
        
        while filled_amount < amount * 0.99:
            # 检查超时
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            if elapsed > max_duration:
                break
            
            try:
                # 获取当前成交量
                if self.exchange:
                    ticker = await self.exchange.fetch_ticker(symbol)
                    vol_1m = ticker.get("baseVolume", 0) / 60  # 每分钟成交量
                    
                    # 计算本次执行量
                    target_amount = vol_1m * participation_rate
                    remaining = amount - filled_amount
                    chunk = min(target_amount, remaining)
                    
                    if chunk > 0:
                        order = await self.exchange.create_order(
                            symbol=symbol,
                            type="market",
                            side=side,
                            amount=chunk,
                        )
                        
                        fill_price = order.get("average", order.get("price", price))
                        fill_amount = order.get("filled", chunk)
                        
                        filled_amount += fill_amount
                        total_cost += fill_amount * fill_price
                        filled_orders += 1
                
                await asyncio.sleep(5)  # 每 5 秒检查一次
            
            except Exception as e:
                logger.warning(f"VWAP execution error: {e}")
                await asyncio.sleep(10)
        
        avg_price = total_cost / filled_amount if filled_amount > 0 else price
        
        return SmartOrderResult(
            order_id=order_id,
            algo=OrderAlgo.VWAP,
            status="filled" if filled_amount >= amount * 0.99 else "partial",
            filled_amount=filled_amount,
            avg_price=avg_price,
            total_cost=total_cost,
            child_orders=filled_orders,
            filled_orders=filled_orders,
        )
    
    async def _execute_iceberg(
        self,
        order_id: str,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        config: SmartOrderConfig,
    ) -> SmartOrderResult:
        """
        Iceberg 执行
        
        只显示一小部分订单，成交后再挂下一批
        """
        display_ratio = config.iceberg_display_size
        variance = config.iceberg_variance
        
        filled_amount = 0.0
        total_cost = 0.0
        filled_orders = 0
        
        import random
        
        while filled_amount < amount * 0.99:
            try:
                # 计算本次显示量（带随机波动）
                remaining = amount - filled_amount
                base_display = amount * display_ratio
                display_amount = base_display * (1 + random.uniform(-variance, variance))
                display_amount = min(display_amount, remaining)
                
                if display_amount <= 0:
                    break
                
                if self.exchange:
                    # 使用限价单
                    order = await self.exchange.create_order(
                        symbol=symbol,
                        type="limit",
                        side=side,
                        amount=display_amount,
                        price=price,
                    )
                    
                    # 等待成交
                    await asyncio.sleep(2)
                    
                    # 检查订单状态
                    order_id_exchange = order.get("id")
                    if order_id_exchange:
                        order_status = await self.exchange.fetch_order(order_id_exchange, symbol)
                        
                        if order_status.get("status") == "closed":
                            fill_price = order_status.get("average", price)
                            fill_amount = order_status.get("filled", display_amount)
                            
                            filled_amount += fill_amount
                            total_cost += fill_amount * fill_price
                            filled_orders += 1
                        else:
                            # 取消未成交订单
                            await self.exchange.cancel_order(order_id_exchange, symbol)
            
            except Exception as e:
                logger.warning(f"Iceberg execution error: {e}")
                await asyncio.sleep(5)
        
        avg_price = total_cost / filled_amount if filled_amount > 0 else price
        
        return SmartOrderResult(
            order_id=order_id,
            algo=OrderAlgo.ICEBERG,
            status="filled" if filled_amount >= amount * 0.99 else "partial",
            filled_amount=filled_amount,
            avg_price=avg_price,
            total_cost=total_cost,
            child_orders=filled_orders,
            filled_orders=filled_orders,
        )
