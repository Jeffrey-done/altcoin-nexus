"""
异步策略引擎
纯协程调度，无线程池阻塞
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type

from core.config import get_settings
from core.db import (
    CandidateRepository,
    SignalLogRepository,
    TradeRepository,
    get_db,
)
from core.events import EventType, get_event_bus
from services.datafeed import DataFeedService

logger = logging.getLogger("nexus.strategy")


class BaseStrategy:
    """策略基类 - 所有策略必须继承"""
    
    name: str = "base"
    direction: str = "SHORT"  # SHORT or LONG
    
    def __init__(self, datafeed: DataFeedService):
        self.datafeed = datafeed
        self.settings = get_settings()
    
    async def scan(self) -> List[Dict[str, Any]]:
        """扫描潜在标的，返回候选列表"""
        raise NotImplementedError
    
    async def confirm(self, candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """确认候选，返回信号详情或None"""
        raise NotImplementedError
    
    async def should_close(self, trade: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """检查是否应该平仓，返回平仓原因或None"""
        raise NotImplementedError


class ShortOverboughtStrategy(BaseStrategy):
    """超买做空策略"""
    
    name = "short_overbought"
    direction = "SHORT"
    
    async def scan(self) -> List[Dict[str, Any]]:
        """扫描超买标的 - 多交易所聚合"""
        config = self.settings.strategy
        
        # 获取所有交易所的行情（聚合扫描）
        candidates = await self.datafeed.scan_potential_symbols(
            min_volume=config.vol_min,
            min_pct_change=config.pct_24h_min,
            max_price=config.price_max,
            exchange=None,  # None = 扫描所有已连接交易所
        )
        
        # 过滤和评分
        scored_candidates = []
        for candidate in candidates:
            try:
                # 获取K线数据计算RSI（从候选所在的交易所）
                ohlcv = await self.datafeed.get_ohlcv(
                    candidate["symbol"], 
                    "1d", 
                    limit=20,
                    exchange=candidate["exchange"],  # 使用候选交易所
                )
                if not ohlcv:
                    continue
                
                # 计算RSI
                rsi = self._calculate_rsi(ohlcv, config.rsi_period)
                if rsi < config.daily_rsi_min:
                    continue
                
                # 计算评分
                score = self._calculate_score(
                    rsi=rsi,
                    pct_change=candidate["pct_change"],
                    volume=candidate["volume"],
                )
                
                candidate["rsi_1d"] = rsi
                candidate["score"] = score
                
                scored_candidates.append(candidate)
            except Exception as e:
                logger.debug(f"Error scoring {candidate['symbol']}: {e}")
                continue
        
        # 按评分排序
        scored_candidates.sort(key=lambda x: x["score"], reverse=True)
        return scored_candidates[:10]  # 返回前10个
    
    async def confirm(self, candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """确认候选"""
        config = self.settings.strategy
        symbol = candidate["symbol"]
        exchange = candidate.get("exchange", "binance")
        
        # 获取4小时K线（从候选交易所）
        ohlcv_4h = await self.datafeed.get_ohlcv(
            symbol, "4h", limit=50, exchange=exchange
        )
        if not ohlcv_4h:
            return None
        
        # 计算4小时RSI
        rsi_4h = self._calculate_rsi(ohlcv_4h, config.rsi_period)
        
        # 检查RSI下降
        if rsi_4h < config.h4_rsi_enter:
            return None
        
        # 获取资金费率（从候选交易所）
        funding = await self.datafeed.get_funding_rate(symbol, exchange)
        funding_rate = funding.get("fundingRate", 0) if funding else 0
        
        # 检查资金费率
        if funding_rate < config.funding_min or funding_rate > config.funding_max:
            return None
        
        # BTC过滤（从主交易所获取）
        if config.btc_filter_enabled:
            primary_exchange = self.settings.exchange.primary_exchange
            btc_ticker = await self.datafeed.get_ticker("BTC/USDT", primary_exchange)
            if btc_ticker:
                btc_pct = btc_ticker.get("percentage", 0)
                if btc_pct < config.btc_crash_threshold or btc_pct > config.btc_pump_threshold:
                    return None
        
        # 确定下单交易所（智能路由）
        target_exchange = await self._select_best_exchange(symbol, exchange)
        
        return {
            "symbol": symbol,
            "direction": self.direction,
            "strategy": self.name,
            "rsi_1d": candidate.get("rsi_1d", 0),
            "rsi_4h": rsi_4h,
            "funding_rate": funding_rate,
            "score": candidate.get("score", 0),
            "price": candidate["price"],
            "scan_exchange": exchange,  # 扫描到的交易所
            "target_exchange": target_exchange,  # 下单目标交易所
        }
    
    async def _select_best_exchange(
        self, 
        symbol: str, 
        scan_exchange: str,
    ) -> str:
        """
        智能选择下单交易所
        
        逻辑：
        1. 优先用主交易所（如果支持该 symbol）
        2. 否则用扫描到的交易所
        3. 考虑流动性和价差
        """
        primary = self.settings.exchange.primary_exchange
        
        # 检查主交易所是否有该交易对
        primary_ticker = await self.datafeed.get_ticker(symbol, primary)
        if primary_ticker:
            # 主交易所有该交易对，比较流动性
            scan_ticker = await self.datafeed.get_ticker(symbol, scan_exchange)
            
            if scan_ticker:
                primary_vol = primary_ticker.get("quoteVolume", 0)
                scan_vol = scan_ticker.get("quoteVolume", 0)
                
                # 如果主交易所流动性差距不大(>50%)，用主交易所
                if primary_vol > scan_vol * 0.5:
                    return primary
            
            return primary
        
        # 主交易所没有该交易对，用扫描到的交易所
        return scan_exchange
    
    async def should_close(self, trade: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """检查是否应该平仓"""
        # 这里实现止损止盈逻辑
        # 由风险管理模块处理
        return None
    
    def _calculate_rsi(self, ohlcv: List, period: int = 14) -> float:
        """计算RSI"""
        if len(ohlcv) < period + 1:
            return 50.0
        
        closes = [candle[4] for candle in ohlcv]
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 2)
    
    def _calculate_score(
        self,
        rsi: float,
        pct_change: float,
        volume: float,
    ) -> int:
        """计算综合评分"""
        score = 0
        
        # RSI评分
        if rsi >= 80:
            score += 40
        elif rsi >= 70:
            score += 30
        elif rsi >= 65:
            score += 20
        
        # 涨幅评分
        if pct_change >= 20:
            score += 30
        elif pct_change >= 15:
            score += 25
        elif pct_change >= 10:
            score += 20
        elif pct_change >= 5:
            score += 15
        
        # 成交量评分
        if volume >= 5000000:
            score += 20
        elif volume >= 2000000:
            score += 15
        elif volume >= 1000000:
            score += 10
        elif volume >= 500000:
            score += 5
        
        return min(score, 100)


class StrategyEngine:
    """
    策略引擎
    
    职责:
    - 驱动所有策略的扫描和确认周期
    - 管理候选池
    - 生成交易信号
    """
    
    def __init__(self, datafeed: DataFeedService):
        self.datafeed = datafeed
        self.settings = get_settings()
        self._strategies: Dict[str, BaseStrategy] = {}
        self._running = False
        self._scan_task: Optional[asyncio.Task] = None
        self._confirm_task: Optional[asyncio.Task] = None
        self._subscriptions: List[str] = []
        
        # 市场状态和优化参数
        self._current_regime: str = "ranging"
        self._regime_multiplier: Dict[str, float] = {"SHORT": 1.0, "LONG": 1.0}
        self._optimized_params: Dict[str, Any] = {}
        
        # 注册默认策略
        self._register_default_strategies()
    
    def _register_default_strategies(self) -> None:
        """注册默认策略"""
        from strategies.long_oversold import LongOversoldStrategy
        from strategies.prepump_sniffer import PrePumpSnifferStrategy
        
        self._strategies["short_overbought"] = ShortOverboughtStrategy(self.datafeed)
        self._strategies["long_oversold"] = LongOversoldStrategy(self.datafeed)
        self._strategies["prepump_sniffer"] = PrePumpSnifferStrategy(self.datafeed)
    
    def register_strategy(self, strategy: BaseStrategy) -> None:
        """注册策略"""
        self._strategies[strategy.name] = strategy
        logger.info(f"Strategy registered: {strategy.name}")
    
    async def start(self) -> None:
        """启动策略引擎"""
        if self._running:
            return
        
        self._running = True
        
        # 注册事件监听 (P0-4, P0-5)
        await self._register_event_listeners()
        
        # 启动扫描和确认任务
        self._scan_task = asyncio.create_task(self._scan_loop())
        self._confirm_task = asyncio.create_task(self._confirm_loop())
        
        logger.info("StrategyEngine started")
    
    async def stop(self) -> None:
        """停止策略引擎"""
        self._running = False
        
        # 取消事件订阅
        bus = await get_event_bus()
        for sub_id in self._subscriptions:
            await bus.unsubscribe(sub_id)
        self._subscriptions.clear()
        
        if self._scan_task:
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass
        
        if self._confirm_task:
            self._confirm_task.cancel()
            try:
                await self._confirm_task
            except asyncio.CancelledError:
                pass
        
        logger.info("StrategyEngine stopped")
    
    async def _register_event_listeners(self) -> None:
        """注册事件监听"""
        bus = await get_event_bus()
        
        # P0-4: 监听市场状态变化
        sub_id = await bus.subscribe(
            EventType.MARKET_REGIME_CHANGED,
            self._on_regime_changed,
            "strategy_regime"
        )
        self._subscriptions.append(sub_id)
        
        # P0-5: 监听优化参数更新
        sub_id = await bus.subscribe(
            EventType.OPTIMIZATION_PARAMS_UPDATED,
            self._on_params_updated,
            "strategy_params"
        )
        self._subscriptions.append(sub_id)
        
        logger.info("StrategyEngine event listeners registered")
    
    async def _on_regime_changed(self, event) -> None:
        """处理市场状态变化"""
        data = event.data
        old_regime = data.get("old_regime", "unknown")
        new_regime = data.get("new_regime", "ranging")
        
        self._current_regime = new_regime
        
        # 更新策略乘数
        from strategies.macro_filter import get_macro_filter
        macro_filter = get_macro_filter()
        
        self._regime_multiplier = {
            "SHORT": macro_filter.get_regime_multiplier("SHORT"),
            "LONG": macro_filter.get_regime_multiplier("LONG"),
        }
        
        logger.info(
            f"StrategyEngine regime changed: {old_regime} -> {new_regime} "
            f"multipliers={self._regime_multiplier}"
        )
    
    async def _on_params_updated(self, event) -> None:
        """处理优化参数更新"""
        data = event.data
        strategy_name = data.get("strategy", "")
        params = data.get("params", {})
        
        if strategy_name in self._strategies:
            # 更新策略配置
            strategy = self._strategies[strategy_name]
            if hasattr(strategy, '_config'):
                strategy._config.update(params)
                logger.info(f"Strategy {strategy_name} params updated: {params}")
            else:
                logger.warning(f"Strategy {strategy_name} has no _config attribute")
        
        self._optimized_params.update(params)
    
    async def _scan_loop(self) -> None:
        """扫描循环"""
        while self._running:
            try:
                await self.scan_all()
                await asyncio.sleep(300)  # 5分钟扫描一次
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scan loop error: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def _confirm_loop(self) -> None:
        """确认循环"""
        while self._running:
            try:
                await self.confirm_all()
                await asyncio.sleep(60)  # 1分钟确认一次
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Confirm loop error: {e}", exc_info=True)
                await asyncio.sleep(30)
    
    async def scan_all(self) -> None:
        """执行所有策略的扫描"""
        bus = await get_event_bus()
        
        for name, strategy in self._strategies.items():
            try:
                candidates = await strategy.scan()
                
                for candidate in candidates:
                    # 保存到数据库
                    await CandidateRepository.upsert({
                        "symbol": candidate["symbol"],
                        "strategy": name,
                        "direction": strategy.direction,
                        "price": candidate["price"],
                        "pct24h": candidate.get("pct_change", 0),
                        "vol24h": candidate.get("volume", 0),
                        "rsi_1d": candidate.get("rsi_1d", 0),
                        "score": candidate.get("score", 0),
                    })
                    
                    # 发布事件
                    await bus.publish(EventType.CANDIDATE_ADDED, {
                        "symbol": candidate["symbol"],
                        "strategy": name,
                        "score": candidate.get("score", 0),
                    })
                
                logger.info(f"Strategy {name} scanned: {len(candidates)} candidates")
            
            except Exception as e:
                logger.error(f"Strategy {name} scan error: {e}", exc_info=True)
    
    async def confirm_all(self) -> None:
        """执行所有策略的确认"""
        bus = await get_event_bus()
        
        for name, strategy in self._strategies.items():
            try:
                # 获取待确认的候选
                candidates = await CandidateRepository.get_active(
                    strategy=name,
                    exclude_triggered=True,
                )
                
                for candidate in candidates:
                    try:
                        signal = await strategy.confirm(candidate)
                        
                        if signal:
                            # 标记候选已触发
                            await CandidateRepository.mark_triggered(
                                symbol=candidate["symbol"],
                                trigger_type="confirm",
                                trigger_reason="Strategy confirmed",
                                strategy=name,
                            )
                            
                            # 记录信号
                            await SignalLogRepository.log({
                                "symbol": candidate["symbol"],
                                "strategy": name,
                                "score": signal.get("score", 0),
                                "grade": self._get_grade(signal.get("score", 0)),
                                "rsi_1d": signal.get("rsi_1d", 0),
                                "rsi_4h": signal.get("rsi_4h", 0),
                                "triggered_open": True,
                            })
                            
                            # 发布信号事件
                            await bus.publish(EventType.SIGNAL_TRIGGERED, signal)
                            
                            logger.info(
                                f"Signal confirmed: {candidate['symbol']} "
                                f"strategy={name} score={signal.get('score', 0)}"
                            )
                    
                    except Exception as e:
                        logger.error(
                            f"Confirm error for {candidate['symbol']}: {e}",
                            exc_info=True,
                        )
            
            except Exception as e:
                logger.error(f"Strategy {name} confirm error: {e}", exc_info=True)
    
    def _get_grade(self, score: int) -> str:
        """获取评分等级"""
        if score >= self.settings.strategy.score_full_threshold:
            return "A"
        elif score >= self.settings.strategy.score_half_threshold:
            return "B"
        return "SKIP"
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "running": self._running,
            "strategies": list(self._strategies.keys()),
            "scan_task": self._scan_task is not None and not self._scan_task.done(),
            "confirm_task": self._confirm_task is not None and not self._confirm_task.done(),
        }
