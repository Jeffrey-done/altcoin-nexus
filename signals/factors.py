"""
因子库 - 30+ 量化因子
"""

import numpy as np
import pandas as pd
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field


class FactorCategory(str, Enum):
    """因子分类"""
    MOMENTUM = "momentum"        # 动量因子
    VOLATILITY = "volatility"    # 波动率因子
    VOLUME = "volume"            # 成交量因子
    TREND = "trend"              # 趋势因子
    MICROSTRUCTURE = "micro"     # 微观结构因子
    SENTIMENT = "sentiment"      # 情绪因子
    FUNDAMENTAL = "fundamental"  # 基本面因子


@dataclass
class Factor:
    """因子定义"""
    name: str
    category: FactorCategory
    description: str
    compute_func: callable
    direction: str = "positive"  # positive: 因子高→收益高; negative: 因子高→收益低
    
    # IC 统计（动态更新）
    ic_mean: float = 0.0
    ic_std: float = 0.0
    ic_ir: float = 0.0
    weight: float = 1.0
    sample_count: int = 0


class FactorRegistry:
    """
    因子注册中心
    
    管理所有因子的注册、计算和权重更新
    """
    
    def __init__(self):
        self._factors: Dict[str, Factor] = {}
        self._register_default_factors()
    
    def _register_default_factors(self) -> None:
        """注册默认因子"""
        
        # ==================== 动量因子 ====================
        self.register(Factor(
            name="rsi_1d",
            category=FactorCategory.MOMENTUM,
            description="日线 RSI",
            compute_func=self._compute_rsi_1d,
            direction="negative",  # RSI 高→做空机会
        ))
        
        self.register(Factor(
            name="rsi_4h",
            category=FactorCategory.MOMENTUM,
            description="4小时 RSI",
            compute_func=self._compute_rsi_4h,
            direction="negative",
        ))
        
        self.register(Factor(
            name="rsi_4h_peak",
            category=FactorCategory.MOMENTUM,
            description="4小时 RSI 峰值",
            compute_func=self._compute_rsi_4h_peak,
            direction="negative",
        ))
        
        self.register(Factor(
            name="pct_24h",
            category=FactorCategory.MOMENTUM,
            description="24小时涨幅",
            compute_func=self._compute_pct_24h,
            direction="negative",  # 涨幅高→做空机会
        ))
        
        self.register(Factor(
            name="pct_7d",
            category=FactorCategory.MOMENTUM,
            description="7天涨幅",
            compute_func=self._compute_pct_7d,
            direction="negative",
        ))
        
        self.register(Factor(
            name="momentum_3d",
            category=FactorCategory.MOMENTUM,
            description="3天动量",
            compute_func=self._compute_momentum_3d,
            direction="negative",
        ))
        
        # ==================== 波动率因子 ====================
        self.register(Factor(
            name="volatility_24h",
            category=FactorCategory.VOLATILITY,
            description="24小时波动率",
            compute_func=self._compute_volatility_24h,
            direction="positive",
        ))
        
        self.register(Factor(
            name="atr_14",
            category=FactorCategory.VOLATILITY,
            description="14周期 ATR",
            compute_func=self._compute_atr_14,
            direction="positive",
        ))
        
        self.register(Factor(
            name="bb_width",
            category=FactorCategory.VOLATILITY,
            description="布林带宽度",
            compute_func=self._compute_bb_width,
            direction="positive",
        ))
        
        self.register(Factor(
            name="range_pct",
            category=FactorCategory.VOLATILITY,
            description="日振幅百分比",
            compute_func=self._compute_range_pct,
            direction="positive",
        ))
        
        # ==================== 成交量因子 ====================
        self.register(Factor(
            name="vol_24h",
            category=FactorCategory.VOLUME,
            description="24小时成交量",
            compute_func=self._compute_vol_24h,
            direction="positive",
        ))
        
        self.register(Factor(
            name="vol_ratio",
            category=FactorCategory.VOLUME,
            description="成交量比率 (vs 7d avg)",
            compute_func=self._compute_vol_ratio,
            direction="positive",
        ))
        
        self.register(Factor(
            name="vol_divergence",
            category=FactorCategory.VOLUME,
            description="量价背离",
            compute_func=self._compute_vol_divergence,
            direction="negative",
        ))
        
        self.register(Factor(
            name="buy_sell_ratio",
            category=FactorCategory.VOLUME,
            description="买卖量比",
            compute_func=self._compute_buy_sell_ratio,
            direction="negative",
        ))
        
        # ==================== 趋势因子 ====================
        self.register(Factor(
            name="ma_cross",
            category=FactorCategory.TREND,
            description="均线交叉 (MA5/MA20)",
            compute_func=self._compute_ma_cross,
            direction="negative",
        ))
        
        self.register(Factor(
            name="trend_strength",
            category=FactorCategory.TREND,
            description="趋势强度 (ADX)",
            compute_func=self._compute_trend_strength,
            direction="positive",
        ))
        
        self.register(Factor(
            name="price_position",
            category=FactorCategory.TREND,
            description="价格位置 (相对高低)",
            compute_func=self._compute_price_position,
            direction="negative",
        ))
        
        # ==================== 微观结构因子 ====================
        self.register(Factor(
            name="funding_rate",
            category=FactorCategory.MICROSTRUCTURE,
            description="资金费率",
            compute_func=self._compute_funding_rate,
            direction="negative",  # 费率高→做空机会
        ))
        
        self.register(Factor(
            name="oi_change",
            category=FactorCategory.MICROSTRUCTURE,
            description="持仓量变化",
            compute_func=self._compute_oi_change,
            direction="positive",
        ))
        
        self.register(Factor(
            name="open_interest",
            category=FactorCategory.MICROSTRUCTURE,
            description="持仓量",
            compute_func=self._compute_open_interest,
            direction="positive",
        ))
        
        self.register(Factor(
            name="liquidation_ratio",
            category=FactorCategory.MICROSTRUCTURE,
            description="爆仓比率",
            compute_func=self._compute_liquidation_ratio,
            direction="positive",
        ))
        
        # ==================== 情绪因子 ====================
        self.register(Factor(
            name="fear_greed_index",
            category=FactorCategory.SENTIMENT,
            description="恐惧贪婪指数",
            compute_func=self._compute_fear_greed,
            direction="negative",
        ))
        
        self.register(Factor(
            name="btc_dominance",
            category=FactorCategory.SENTIMENT,
            description="BTC 市值占比",
            compute_func=self._compute_btc_dominance,
            direction="positive",
        ))
        
        self.register(Factor(
            name="social_volume",
            category=FactorCategory.SENTIMENT,
            description="社交热度",
            compute_func=self._compute_social_volume,
            direction="negative",
        ))
        
        # ==================== 基本面因子 ====================
        self.register(Factor(
            name="market_cap",
            category=FactorCategory.FUNDAMENTAL,
            description="市值",
            compute_func=self._compute_market_cap,
            direction="positive",
        ))
        
        self.register(Factor(
            name="age_days",
            category=FactorCategory.FUNDAMENTAL,
            description="上市天数",
            compute_func=self._compute_age_days,
            direction="positive",
        ))
    
    def register(self, factor: Factor) -> None:
        """注册因子"""
        self._factors[factor.name] = factor
    
    def get_factor(self, name: str) -> Optional[Factor]:
        """获取因子"""
        return self._factors.get(name)
    
    def get_all_factors(self) -> Dict[str, Factor]:
        """获取所有因子"""
        return self._factors.copy()
    
    def get_factors_by_category(self, category: FactorCategory) -> List[Factor]:
        """按分类获取因子"""
        return [f for f in self._factors.values() if f.category == category]
    
    @property
    def factor_names(self) -> List[str]:
        """获取所有因子名称"""
        return list(self._factors.keys())
    
    def compute_all(
        self,
        ohlcv: List[List],
        external_data: Optional[Dict] = None,
    ) -> Dict[str, float]:
        """
        计算所有因子值
        
        Args:
            ohlcv: K线数据 [[timestamp, open, high, low, close, volume], ...]
            external_data: 外部数据 (funding_rate, oi, etc.)
        
        Returns:
            {factor_name: value}
        """
        results = {}
        
        for name, factor in self._factors.items():
            try:
                value = factor.compute_func(ohlcv, external_data)
                results[name] = value
            except Exception as e:
                results[name] = 0.0
        
        return results
    
    def update_ic_stats(
        self,
        factor_name: str,
        ic_value: float,
    ) -> None:
        """更新因子 IC 统计"""
        factor = self._factors.get(factor_name)
        if not factor:
            return
        
        # 增量更新均值和标准差
        n = factor.sample_count + 1
        old_mean = factor.ic_mean
        
        factor.ic_mean = old_mean + (ic_value - old_mean) / n
        factor.ic_std = ((factor.ic_std ** 2 * (n - 1) + (ic_value - old_mean) * (ic_value - factor.ic_mean)) / n) ** 0.5
        factor.sample_count = n
        
        # 计算 IR
        if factor.ic_std > 0:
            factor.ic_ir = factor.ic_mean / factor.ic_std
    
    def update_weights(self, min_samples: int = 30) -> None:
        """
        基于 IC 统计更新因子权重
        
        权重 = |IC_mean| * IC_IR (如果样本足够)
        """
        for factor in self._factors.values():
            if factor.sample_count < min_samples:
                factor.weight = 1.0
                continue
            
            # 权重 = |IC_mean| * (1 + IC_IR)
            factor.weight = abs(factor.ic_mean) * (1 + max(factor.ic_ir, 0))
    
    # ==================== 因子计算函数 ====================
    
    def _compute_rsi_1d(self, ohlcv: List[List], ext: Optional[Dict]) -> float:
        """日线 RSI"""
        if len(ohlcv) < 15:
            return 50.0
        closes = [c[4] for c in ohlcv]
        return self._rsi(closes, 14)
    
    def _compute_rsi_4h(self, ohlcv: List[List], ext: Optional[Dict]) -> float:
        """4小时 RSI"""
        if len(ohlcv) < 15:
            return 50.0
        closes = [c[4] for c in ohlcv[-50:]]
        return self._rsi(closes, 14)
    
    def _compute_rsi_4h_peak(self, ohlcv: List[List], ext: Optional[Dict]) -> float:
        """4小时 RSI 峰值"""
        if len(ohlcv) < 50:
            return 50.0
        closes = [c[4] for c in ohlcv[-50:]]
        rsi_values = []
        for i in range(14, len(closes)):
            rsi_values.append(self._rsi(closes[:i+1], 14))
        return max(rsi_values) if rsi_values else 50.0
    
    def _compute_pct_24h(self, ohlcv: List[List], ext: Optional[Dict]) -> float:
        """24小时涨幅"""
        if len(ohlcv) < 2:
            return 0.0
        return (ohlcv[-1][4] - ohlcv[-2][4]) / ohlcv[-2][4] * 100
    
    def _compute_pct_7d(self, ohlcv: List[List], ext: Optional[Dict]) -> float:
        """7天涨幅"""
        if len(ohlcv) < 7:
            return 0.0
        return (ohlcv[-1][4] - ohlcv[-7][4]) / ohlcv[-7][4] * 100
    
    def _compute_momentum_3d(self, ohlcv: List[List], ext: Optional[Dict]) -> float:
        """3天动量"""
        if len(ohlcv) < 3:
            return 0.0
        returns = [(ohlcv[i][4] - ohlcv[i-1][4]) / ohlcv[i-1][4] 
                   for i in range(-2, 0)]
        return sum(returns) * 100
    
    def _compute_volatility_24h(self, ohlcv: List[List], ext: Optional[Dict]) -> float:
        """24小时波动率"""
        if len(ohlcv) < 24:
            return 0.0
        closes = [c[4] for c in ohlcv[-24:]]
        returns = [(closes[i] - closes[i-1]) / closes[i-1] 
                   for i in range(1, len(closes))]
        import numpy as np
        return float(np.std(returns) * 100)
    
    def _compute_atr_14(self, ohlcv: List[List], ext: Optional[Dict]) -> float:
        """14周期 ATR"""
        if len(ohlcv) < 15:
            return 0.0
        tr_values = []
        for i in range(1, len(ohlcv)):
            high = ohlcv[i][2]
            low = ohlcv[i][3]
            prev_close = ohlcv[i-1][4]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_values.append(tr)
        return sum(tr_values[-14:]) / 14
    
    def _compute_bb_width(self, ohlcv: List[List], ext: Optional[Dict]) -> float:
        """布林带宽度"""
        if len(ohlcv) < 20:
            return 0.0
        closes = [c[4] for c in ohlcv[-20:]]
        import numpy as np
        std = np.std(closes)
        mean = np.mean(closes)
        return (std * 2 / mean * 100) if mean > 0 else 0.0
    
    def _compute_range_pct(self, ohlcv: List[List], ext: Optional[Dict]) -> float:
        """日振幅百分比"""
        if not ohlcv:
            return 0.0
        high = ohlcv[-1][2]
        low = ohlcv[-1][3]
        close = ohlcv[-1][4]
        return ((high - low) / close * 100) if close > 0 else 0.0
    
    def _compute_vol_24h(self, ohlcv: List[List], ext: Optional[Dict]) -> float:
        """24小时成交量"""
        if not ohlcv:
            return 0.0
        return ohlcv[-1][5]
    
    def _compute_vol_ratio(self, ohlcv: List[List], ext: Optional[Dict]) -> float:
        """成交量比率"""
        if len(ohlcv) < 7:
            return 1.0
        recent_vol = ohlcv[-1][5]
        avg_vol = sum(c[5] for c in ohlcv[-7:]) / 7
        return (recent_vol / avg_vol) if avg_vol > 0 else 1.0
    
    def _compute_vol_divergence(self, ohlcv: List[List], ext: Optional[Dict]) -> float:
        """量价背离"""
        if len(ohlcv) < 5:
            return 0.0
        price_change = (ohlcv[-1][4] - ohlcv[-5][4]) / ohlcv[-5][4]
        vol_change = (ohlcv[-1][5] - ohlcv[-5][5]) / ohlcv[-5][5] if ohlcv[-5][5] > 0 else 0
        return price_change - vol_change
    
    def _compute_buy_sell_ratio(self, ohlcv: List[List], ext: Optional[Dict]) -> float:
        """买卖量比 (简化)"""
        if not ohlcv:
            return 1.0
        # 用收盘价相对高低估算
        close = ohlcv[-1][4]
        high = ohlcv[-1][2]
        low = ohlcv[-1][3]
        if high == low:
            return 1.0
        return (close - low) / (high - low)
    
    def _compute_ma_cross(self, ohlcv: List[List], ext: Optional[Dict]) -> float:
        """均线交叉"""
        if len(ohlcv) < 20:
            return 0.0
        closes = [c[4] for c in ohlcv]
        ma5 = sum(closes[-5:]) / 5
        ma20 = sum(closes[-20:]) / 20
        return ((ma5 - ma20) / ma20 * 100) if ma20 > 0 else 0.0
    
    def _compute_trend_strength(self, ohlcv: List[List], ext: Optional[Dict]) -> float:
        """趋势强度 (简化 ADX)"""
        if len(ohlcv) < 14:
            return 0.0
        closes = [c[4] for c in ohlcv[-14:]]
        up_moves = [closes[i] - closes[i-1] for i in range(1, len(closes)) if closes[i] > closes[i-1]]
        down_moves = [closes[i-1] - closes[i] for i in range(1, len(closes)) if closes[i] < closes[i-1]]
        avg_up = sum(up_moves) / len(up_moves) if up_moves else 0
        avg_down = sum(down_moves) / len(down_moves) if down_moves else 0
        if avg_up + avg_down == 0:
            return 0.0
        return abs(avg_up - avg_down) / (avg_up + avg_down) * 100
    
    def _compute_price_position(self, ohlcv: List[List], ext: Optional[Dict]) -> float:
        """价格位置"""
        if len(ohlcv) < 20:
            return 0.5
        closes = [c[4] for c in ohlcv[-20:]]
        current = closes[-1]
        min_price = min(closes)
        max_price = max(closes)
        if max_price == min_price:
            return 0.5
        return (current - min_price) / (max_price - min_price)
    
    def _compute_funding_rate(self, ohlcv: List[List], ext: Optional[Dict]) -> float:
        """资金费率"""
        if ext and "funding_rate" in ext:
            return ext["funding_rate"]
        return 0.0
    
    def _compute_oi_change(self, ohlcv: List[List], ext: Optional[Dict]) -> float:
        """持仓量变化"""
        if ext and "oi_change" in ext:
            return ext["oi_change"]
        return 0.0
    
    def _compute_open_interest(self, ohlcv: List[List], ext: Optional[Dict]) -> float:
        """持仓量"""
        if ext and "open_interest" in ext:
            return ext["open_interest"]
        return 0.0
    
    def _compute_liquidation_ratio(self, ohlcv: List[List], ext: Optional[Dict]) -> float:
        """爆仓比率"""
        if ext and "liquidation_ratio" in ext:
            return ext["liquidation_ratio"]
        return 0.0
    
    def _compute_fear_greed(self, ohlcv: List[List], ext: Optional[Dict]) -> float:
        """恐惧贪婪指数"""
        if ext and "fear_greed" in ext:
            return ext["fear_greed"]
        return 50.0
    
    def _compute_btc_dominance(self, ohlcv: List[List], ext: Optional[Dict]) -> float:
        """BTC 市值占比"""
        if ext and "btc_dominance" in ext:
            return ext["btc_dominance"]
        return 50.0
    
    def _compute_social_volume(self, ohlcv: List[List], ext: Optional[Dict]) -> float:
        """社交热度"""
        if ext and "social_volume" in ext:
            return ext["social_volume"]
        return 0.0
    
    def _compute_market_cap(self, ohlcv: List[List], ext: Optional[Dict]) -> float:
        """市值"""
        if ext and "market_cap" in ext:
            return ext["market_cap"]
        return 0.0
    
    def _compute_age_days(self, ohlcv: List[List], ext: Optional[Dict]) -> float:
        """上市天数"""
        if ext and "age_days" in ext:
            return ext["age_days"]
        return 0.0
    
    def _rsi(self, closes: List[float], period: int = 14) -> float:
        """计算 RSI"""
        if len(closes) < period + 1:
            return 50.0
        
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
