"""
宏观决策过滤器 (MacroFilter)
将宏观信号转化为仓位乘数和评分加成
"""

import logging
from typing import Any, Dict, Optional
from dataclasses import dataclass

from signals.regime import MarketRegime, MarketRegimeDetector

logger = logging.getLogger("nexus.macro")


@dataclass
class MacroDecision:
    """宏观决策"""
    regime: MarketRegime
    confidence: float
    
    # 决策输出
    stake_multiplier: float = 1.0    # 仓位乘数
    score_bonus: int = 0             # 评分加成
    allow_open: bool = True          # 允许开仓
    reason: str = ""


class MacroFilter:
    """
    宏观决策过滤器
    
    功能：
    1. 接收市场状态信号
    2. 根据状态调整仓位和评分
    3. 在极端行情下阻止开仓
    
    这是 L4 级自治的核心 - 根据环境自动调整行为
    """
    
    def __init__(self, regime_detector: Optional[MarketRegimeDetector] = None):
        self.regime_detector = regime_detector
        
        # 宏观参数配置
        self._config = {
            # 市场状态 → 仓位乘数
            "regime_multipliers": {
                MarketRegime.TRENDING_UP: {
                    "SHORT": 0.3,   # 上涨趋势做空减仓
                    "LONG": 1.5,    # 上涨趋势做多加仓
                },
                MarketRegime.TRENDING_DOWN: {
                    "SHORT": 1.5,   # 下跌趋势做空加仓
                    "LONG": 0.3,    # 下跌趋势做多减仓
                },
                MarketRegime.RANGING: {
                    "SHORT": 1.0,
                    "LONG": 1.0,
                },
                MarketRegime.HIGH_VOLATILITY: {
                    "SHORT": 0.5,   # 高波动减仓
                    "LONG": 0.5,
                },
                MarketRegime.CRASH: {
                    "SHORT": 0.0,   # 崩盘暂停
                    "LONG": 0.0,
                },
                MarketRegime.RECOVERY: {
                    "SHORT": 0.5,
                    "LONG": 1.2,    # 反弹做多加仓
                },
            },
            
            # 市场状态 → 评分加成
            "regime_score_bonus": {
                MarketRegime.TRENDING_UP: {"SHORT": -10, "LONG": 15},
                MarketRegime.TRENDING_DOWN: {"SHORT": 15, "LONG": -10},
                MarketRegime.RANGING: {"SHORT": 0, "LONG": 0},
                MarketRegime.HIGH_VOLATILITY: {"SHORT": -5, "LONG": -5},
                MarketRegime.CRASH: {"SHORT": -20, "LONG": -20},
                MarketRegime.RECOVERY: {"SHORT": -5, "LONG": 10},
            },
            
            # 乘数上限保护
            "max_multiplier": 2.0,  # 最大乘数不超过2倍
            "min_multiplier": 0.0,  # 最小乘数
            
            # BTC 趋势阈值
            "btc_crash_threshold": -8.0,
            "btc_pump_threshold": 10.0,
            
            # 恐惧贪婪指数阈值
            "fear_greed_extreme_fear": 20,
            "fear_greed_extreme_greed": 80,
        }
    
    def evaluate(
        self,
        direction: str,
        external_data: Optional[Dict] = None,
    ) -> MacroDecision:
        """
        评估宏观环境，生成决策
        
        Args:
            direction: 交易方向 (SHORT/LONG)
            external_data: 外部数据 (btc_trend, fear_greed, etc.)
        
        Returns:
            宏观决策
        """
        # 获取市场状态
        regime = MarketRegime.RANGING
        confidence = 0.5
        
        if self.regime_detector:
            current = self.regime_detector.get_current_regime()
            if current:
                regime = current.regime
                confidence = current.confidence
        
        # 获取外部数据
        btc_trend = external_data.get("btc_trend", 0) if external_data else 0
        fear_greed = external_data.get("fear_greed", 50) if external_data else 50
        
        # 计算仓位乘数
        multiplier_config = self._config["regime_multipliers"].get(regime, {})
        stake_multiplier = multiplier_config.get(direction, 1.0)
        
        # 计算评分加成
        bonus_config = self._config["regime_score_bonus"].get(regime, {})
        score_bonus = bonus_config.get(direction, 0)
        
        # 检查是否允许开仓
        allow_open = True
        reasons = []  # 使用列表累加原因
        
        # 崩盘检查
        if regime == MarketRegime.CRASH:
            allow_open = False
            reasons.append("Market crash detected")
        
        # BTC 极端行情检查
        if btc_trend < self._config["btc_crash_threshold"]:
            stake_multiplier *= 0.5
            score_bonus -= 10
            reasons.append(f"BTC crash: {btc_trend:.1f}%")
        
        if btc_trend > self._config["btc_pump_threshold"]:
            if direction == "SHORT":
                stake_multiplier *= 0.3
                score_bonus -= 15
                reasons.append(f"BTC pump: {btc_trend:.1f}%")
        
        # 恐惧贪婪指数检查
        if fear_greed < self._config["fear_greed_extreme_fear"]:
            if direction == "SHORT":
                stake_multiplier *= 0.5
            elif direction == "LONG":
                stake_multiplier *= 1.2  # 极度恐惧时做多加仓
            reasons.append(f"Extreme fear: {fear_greed}")
        
        if fear_greed > self._config["fear_greed_extreme_greed"]:
            if direction == "LONG":
                stake_multiplier *= 0.5
            reasons.append(f"Extreme greed: {fear_greed}")
        
        # 乘数上限保护
        max_mult = self._config["max_multiplier"]
        min_mult = self._config["min_multiplier"]
        stake_multiplier = max(min(stake_multiplier, max_mult), min_mult)
        
        return MacroDecision(
            regime=regime,
            confidence=confidence,
            stake_multiplier=stake_multiplier,
            score_bonus=score_bonus,
            allow_open=allow_open,
            reason="; ".join(reasons) if reasons else "",
        )
    
    def get_regime_multiplier(self, direction: str) -> float:
        """获取当前市场状态的仓位乘数"""
        if not self.regime_detector:
            return 1.0
        
        current = self.regime_detector.get_current_regime()
        if not current:
            return 1.0
        
        multipliers = self._config["regime_multipliers"].get(current.regime, {})
        return multipliers.get(direction, 1.0)


# 全局单例
_macro_filter: Optional[MacroFilter] = None


def get_macro_filter(regime_detector: Optional[MarketRegimeDetector] = None) -> MacroFilter:
    """获取全局宏观过滤器"""
    global _macro_filter
    if _macro_filter is None:
        _macro_filter = MacroFilter(regime_detector)
    return _macro_filter
