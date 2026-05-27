"""
统一执行路由器
整合 WS 下单、Smart Order 和 REST API
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import ccxt.async_support as ccxt

from core.config import get_settings
from core.db import EventRepository, TradeRepository, get_db
from core.events import EventType, get_event_bus

logger = logging.getLogger("nexus.execution")


class OrderType(str, Enum):
    """订单类型"""
    MARKET = "market"
    LIMIT = "limit"
    STOP_MARKET = "stop_market"
    TAKE_PROFIT_MARKET = "take_profit_market"


class OrderPriority(str, Enum):
    """订单优先级"""
    URGENT = "urgent"      # 紧急（硬止损、移动止损）
    NORMAL = "normal"      # 普通（开仓、止盈）
    LOW = "low"            # 低优先级


class ExecutionRouter:
    """
    统一执行路由器
    
    根据订单属性自动路由:
    - 紧急订单 -> WS 直连（低延迟）
    - 普通订单 -> Smart Order（TWAP/VWAP）
    - REST API 备用
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._exchanges: Dict[str, ccxt.Exchange] = {}
        self._running = False
        self._pending_orders: Dict[str, Dict[str, Any]] = {}
        self._subscriptions: List[str] = []
        
        # 统计
        self._stats = {
            "total_orders": 0,
            "successful_orders": 0,
            "failed_orders": 0,
            "total_slippage_pct": 0.0,
        }
    
    async def start(self) -> None:
        """启动执行路由器"""
        if self._running:
            return
        
        self._running = True
        await self._init_exchanges()
        
        # 注册事件监听
        await self._register_event_listeners()
        
        logger.info("ExecutionRouter started")
    
    async def stop(self) -> None:
        """停止执行路由器"""
        self._running = False
        
        # 取消事件订阅
        bus = await get_event_bus()
        for sub_id in self._subscriptions:
            await bus.unsubscribe(sub_id)
        self._subscriptions.clear()
        
        for name, exchange in self._exchanges.items():
            try:
                await exchange.close()
            except Exception:
                pass
        
        self._exchanges.clear()
        logger.info("ExecutionRouter stopped")
    
    async def _register_event_listeners(self) -> None:
        """注册事件监听"""
        bus = await get_event_bus()
        
        # 监听系统恐慌事件 - 紧急全平仓
        sub_id = await bus.subscribe(
            EventType.SYSTEM_PANIC,
            self._on_system_panic,
            "execution_panic"
        )
        self._subscriptions.append(sub_id)
        
        logger.info("ExecutionRouter event listeners registered")
    
    async def _on_system_panic(self, event) -> None:
        """处理系统恐慌事件 - 紧急全平仓"""
        data = event.data
        reason = data.get("reason", "Unknown")
        action = data.get("action", "")
        
        logger.critical(f"SYSTEM PANIC received: {reason} action={action}")
        
        if action == "close_all":
            # 获取所有持仓并平仓
            from core.db import TradeRepository
            open_trades = await TradeRepository.get_open()
            
            closed_count = 0
            for trade in open_trades:
                try:
                    symbol = trade.get("symbol", "")
                    direction = trade.get("direction", "")
                    amount = trade.get("shares", 0)
                    exchange = trade.get("exchange", "binance")
                    
                    if amount > 0:
                        result = await self.execute_close(
                            symbol=symbol,
                            direction=direction,
                            amount=amount,
                            exchange=exchange,
                            reason=f"PANIC: {reason}",
                            priority=OrderPriority.URGENT,
                        )
                        if result:
                            closed_count += 1
                            logger.info(f"PANIC closed: {symbol} {direction}")
                except Exception as e:
                    logger.error(f"PANIC close failed for {trade.get('symbol')}: {e}")
            
            logger.critical(f"PANIC completed: {closed_count}/{len(open_trades)} positions closed")
    
    async def _init_exchanges(self) -> None:
        """初始化交易所连接"""
        config = self.settings.exchange
        
        # Binance
        if config.binance_api_key:
            try:
                self._exchanges["binance"] = ccxt.binance({
                    "apiKey": config.binance_api_key,
                    "secret": config.binance_api_secret,
                    "enableRateLimit": True,
                    "options": {
                        "defaultType": "future",
                        "adjustForTimeDifference": True,
                    },
                })
                logger.info("Binance execution connection initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Binance: {e}")
        
        # OKX
        if config.okx_api_key:
            try:
                self._exchanges["okx"] = ccxt.okx({
                    "apiKey": config.okx_api_key,
                    "secret": config.okx_api_secret,
                    "password": config.okx_passphrase,
                    "enableRateLimit": True,
                })
                logger.info("OKX execution connection initialized")
            except Exception as e:
                logger.error(f"Failed to initialize OKX: {e}")
        
        # Bybit
        if config.bybit_api_key:
            try:
                self._exchanges["bybit"] = ccxt.bybit({
                    "apiKey": config.bybit_api_key,
                    "secret": config.bybit_api_secret,
                    "enableRateLimit": True,
                    "options": {
                        "defaultType": "linear",
                        "adjustForTimeDifference": True,
                    },
                })
                logger.info("Bybit execution connection initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Bybit: {e}")
        
        # Gate.io
        if config.gate_api_key:
            try:
                self._exchanges["gate"] = ccxt.gate({
                    "apiKey": config.gate_api_key,
                    "secret": config.gate_api_secret,
                    "enableRateLimit": True,
                    "options": {
                        "defaultType": "future",
                        "adjustForTimeDifference": True,
                    },
                })
                logger.info("Gate.io execution connection initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Gate.io: {e}")
        
        # Bitget
        if config.bitget_api_key:
            try:
                self._exchanges["bitget"] = ccxt.bitget({
                    "apiKey": config.bitget_api_key,
                    "secret": config.bitget_api_secret,
                    "password": config.bitget_passphrase,
                    "enableRateLimit": True,
                    "options": {
                        "defaultType": "future",
                        "adjustForTimeDifference": True,
                    },
                })
                logger.info("Bitget execution connection initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Bitget: {e}")
    
    async def execute_open(
        self,
        symbol: str,
        direction: str,
        stake: float,
        leverage: int,
        exchange: str = "binance",
        strategy: str = "short_overbought",
        account_id: str = "",
        priority: OrderPriority = OrderPriority.NORMAL,
    ) -> Optional[Dict[str, Any]]:
        """
        执行开仓
        
        Args:
            symbol: 交易对
            direction: 方向 (SHORT/LONG)
            stake: 保证金
            leverage: 杠杆
            exchange: 交易所
            strategy: 策略名称
            account_id: 账户ID
            priority: 订单优先级
        
        Returns:
            订单信息或None
        """
        if not self._running:
            logger.error("ExecutionRouter not running")
            return None
        
        client_order_id = f"nexus_{uuid.uuid4().hex[:16]}"
        
        try:
            # 记录下单意图
            await EventRepository.log(
                "order_intent",
                symbol=symbol,
                direction=direction,
                stake=stake,
                leverage=leverage,
                exchange=exchange,
                account_id=account_id,
                client_order_id=client_order_id,
            )
            
            # 获取交易所连接
            ex = self._exchanges.get(exchange)
            if not ex:
                raise ValueError(f"Exchange {exchange} not available")
            
            # 设置杠杆
            try:
                await ex.set_leverage(leverage, symbol)
            except Exception as e:
                logger.warning(f"Failed to set leverage: {e}")
            
            # 设置保证金模式
            try:
                await ex.set_margin_mode("isolated", symbol)
            except Exception as e:
                logger.warning(f"Failed to set margin mode: {e}")
            
            # 计算下单数量
            ticker = await ex.fetch_ticker(symbol)
            price = ticker["last"]
            amount = (stake * leverage) / price
            
            # 发布订单发送事件 (P0-3: 补齐 EXECUTION_ORDER_SENT)
            bus = await get_event_bus()
            await bus.publish(EventType.EXECUTION_ORDER_SENT, {
                "symbol": symbol,
                "direction": direction,
                "stake": stake,
                "leverage": leverage,
                "exchange": exchange,
                "account_id": account_id,
                "client_order_id": client_order_id,
                "amount": amount,
                "price": price,
            })
            
            # 执行下单
            side = "sell" if direction == "SHORT" else "buy"
            order = await ex.create_order(
                symbol=symbol,
                type="market",
                side=side,
                amount=amount,
                params={"clientOrderId": client_order_id},
            )
            
            # 计算滑点
            fill_price = order.get("average", order.get("price", 0))
            slippage_pct = abs(fill_price - price) / price * 100 if price > 0 else 0
            
            # 记录执行事件
            await EventRepository.log(
                "order_filled",
                symbol=symbol,
                direction=direction,
                stake=stake,
                leverage=leverage,
                exchange=exchange,
                account_id=account_id,
                client_order_id=client_order_id,
                order_id=order.get("id", ""),
                fill_price=fill_price,
                fill_amount=order.get("filled", 0),
            )
            
            # 更新统计
            self._stats["total_orders"] += 1
            self._stats["successful_orders"] += 1
            self._stats["total_slippage_pct"] += slippage_pct
            
            # 发布订单成交事件
            await bus.publish(EventType.EXECUTION_ORDER_FILLED, {
                "symbol": symbol,
                "direction": direction,
                "order_id": order.get("id", ""),
                "fill_price": fill_price,
                "slippage_pct": slippage_pct,
                "account_id": account_id,
                "client_order_id": client_order_id,
            })
            
            # 发布开仓事件 (P0-2: 补齐 TRADE_OPENED)
            trade_id = f"trade_{uuid.uuid4().hex[:12]}"
            await bus.publish(EventType.TRADE_OPENED, {
                "trade_id": trade_id,
                "symbol": symbol,
                "direction": direction,
                "stake": stake,
                "leverage": leverage,
                "entry_price": fill_price,
                "exchange": exchange,
                "account_id": account_id,
                "strategy": strategy,
                "order_id": order.get("id", ""),
                "client_order_id": client_order_id,
            })
            
            logger.info(
                f"Order filled: {symbol} {direction} "
                f"price={fill_price} slippage={slippage_pct:.3f}%"
            )
            
            return {
                "order_id": order.get("id", ""),
                "client_order_id": client_order_id,
                "fill_price": fill_price,
                "fill_amount": order.get("filled", 0),
                "slippage_pct": slippage_pct,
            }
        
        except Exception as e:
            # 记录失败
            await EventRepository.log(
                "order_failed",
                symbol=symbol,
                direction=direction,
                stake=stake,
                exchange=exchange,
                account_id=account_id,
                client_order_id=client_order_id,
                error=str(e),
            )
            
            self._stats["total_orders"] += 1
            self._stats["failed_orders"] += 1
            
            # 发布事件
            bus = await get_event_bus()
            await bus.publish(EventType.EXECUTION_ORDER_FAILED, {
                "symbol": symbol,
                "direction": direction,
                "error": str(e),
            })
            
            logger.error(f"Order failed: {symbol} {direction} - {e}")
            return None
    
    async def execute_close(
        self,
        symbol: str,
        direction: str,
        amount: float,
        exchange: str = "binance",
        reason: str = "",
        priority: OrderPriority = OrderPriority.URGENT,
    ) -> Optional[Dict[str, Any]]:
        """
        执行平仓
        
        Args:
            symbol: 交易对
            direction: 方向
            amount: 数量
            exchange: 交易所
            reason: 平仓原因
            priority: 订单优先级
        
        Returns:
            订单信息或None
        """
        if not self._running:
            return None
        
        try:
            ex = self._exchanges.get(exchange)
            if not ex:
                raise ValueError(f"Exchange {exchange} not available")
            
            # 平仓方向与开仓相反
            side = "buy" if direction == "SHORT" else "sell"
            
            order = await ex.create_order(
                symbol=symbol,
                type="market",
                side=side,
                amount=amount,
                params={"reduceOnly": True},
            )
            
            fill_price = order.get("average", order.get("price", 0))
            
            await EventRepository.log(
                "close_filled",
                symbol=symbol,
                direction=direction,
                fill_price=fill_price,
                fill_amount=order.get("filled", 0),
                exchange=exchange,
            )
            
            logger.info(f"Close order filled: {symbol} {direction} price={fill_price}")
            
            return {
                "order_id": order.get("id", ""),
                "fill_price": fill_price,
                "fill_amount": order.get("filled", 0),
            }
        
        except Exception as e:
            logger.error(f"Close order failed: {symbol} {direction} - {e}")
            return None
    
    async def execute_stop_loss(
        self,
        symbol: str,
        direction: str,
        amount: float,
        stop_price: float,
        exchange: str = "binance",
    ) -> Optional[Dict[str, Any]]:
        """执行止损单"""
        try:
            ex = self._exchanges.get(exchange)
            if not ex:
                raise ValueError(f"Exchange {exchange} not available")
            
            side = "buy" if direction == "SHORT" else "sell"
            
            order = await ex.create_order(
                symbol=symbol,
                type="stop_market",
                side=side,
                amount=amount,
                params={
                    "stopPrice": stop_price,
                    "reduceOnly": True,
                },
            )
            
            logger.info(f"Stop loss set: {symbol} {direction} at {stop_price}")
            return {"order_id": order.get("id", "")}
        
        except Exception as e:
            logger.error(f"Stop loss failed: {symbol} {direction} - {e}")
            return None
    
    async def execute_take_profit(
        self,
        symbol: str,
        direction: str,
        amount: float,
        take_profit_price: float,
        exchange: str = "binance",
    ) -> Optional[Dict[str, Any]]:
        """执行止盈单"""
        try:
            ex = self._exchanges.get(exchange)
            if not ex:
                raise ValueError(f"Exchange {exchange} not available")
            
            side = "buy" if direction == "SHORT" else "sell"
            
            order = await ex.create_order(
                symbol=symbol,
                type="take_profit_market",
                side=side,
                amount=amount,
                params={
                    "stopPrice": take_profit_price,
                    "reduceOnly": True,
                },
            )
            
            logger.info(f"Take profit set: {symbol} {direction} at {take_profit_price}")
            return {"order_id": order.get("id", "")}
        
        except Exception as e:
            logger.error(f"Take profit failed: {symbol} {direction} - {e}")
            return None
    
    async def get_position(
        self,
        symbol: str,
        exchange: str = "binance",
    ) -> Optional[Dict[str, Any]]:
        """获取持仓信息"""
        try:
            ex = self._exchanges.get(exchange)
            if not ex:
                return None
            
            positions = await ex.fetch_positions([symbol])
            for pos in positions:
                if pos["symbol"] == symbol and float(pos.get("contracts", 0)) > 0:
                    return pos
            return None
        except Exception as e:
            logger.error(f"Failed to get position: {e}")
            return None
    
    async def get_balance(
        self,
        exchange: str = "binance",
    ) -> Dict[str, Any]:
        """获取账户余额"""
        try:
            ex = self._exchanges.get(exchange)
            if not ex:
                return {}
            
            balance = await ex.fetch_balance()
            return balance
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return {}
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        status = {
            "running": self._running,
            "exchanges": {},
            "stats": self._stats,
        }
        
        for name, exchange in self._exchanges.items():
            try:
                await exchange.fetch_time()
                status["exchanges"][name] = "connected"
            except Exception as e:
                status["exchanges"][name] = f"error: {e}"
        
        return status
