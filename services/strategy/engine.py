"""
Async Strategy Engine
Pure coroutine scheduling, no thread pool blocking
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.config import get_settings
from core.db import CandidateRepository, SignalLogRepository, TradeRepository
from core.events import EventType, get_event_bus
from services.datafeed import DataFeedService
from strategies.base import BaseStrategy

logger = logging.getLogger("nexus.strategy")


class StrategyEngine:
    """
    Strategy Engine
    
    Responsibilities:
    - Drive scanning and confirmation cycles for all registered strategies
    - Manage candidate pool
    - Generate trade signals (published via event bus)
    """
    
    def __init__(self, datafeed: DataFeedService):
        self.datafeed = datafeed
        self.settings = get_settings()
        self._strategies: Dict[str, BaseStrategy] = {}
        self._running = False
        self._scan_task: Optional[asyncio.Task] = None
        self._confirm_task: Optional[asyncio.Task] = None
        self._subscriptions: List[str] = []
        
        # Market regime and optimization parameters
        self._current_regime: str = "ranging"
        self._regime_multiplier: Dict[str, float] = {"SHORT": 1.0, "LONG": 1.0}
        self._optimized_params: Dict[str, Any] = {}
        
        # Register default strategies
        self._register_default_strategies()
    
    def _register_default_strategies(self) -> None:
        from strategies.short_overbought import ShortOverboughtStrategy
        from strategies.long_oversold import LongOversoldStrategy
        from strategies.prepump_sniffer import PrePumpSnifferStrategy
        from strategies.arb_cross_exchange import CrossExchangeArbStrategy
        from strategies.momentum_scalp import MomentumScalpStrategy
        
        self._strategies["short_overbought"] = ShortOverboughtStrategy(self.datafeed)
        self._strategies["long_oversold"] = LongOversoldStrategy(self.datafeed)
        self._strategies["prepump_sniffer"] = PrePumpSnifferStrategy(self.datafeed)
        self._strategies["arb_cross_exchange"] = CrossExchangeArbStrategy(self.datafeed)
        self._strategies["momentum_scalp"] = MomentumScalpStrategy(self.datafeed)
    
    def register_strategy(self, strategy: BaseStrategy) -> None:
        self._strategies[strategy.name] = strategy
        logger.info(f"Strategy registered: {strategy.name}")
    
    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        await self._register_event_listeners()
        self._scan_task = asyncio.create_task(self._scan_loop())
        self._confirm_task = asyncio.create_task(self._confirm_loop())
        logger.info(f"StrategyEngine started with: {list(self._strategies.keys())}")
    
    async def stop(self) -> None:
        self._running = False
        bus = await get_event_bus()
        for sub_id in self._subscriptions:
            await bus.unsubscribe(sub_id)
        self._subscriptions.clear()
        for task in (self._scan_task, self._confirm_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        logger.info("StrategyEngine stopped")
    
    async def _register_event_listeners(self) -> None:
        bus = await get_event_bus()
        sub_id = await bus.subscribe(EventType.MARKET_REGIME_CHANGED, self._on_regime_changed, "strategy_regime")
        self._subscriptions.append(sub_id)
        sub_id = await bus.subscribe(EventType.OPTIMIZATION_PARAMS_UPDATED, self._on_params_updated, "strategy_params")
        self._subscriptions.append(sub_id)
        logger.info("StrategyEngine event listeners registered")
    
    async def _on_regime_changed(self, event) -> None:
        data = event.data
        self._current_regime = data.get("new_regime", "ranging")
        from strategies.macro_filter import get_macro_filter
        macro = get_macro_filter()
        self._regime_multiplier = {
            "SHORT": macro.get_regime_multiplier("SHORT"),
            "LONG": macro.get_regime_multiplier("LONG"),
        }
        logger.info(f"Regime changed -> {self._current_regime} multipliers={self._regime_multiplier}")
    
    async def _on_params_updated(self, event) -> None:
        data = event.data
        name = data.get("strategy", "")
        params = data.get("params", {})
        if name in self._strategies and hasattr(self._strategies[name], "_config"):
            self._strategies[name]._config.update(params)
        self._optimized_params.update(params)
    
    async def _scan_loop(self) -> None:
        while self._running:
            try:
                await self.scan_all()
                await asyncio.sleep(300)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scan loop error: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def _confirm_loop(self) -> None:
        while self._running:
            try:
                await self.confirm_all()
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Confirm loop error: {e}", exc_info=True)
                await asyncio.sleep(30)
    
    async def scan_all(self) -> None:
        bus = await get_event_bus()
        for name, strategy in self._strategies.items():
            if not strategy.is_enabled:
                continue
            try:
                candidates = await strategy.scan()
                for c in candidates:
                    direction = c.get("direction", strategy.direction)
                    mult = self._regime_multiplier.get(direction, 1.0)
                    c["score"] = int(c.get("score", 0) * mult)
                    
                    await CandidateRepository.upsert({
                        "symbol": c["symbol"], "strategy": name,
                        "direction": strategy.direction, "price": c["price"],
                        "pct24h": c.get("pct_change", c.get("pct_24h", 0)),
                        "vol24h": c.get("volume", 0), "rsi_1d": c.get("rsi_1d", 0),
                        "score": c.get("score", 0),
                    })
                    await bus.publish(EventType.CANDIDATE_ADDED, {
                        "symbol": c["symbol"], "strategy": name, "score": c.get("score", 0),
                    })
                logger.info(f"Strategy {name}: {len(candidates)} candidates")
            except Exception as e:
                logger.error(f"Strategy {name} scan error: {e}", exc_info=True)
    
    async def confirm_all(self) -> None:
        bus = await get_event_bus()
        from strategies.macro_filter import get_macro_filter
        macro = get_macro_filter()
        
        for name, strategy in self._strategies.items():
            if not strategy.is_enabled:
                continue
            try:
                candidates = await CandidateRepository.get_active(strategy=name, exclude_triggered=True)
                for c in candidates:
                    try:
                        signal = await strategy.confirm(c)
                        if not signal:
                            continue
                        
                        direction = signal.get("direction", strategy.direction)
                        decision = macro.evaluate(direction)
                        if not decision.allow_open:
                            logger.info(f"Macro blocked {c['symbol']}: {decision.reason}")
                            continue
                        
                        signal["score"] = signal.get("score", 0) + decision.score_bonus
                        signal["stake_multiplier"] = decision.stake_multiplier
                        
                        await CandidateRepository.mark_triggered(
                            symbol=c["symbol"], trigger_type="confirm",
                            trigger_reason="Strategy confirmed", strategy=name,
                        )
                        await SignalLogRepository.log({
                            "symbol": c["symbol"], "strategy": name,
                            "score": signal.get("score", 0),
                            "grade": self._get_grade(signal.get("score", 0)),
                            "rsi_1d": signal.get("rsi_1d", 0), "rsi_4h": signal.get("rsi_4h", 0),
                            "triggered_open": True,
                        })
                        await bus.publish(EventType.SIGNAL_TRIGGERED, signal)
                        logger.info(f"Signal: {c['symbol']} {name} score={signal.get('score', 0)}")
                    except Exception as e:
                        logger.error(f"Confirm error {c['symbol']}: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Strategy {name} confirm error: {e}", exc_info=True)
    
    def _get_grade(self, score: int) -> str:
        if score >= self.settings.strategy.score_full_threshold:
            return "A"
        elif score >= self.settings.strategy.score_half_threshold:
            return "B"
        return "SKIP"
    
    async def health_check(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "strategies": list(self._strategies.keys()),
            "scan_task": self._scan_task is not None and not self._scan_task.done(),
            "confirm_task": self._confirm_task is not None and not self._confirm_task.done(),
            "current_regime": self._current_regime,
        }
