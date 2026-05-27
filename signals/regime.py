"""
市场状态感知模块
实时识别市场状态，驱动策略动态切换
"""

import asyncio
import logging
from enum import Enum
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from core.config import get_settings
from core.events import EventType, get_event_bus

logger = logging.getLogger("nexus.regime")


class MarketRegime(str, Enum):
    """市场状态枚举"""
    TRENDING_UP = "trending_up"      # 单边上涨
    TRENDING_DOWN = "trending_down"  # 单边下跌
    RANGING = "ranging"              # 震荡
    HIGH_VOLATILITY = "high_vol"     # 高波动
    CRASH = "crash"                  # 崩盘
    RECOVERY = "recovery"            # 反弹恢复


@dataclass
class RegimeState:
    """市场状态"""
    regime: MarketRegime
    confidence: float  # 0-1
    btc_trend: float   # BTC 24h 涨跌幅
    volatility: float  # 波动率
    funding_rate: avg_funding_rate  # 平均资金费率
    timestamp: datetime


class MarketRegimeDetector:
    """
    市场状态检测器
    
    基于多维度指标实时判断市场状态：
    - BTC 趋势
    - 波动率
    - 资金费率
    - 市场宽度（涨跌比）
    """
    
    def __init__(self, datafeed=None):
        self.settings = get_settings()
        self.datafeed = datafeed
        self._running = False
        self._detect_task: Optional[asyncio.Task] = None
        
        # 当前状态
        self._current_regime: Optional[RegimeState] = None
        self._regime_history: List[RegimeState] = []
        
        # 阈值配置
        self._crash_threshold = -8.0      # 崩盘阈值
        self._pump_threshold = 10.0       # 暴涨阈值
        self._high_vol_threshold = 5.0    # 高波动阈值
        self._trend_threshold = 3.0       # 趋势阈值
    
    async def start(self) -> None:
        """启动检测器"""
        if self._running:
            return
        
        self._running = True
        self._detect_task = asyncio.create_task(self._detect_loop())
        logger.info("MarketRegimeDetector started")
    
    async def stop(self) -> None:
        """停止检测器"""
        self._running = False
        
        if self._detect_task:
            self._detect_task.cancel()
            try:
                await self._detect_task
            except asyncio.CancelledError:
                pass
        
        logger.info("MarketRegimeDetector stopped")
    
    async def _detect_loop(self) -> None:
        """检测循环"""
        while self._running:
            try:
                await self._detect_regime()
                await asyncio.sleep(300)  # 5分钟检测一次
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Regime detection error: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def _detect_regime(self) -> None:
        """检测市场状态"""
        if not self.datafeed:
            return
        
        try:
            # 获取 BTC 数据
            btc_ticker = await self.datafeed.get_ticker("BTC/USDT")
            if not btc_ticker:
                return
            
            btc_trend = btc_ticker.get("percentage", 0)
            btc_volatility = await self._calculate_volatility("BTC/USDT")
            
            # 获取市场宽度
            market_breadth = await self._calculate_market_breadth()
            
            # 获取平均资金费率
            avg_funding = await self._get_avg_funding_rate()
            
            # 判断市场状态
            regime, confidence = self._classify_regime(
                btc_trend=btc_trend,
                volatility=btc_volatility,
                market_breadth=market_breadth,
                funding_rate=avg_funding,
            )
            
            # 更新状态
            new_state = RegimeState(
                regime=regime,
                confidence=confidence,
                btc_trend=btc_trend,
                volatility=btc_volatility,
                funding_rate=avg_funding,
                timestamp=datetime.now(timezone.utc),
            )
            
            # 检查状态是否变化
            if self._current_regime is None or self._current_regime.regime != regime:
                await self._on_regime_changed(self._current_regime, new_state)
            
            self._current_regime = new_state
            self._regime_history.append(new_state)
            
            # 保留最近 100 条记录
            if len(self._regime_history) > 100:
                self._regime_history = self._regime_history[-100:]
            
            logger.debug(f"Market regime: {regime.value} (confidence: {confidence:.2f})")
        
        except Exception as e:
            logger.error(f"Regime detection error: {e}")
    
    def _classify_regime(
        self,
        btc_trend: float,
        volatility: float,
        market_breadth: float,
        funding_rate: float,
    ) -> tuple[MarketRegime, float]:
        """
        分类市场状态
        
        Returns:
            (市场状态, 置信度)
        """
        # 崩盘检测
        if btc_trend < self._crash_threshold:
            return MarketRegime.CRASH, 0.9
        
        # 暴涨检测
        if btc_trend > self._pump_threshold:
            return MarketRegime.TRENDING_UP, 0.85
        
        # 高波动检测
        if volatility > self._high_vol_threshold:
            return MarketRegime.HIGH_VOLATILITY, 0.8
        
        # 趋势检测
        if btc_trend > self._trend_threshold:
            return MarketRegime.TRENDING_UP, 0.75
        
        if btc_trend < -self._trend_threshold:
            return MarketRegime.TRENDING_DOWN, 0.75
        
        # 震荡
        return MarketRegime.RANGING, 0.7
    
    async def _calculate_volatility(self, symbol: str) -> float:
        """计算波动率"""
        if not self.datafeed:
            return 0.0
        
        try:
            ohlcv = await self.datafeed.get_ohlcv(symbol, "1h", limit=24)
            if not ohlcv or len(ohlcv) < 2:
                return 0.0
            
            # 计算小时收益率的标准差
            closes = [candle[4] for candle in ohlcv]
            returns = [(closes[i] - closes[i-1]) / closes[i-1] * 100 
                      for i in range(1, len(closes))]
            
            if not returns:
                return 0.0
            
            import numpy as np
            return float(np.std(returns))
        
        except Exception:
            return 0.0
    
    async def _calculate_market_breadth(self) -> float:
        """计算市场宽度（涨跌比）"""
        if not self.datafeed:
            return 0.5
        
        try:
            tickers = await self.datafeed.get_all_tickers()
            if not tickers:
                return 0.5
            
            up_count = 0
            total = 0
            
            for symbol, ticker in tickers.items():
                if symbol.endswith("/USDT"):
                    pct = ticker.get("percentage", 0)
                    if pct > 0:
                        up_count += 1
                    total += 1
            
            return up_count / total if total > 0 else 0.5
        
        except Exception:
            return 0.5
    
    async def _get_avg_funding_rate(self) -> float:
        """获取平均资金费率"""
        # 简化实现
        return 0.0
    
    async def _on_regime_changed(
        self,
        old_state: Optional[RegimeState],
        new_state: RegimeState,
    ) -> None:
        """市场状态变化回调"""
        old_regime = old_state.regime.value if old_state else "unknown"
        new_regime = new_state.regime.value
        
        logger.info(f"Market regime changed: {old_regime} -> {new_regime}")
        
        # 发布事件
        bus = await get_event_bus()
        await bus.publish(EventType.MARKET_REGIME_CHANGED, {
            "old_regime": old_regime,
            "new_regime": new_regime,
            "confidence": new_state.confidence,
            "btc_trend": new_state.btc_trend,
            "volatility": new_state.volatility,
        })
    
    def get_current_regime(self) -> Optional[RegimeState]:
        """获取当前市场状态"""
        return self._current_regime
    
    def get_regime_history(self) -> List[RegimeState]:
        """获取状态历史"""
        return self._regime_history
    
    def get_strategy_multiplier(self) -> Dict[str, float]:
        """
        根据市场状态获取策略乘数
        
        Returns:
            {direction: multiplier}
        """
        if not self._current_regime:
            return {"SHORT": 1.0, "LONG": 1.0}
        
        regime = self._current_regime.regime
        
        multipliers = {
            MarketRegime.TRENDING_UP: {"SHORT": 0.3, "LONG": 1.5},
            MarketRegime.TRENDING_DOWN: {"SHORT": 1.5, "LONG": 0.3},
            MarketRegime.RANGING: {"SHORT": 1.0, "LONG": 1.0},
            MarketRegime.HIGH_VOLATILITY: {"SHORT": 0.5, "LONG": 0.5},
            MarketRegime.CRASH: {"SHORT": 0.0, "LONG": 0.0},  # 暂停交易
            MarketRegime.RECOVERY: {"SHORT": 0.5, "LONG": 1.0},
        }
        
        return multipliers.get(regime, {"SHORT": 1.0, "LONG": 1.0})
