"""
Trade Manager Service
Full lifecycle management: Signal -> Execute -> TP/SL -> Close

Connects strategy signals to actual order execution,
and manages positions through their entire lifecycle with dynamic TP/SL.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.config import get_settings
from core.db import EventRepository, TradeRepository
from core.events import EventType, get_event_bus
from services.execution.router import ExecutionRouter, OrderPriority
from services.datafeed import DataFeedService

logger = logging.getLogger("nexus.trade_manager")


class PositionTracker:
    """Real-time position price tracking with TP/SL evaluation"""
    
    def __init__(self):
        self._positions: Dict[str, Dict[str, Any]] = {}
        self._price_cache: Dict[str, float] = {}
    
    def register(self, trade_id: str, trade_data: Dict[str, Any]) -> None:
        self._positions[trade_id] = {
            **trade_data,
            "best_price": trade_data.get("entry_price", 0),
            "current_price": trade_data.get("entry_price", 0),
            "pnl_pct": 0.0,
            "trail_active": False,
            "tp1_triggered": trade_data.get("tp1_triggered", False),
        }
    
    def unregister(self, trade_id: str) -> None:
        self._positions.pop(trade_id, None)
    
    def update_price(self, symbol: str, price: float) -> None:
        self._price_cache[symbol] = price
        for tid, pos in self._positions.items():
            if pos.get("symbol") == symbol:
                pos["current_price"] = price
                entry = pos.get("entry_price", 0)
                direction = pos.get("direction", "LONG")
                stake = pos.get("stake", 0)
                leverage = pos.get("leverage", 1)
                if entry > 0:
                    if direction == "LONG":
                        pos["pnl_pct"] = (price - entry) / entry * 100
                        pos["pnl"] = (price - entry) / entry * stake * leverage
                        if price > pos.get("best_price", 0):
                            pos["best_price"] = price
                    else:
                        pos["pnl_pct"] = (entry - price) / entry * 100
                        pos["pnl"] = (entry - price) / entry * stake * leverage
                        if price < pos.get("best_price", float("inf")):
                            pos["best_price"] = price
    
    def check_triggers(self, trade_id: str) -> Optional[Dict[str, Any]]:
        pos = self._positions.get(trade_id)
        if not pos:
            return None
        
        pnl_pct = pos.get("pnl_pct", 0)
        direction = pos.get("direction", "LONG")
        entry = pos.get("entry_price", 0)
        current = pos.get("current_price", 0)
        best = pos.get("best_price", 0)
        
        if not entry or not current:
            return None
        
        # Hard stop loss
        hard_stop_pct = pos.get("hard_stop_pct", 5.0)
        if hard_stop_pct and pnl_pct <= -hard_stop_pct:
            return {"type": "hard_stop", "reason": f"PnL {pnl_pct:.2f}% hit stop -{hard_stop_pct}%"}
        
        # TP1 (partial close)
        tp1_pct = pos.get("tp1_pct", 3.0)
        if not pos.get("tp1_triggered") and tp1_pct and pnl_pct >= tp1_pct:
            return {"type": "tp1", "reason": f"PnL {pnl_pct:.2f}% hit TP1 {tp1_pct}%"}
        
        # TP2 (full close) - only after TP1
        tp2_pct = pos.get("tp2_pct", 6.0)
        if pos.get("tp1_triggered") and tp2_pct and pnl_pct >= tp2_pct:
            return {"type": "tp2", "reason": f"PnL {pnl_pct:.2f}% hit TP2 {tp2_pct}%"}
        
        # Trailing stop (after TP1 or trail activation)
        trail_activate = pos.get("trail_activate_pct", 2.0)
        if trail_activate and (pos.get("tp1_triggered") or pnl_pct >= trail_activate):
            pos["trail_active"] = True
            trail_ratio = pos.get("trail_retrace_ratio", 0.5)
            if direction == "LONG" and best > 0:
                retrace = (best - current) / best * 100
                max_retrace = pnl_pct * trail_ratio
                if retrace > max_retrace and pnl_pct > 0:
                    return {"type": "trail_stop", "reason": f"Trail: retraced {retrace:.2f}% > max {max_retrace:.2f}%"}
            elif direction == "SHORT" and best < float("inf") and best > 0:
                retrace = (current - best) / best * 100
                max_retrace = pnl_pct * trail_ratio
                if retrace > max_retrace and pnl_pct > 0:
                    return {"type": "trail_stop", "reason": f"Trail: retraced {retrace:.2f}% > max {max_retrace:.2f}%"}
        
        # Max hold time
        max_hold = pos.get("max_hold_minutes", 0)
        if max_hold and max_hold > 0:
            opened_at = pos.get("opened_at")
            if opened_at:
                if isinstance(opened_at, str):
                    opened_at = datetime.fromisoformat(opened_at)
                elapsed = (datetime.now(timezone.utc) - opened_at).total_seconds() / 60
                if elapsed > max_hold:
                    return {"type": "max_hold", "reason": f"Max hold {max_hold}m exceeded ({elapsed:.0f}m)"}
        
        return None
    
    def get_all_positions(self) -> Dict[str, Dict[str, Any]]:
        return self._positions.copy()
    
    def get_position(self, trade_id: str) -> Optional[Dict[str, Any]]:
        return self._positions.get(trade_id)


class TradeManagerService:
    """
    Trade Manager - Full Lifecycle Controller
    
    Pipeline:
    1. Subscribe to SIGNAL_TRIGGERED events
    2. Pre-flight checks (grade, size)
    3. Execute open via ExecutionRouter
    4. Register in PositionTracker
    5. Real-time price monitoring
    6. Dynamic TP/SL evaluation
    7. Execute close / partial close
    8. Update risk state and publish events
    """
    
    def __init__(self, execution_router: ExecutionRouter, datafeed: DataFeedService):
        self.execution_router = execution_router
        self.datafeed = datafeed
        self.settings = get_settings()
        self._running = False
        self._subscriptions: List[str] = []
        self._monitor_task: Optional[asyncio.Task] = None
        self._price_task: Optional[asyncio.Task] = None
        self.tracker = PositionTracker()
        self._stats = {
            "signals_received": 0,
            "signals_executed": 0,
            "signals_blocked": 0,
            "positions_closed": 0,
            "total_pnl": 0.0,
        }
    
    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        await self._load_open_positions()
        await self._register_event_listeners()
        self._monitor_task = asyncio.create_task(self._monitor_positions_loop())
        self._price_task = asyncio.create_task(self._price_update_loop())
        logger.info(f"TradeManagerService started | Tracking {len(self.tracker.get_all_positions())} positions")
    
    async def stop(self) -> None:
        self._running = False
        bus = await get_event_bus()
        for sub_id in self._subscriptions:
            await bus.unsubscribe(sub_id)
        self._subscriptions.clear()
        for task in (self._monitor_task, self._price_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        logger.info("TradeManagerService stopped")
    
    async def _load_open_positions(self) -> None:
        try:
            open_trades = await TradeRepository.get_open()
            for trade in open_trades:
                tid = trade.get("id", "")
                if tid:
                    self.tracker.register(tid, trade)
            logger.info(f"Loaded {len(open_trades)} open positions into tracker")
        except Exception as e:
            logger.error(f"Failed to load open positions: {e}")
    
    async def _register_event_listeners(self) -> None:
        bus = await get_event_bus()
        for event_type, handler, name in [
            (EventType.SIGNAL_TRIGGERED, self._on_signal_triggered, "tm_signal"),
            (EventType.TRADE_TP1, self._on_tp1_event, "tm_tp1"),
            (EventType.RISK_ALERT, self._on_risk_alert, "tm_risk"),
        ]:
            sub_id = await bus.subscribe(event_type, handler, name)
            self._subscriptions.append(sub_id)
        logger.info("TradeManager event listeners registered")
    
    async def _on_signal_triggered(self, event) -> None:
        signal = event.data
        self._stats["signals_received"] += 1
        
        symbol = signal.get("symbol", "")
        direction = signal.get("direction", "LONG")
        strategy = signal.get("strategy", "")
        score = signal.get("score", 0)
        exchange = signal.get("exchange", "binance")
        
        if signal.get("risk_blocked"):
            self._stats["signals_blocked"] += 1
            return
        
        grade = self._get_grade(score)
        if grade == "SKIP":
            self._stats["signals_blocked"] += 1
            return
        
        # Position sizing
        stake_multiplier = signal.get("stake_multiplier", 1.0)
        base_stake = self.settings.risk.default_stake
        if signal.get("default_stake_pct"):
            base_stake = self.settings.risk.max_stake * signal["default_stake_pct"]
        
        stake = min(base_stake * stake_multiplier, self.settings.risk.max_stake * 0.5)
        stake = max(stake, 5.0)
        leverage = signal.get("leverage", self.settings.exchange.leverage)
        
        logger.info(f"Signal: {symbol} {direction} strat={strategy} score={score} grade={grade} stake=${stake:.2f} lev={leverage}x")
        
        result = await self.execution_router.execute_open(
            symbol=symbol, direction=direction, stake=stake, leverage=leverage,
            exchange=exchange, strategy=strategy, priority=OrderPriority.NORMAL,
        )
        
        if result:
            self._stats["signals_executed"] += 1
            await self._create_trade_record(signal, result, stake, leverage, exchange)
        else:
            self._stats["signals_blocked"] += 1
    
    async def _create_trade_record(self, signal, result, stake, leverage, exchange) -> None:
        trade_id = f"trade_{uuid.uuid4().hex[:12]}"
        entry_price = result.get("fill_price", signal.get("price", 0))
        direction = signal.get("direction", "LONG")
        
        tp1_pct = signal.get("tp1_pct", self.settings.strategy.tp1_pct)
        tp2_pct = signal.get("tp2_pct", self.settings.strategy.tp2_pct)
        hard_stop_pct = signal.get("hard_stop_pct", self.settings.strategy.hard_stop_pct)
        trail_activate_pct = signal.get("trail_activate_pct", self.settings.strategy.trail_activate_pct)
        
        if direction == "LONG":
            tp1_price = entry_price * (1 + tp1_pct / 100)
            tp2_price = entry_price * (1 + tp2_pct / 100)
            hard_stop_price = entry_price * (1 - hard_stop_pct / 100)
        else:
            tp1_price = entry_price * (1 - tp1_pct / 100)
            tp2_price = entry_price * (1 - tp2_pct / 100)
            hard_stop_price = entry_price * (1 + hard_stop_pct / 100)
        
        max_hold_min = signal.get("max_hold_minutes", 1440)
        
        trade_data = {
            "id": trade_id,
            "symbol": signal["symbol"],
            "direction": direction,
            "strategy": signal.get("strategy", ""),
            "status": "open",
            "entry_price": entry_price,
            "stake": stake,
            "leverage": leverage,
            "notional": stake * leverage,
            "shares": (stake * leverage) / entry_price if entry_price > 0 else 0,
            "take_profit_1": tp1_price,
            "take_profit_2": tp2_price,
            "tp1_triggered": False,
            "stake_remaining": stake,
            "hard_stop_price": hard_stop_price,
            "best_pnl_pct": 0.0,
            "trail_stop_price": None,
            "max_hold_hours": max_hold_min // 60,
            "exchange": exchange,
            "live_order_id": result.get("order_id", ""),
            "client_order_id": result.get("client_order_id", ""),
            "ref_price_at_order": signal.get("price", 0),
            "slippage_pct": result.get("slippage_pct", 0),
            "account_id": "default",
            "opened_at": datetime.now(timezone.utc),
        }
        
        await TradeRepository.create(trade_data)
        self.tracker.register(trade_id, trade_data)
        
        # Place exchange-level stop loss
        try:
            shares = trade_data["shares"]
            await self.execution_router.execute_stop_loss(
                symbol=signal["symbol"], direction=direction,
                amount=shares, stop_price=hard_stop_price, exchange=exchange,
            )
        except Exception as e:
            logger.warning(f"Exchange SL placement failed: {e} (local monitoring active)")
        
        logger.info(
            f"Trade opened: {trade_id} {signal['symbol']} {direction} "
            f"@ {entry_price:.6f} TP1={tp1_price:.6f} SL={hard_stop_price:.6f}"
        )
    
    async def _on_tp1_event(self, event) -> None:
        data = event.data
        trade_id = data.get("trade_id", "")
        if trade_id:
            pos = self.tracker.get_position(trade_id)
            if pos and not pos.get("tp1_triggered"):
                await self._execute_partial_close(trade_id, 0.5, "TP1")
    
    async def _on_risk_alert(self, event) -> None:
        data = event.data
        alert_type = data.get("alert_type", "")
        trade_id = data.get("trade_id", "")
        if trade_id and alert_type in ("hard_stop_triggered", "trail_stop_triggered"):
            await self._execute_full_close(trade_id, alert_type)
    
    async def _execute_partial_close(self, trade_id: str, ratio: float, reason: str) -> bool:
        pos = self.tracker.get_position(trade_id)
        if not pos:
            return False
        
        close_amount = pos.get("shares", 0) * ratio
        if close_amount <= 0:
            return False
        
        result = await self.execution_router.execute_close(
            symbol=pos["symbol"], direction=pos["direction"],
            amount=close_amount, exchange=pos.get("exchange", "binance"),
            reason=reason, priority=OrderPriority.NORMAL,
        )
        
        if result:
            pos["tp1_triggered"] = True
            pos["shares"] = pos.get("shares", 0) - close_amount
            pos["stake_remaining"] = pos.get("stake", 0) * (1 - ratio)
            
            fill_price = result.get("fill_price", 0)
            entry = pos.get("entry_price", 0)
            if entry > 0 and fill_price > 0:
                if pos["direction"] == "LONG":
                    partial_pnl = (fill_price - entry) / entry * close_amount * entry
                else:
                    partial_pnl = (entry - fill_price) / entry * close_amount * entry
                self._stats["total_pnl"] += partial_pnl
            
            await TradeRepository.trigger_tp1_with_lock(
                trade_id=trade_id, tp1_price=fill_price,
                tp1_close_order_id=result.get("order_id"),
            )
            logger.info(f"Partial close: {trade_id} {ratio*100:.0f}% @ {fill_price} reason={reason}")
            return True
        return False
    
    async def _execute_full_close(self, trade_id: str, reason: str) -> bool:
        pos = self.tracker.get_position(trade_id)
        if not pos or pos.get("shares", 0) <= 0:
            return False
        
        result = await self.execution_router.execute_close(
            symbol=pos["symbol"], direction=pos["direction"],
            amount=pos["shares"], exchange=pos.get("exchange", "binance"),
            reason=reason, priority=OrderPriority.URGENT,
        )
        
        if result:
            fill_price = result.get("fill_price", 0)
            entry = pos.get("entry_price", 0)
            if entry > 0 and fill_price > 0:
                if pos["direction"] == "LONG":
                    pnl = (fill_price - entry) / entry * pos.get("stake", 0) * pos.get("leverage", 1)
                else:
                    pnl = (entry - fill_price) / entry * pos.get("stake", 0) * pos.get("leverage", 1)
            else:
                pnl = pos.get("pnl", 0)
            
            total_pnl = pnl + pos.get("tp1_locked_pnl", 0)
            self._stats["total_pnl"] += total_pnl
            self._stats["positions_closed"] += 1
            
            await TradeRepository.close_trade(
                trade_id=trade_id, pnl=total_pnl, close_price=fill_price,
                close_reason=reason, close_type="signal",
                close_order_id=result.get("order_id"),
                exit_ref_price=fill_price,
                exit_slippage_pct=result.get("slippage_pct", 0),
            )
            
            self.tracker.unregister(trade_id)
            
            bus = await get_event_bus()
            await bus.publish(EventType.TRADE_CLOSED, {
                "trade_id": trade_id, "symbol": pos["symbol"],
                "direction": pos["direction"], "pnl": total_pnl,
                "close_reason": reason, "close_price": fill_price,
                "account_id": pos.get("account_id", "default"),
            })
            
            logger.info(f"Trade closed: {trade_id} pnl=${total_pnl:.2f} reason={reason}")
            return True
        return False
    
    async def _monitor_positions_loop(self) -> None:
        while self._running:
            try:
                for trade_id, pos in list(self.tracker.get_all_positions().items()):
                    trigger = self.tracker.check_triggers(trade_id)
                    if trigger:
                        t, r = trigger["type"], trigger["reason"]
                        logger.warning(f"Trigger: {trade_id} {t}: {r}")
                        if t == "tp1":
                            await self._execute_partial_close(trade_id, 0.5, r)
                        else:
                            await self._execute_full_close(trade_id, r)
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor error: {e}", exc_info=True)
                await asyncio.sleep(5)
    
    async def _price_update_loop(self) -> None:
        while self._running:
            try:
                positions = self.tracker.get_all_positions()
                symbols_seen = set()
                for pos in positions.values():
                    ex = pos.get("exchange", "binance")
                    sym = pos.get("symbol", "")
                    key = f"{ex}:{sym}"
                    if key in symbols_seen:
                        continue
                    symbols_seen.add(key)
                    try:
                        ticker = await self.datafeed.get_ticker(sym, ex)
                        if ticker and ticker.get("last"):
                            self.tracker.update_price(sym, ticker["last"])
                    except Exception:
                        continue
                await asyncio.sleep(3)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Price update error: {e}")
                await asyncio.sleep(5)
    
    def _get_grade(self, score: int) -> str:
        if score >= self.settings.strategy.score_full_threshold:
            return "A"
        elif score >= self.settings.strategy.score_half_threshold:
            return "B"
        return "SKIP"
    
    async def health_check(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "positions_tracked": len(self.tracker.get_all_positions()),
            "stats": self._stats,
        }
