"""
多因子评分器
基于 IC 加权的信号评分
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from .factors import FactorRegistry, FactorCategory

logger = logging.getLogger("nexus.scorer")


@dataclass
class ScoreResult:
    """评分结果"""
    symbol: str
    direction: str
    total_score: int  # 0-100
    grade: str        # A / B / C / SKIP
    
    # 分项得分
    momentum_score: float = 0.0
    volatility_score: float = 0.0
    volume_score: float = 0.0
    trend_score: float = 0.0
    micro_score: float = 0.0
    sentiment_score: float = 0.0
    
    # 因子详情
    factor_values: Dict[str, float] = field(default_factory=dict)
    factor_scores: Dict[str, float] = field(default_factory=dict)
    factor_weights: Dict[str, float] = field(default_factory=dict)
    
    # 元数据
    source: str = "multifactor"  # linear / multifactor / ml
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "total_score": self.total_score,
            "grade": self.grade,
            "momentum_score": self.momentum_score,
            "volatility_score": self.volatility_score,
            "volume_score": self.volume_score,
            "trend_score": self.trend_score,
            "micro_score": self.micro_score,
            "sentiment_score": self.sentiment_score,
            "factor_values": self.factor_values,
            "factor_scores": self.factor_scores,
            "factor_weights": self.factor_weights,
            "source": self.source,
            "confidence": self.confidence,
        }


class MultiFactorScorer:
    """
    多因子评分器
    
    基于 IC 加权的信号评分系统：
    1. 计算所有因子值
    2. 基于历史 IC 值加权
    3. 输出综合评分和等级
    """
    
    def __init__(self, registry: Optional[FactorRegistry] = None):
        self.registry = registry or FactorRegistry()
        
        # 评分阈值
        self.grade_a_threshold = 80
        self.grade_b_threshold = 60
        self.skip_threshold = 40
    
    def score(
        self,
        symbol: str,
        direction: str,
        ohlcv: List[List],
        external_data: Optional[Dict] = None,
    ) -> ScoreResult:
        """
        计算多因子评分
        
        Args:
            symbol: 交易对
            direction: 方向 (SHORT/LONG)
            ohlcv: K线数据
            external_data: 外部数据
        
        Returns:
            评分结果
        """
        # 1. 计算所有因子值
        factor_values = self.registry.compute_all(ohlcv, external_data)
        
        # 2. 按分类汇总
        category_scores = {cat: 0.0 for cat in FactorCategory}
        category_weights = {cat: 0.0 for cat in FactorCategory}
        
        factor_scores = {}
        factor_weights = {}
        
        for name, value in factor_values.items():
            factor = self.registry.get_factor(name)
            if not factor:
                continue
            
            # 计算因子得分 (标准化到 0-100)
            score = self._normalize_factor_score(factor, value, direction)
            
            # 加权
            weight = factor.weight
            
            factor_scores[name] = score
            factor_weights[name] = weight
            
            # 按分类累加
            category_scores[factor.category] += score * weight
            category_weights[factor.category] += weight
        
        # 3. 计算分类得分
        category_final = {}
        for cat in FactorCategory:
            if category_weights[cat] > 0:
                category_final[cat] = category_scores[cat] / category_weights[cat]
            else:
                category_final[cat] = 50.0  # 默认值
        
        # 4. 计算总分 (各分类加权)
        category_weight_map = {
            FactorCategory.MOMENTUM: 0.30,
            FactorCategory.VOLATILITY: 0.15,
            FactorCategory.VOLUME: 0.15,
            FactorCategory.TREND: 0.15,
            FactorCategory.MICROSTRUCTURE: 0.15,
            FactorCategory.SENTIMENT: 0.05,
            FactorCategory.FUNDAMENTAL: 0.05,
        }
        
        total_score = sum(
            category_final[cat] * category_weight_map[cat]
            for cat in FactorCategory
        )
        
        # 5. 确定等级
        grade = self._determine_grade(total_score)
        
        # 6. 计算置信度
        confidence = self._calculate_confidence(factor_values, factor_weights)
        
        return ScoreResult(
            symbol=symbol,
            direction=direction,
            total_score=int(total_score),
            grade=grade,
            momentum_score=category_final.get(FactorCategory.MOMENTUM, 0),
            volatility_score=category_final.get(FactorCategory.VOLATILITY, 0),
            volume_score=category_final.get(FactorCategory.VOLUME, 0),
            trend_score=category_final.get(FactorCategory.TREND, 0),
            micro_score=category_final.get(FactorCategory.MICROSTRUCTURE, 0),
            sentiment_score=category_final.get(FactorCategory.SENTIMENT, 0),
            factor_values=factor_values,
            factor_scores=factor_scores,
            factor_weights=factor_weights,
            source="multifactor",
            confidence=confidence,
        )
    
    def _normalize_factor_score(
        self,
        factor,
        value: float,
        direction: str,
    ) -> float:
        """
        标准化因子得分
        
        将原始因子值转换为 0-100 分
        """
        # 根据因子方向和交易方向调整
        is_aligned = (factor.direction == "negative" and direction == "SHORT") or \
                     (factor.direction == "positive" and direction == "LONG")
        
        # RSI 特殊处理
        if "rsi" in factor.name:
            if direction == "SHORT":
                # 做空：RSI 越高分越高
                return min(value, 100)
            else:
                # 做多：RSI 越低分越高
                return max(100 - value, 0)
        
        # 涨跌幅特殊处理
        if "pct" in factor.name or "momentum" in factor.name:
            if direction == "SHORT":
                # 做空：涨幅越大分越高
                return min(max(value * 5 + 50, 0), 100)
            else:
                # 做多：跌幅越大分越高
                return min(max(-value * 5 + 50, 0), 100)
        
        # 资金费率特殊处理
        if "funding" in factor.name:
            if direction == "SHORT":
                # 做空：费率越高分越高
                return min(max(value * 10000 + 50, 0), 100)
            else:
                # 做多：费率越低分越高
                return min(max(-value * 10000 + 50, 0), 100)
        
        # 通用处理：标准化到 0-100
        # 这里简化处理，实际应该基于历史分布
        return min(max(value * 10 + 50, 0), 100)
    
    def _determine_grade(self, score: float) -> str:
        """确定等级"""
        if score >= self.grade_a_threshold:
            return "A"
        elif score >= self.grade_b_threshold:
            return "B"
        elif score >= self.skip_threshold:
            return "C"
        return "SKIP"
    
    def _calculate_confidence(
        self,
        factor_values: Dict[str, float],
        factor_weights: Dict[str, float],
    ) -> float:
        """计算置信度"""
        if not factor_weights:
            return 0.0
        
        # 基于有效因子数量和权重分布
        valid_factors = sum(1 for w in factor_weights.values() if w > 0)
        total_weight = sum(factor_weights.values())
        
        if total_weight == 0:
            return 0.0
        
        # 归一化权重
        normalized_weights = [w / total_weight for w in factor_weights.values() if w > 0]
        
        # 权重分散度 (越集中置信度越高)
        import numpy as np
        weight_entropy = -sum(w * np.log(w) for w in normalized_weights if w > 0)
        max_entropy = np.log(len(normalized_weights)) if normalized_weights else 1
        
        confidence = 1 - (weight_entropy / max_entropy) if max_entropy > 0 else 0
        
        return round(confidence, 2)


def score_signal_multifactor(
    ohlcv: List[List],
    symbol: str = "",
    direction: str = "SHORT",
    external_data: Optional[Dict] = None,
) -> ScoreResult:
    """
    多因子评分入口函数
    
    与旧系统兼容的接口
    """
    scorer = MultiFactorScorer()
    return scorer.score(symbol, direction, ohlcv, external_data)
