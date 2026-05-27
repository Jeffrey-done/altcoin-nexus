"""
统一信号评分入口
优先级: ml > multifactor > linear
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from signals.factors import FactorRegistry
from signals.scorer import MultiFactorScorer, ScoreResult

logger = logging.getLogger("nexus.scoring")


@dataclass
class UnifiedScoreResult:
    """统一评分结果"""
    symbol: str
    direction: str
    score: int
    grade: str
    source: str  # ml / multifactor / linear
    
    # 详细信息
    ml_result: Optional[Dict] = None
    multifactor_result: Optional[ScoreResult] = None
    linear_result: Optional[Dict] = None
    
    # 置信度
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "score": self.score,
            "grade": self.grade,
            "source": self.source,
            "confidence": self.confidence,
            "ml": self.ml_result,
            "multifactor": self.multifactor_result.to_dict() if self.multifactor_result else None,
            "linear": self.linear_result,
        }


class UnifiedScorer:
    """
    统一评分器
    
    按优先级尝试不同评分方法:
    1. ML (XGBoost) - 最高优先级
    2. Multifactor (IC加权) - 次优先级
    3. Linear (硬编码权重) - 兜底
    """
    
    def __init__(self):
        self._factor_registry = FactorRegistry()
        self._multifactor_scorer = MultiFactorScorer(self._factor_registry)
        self._ml_scorer = None
        
        # 尝试加载 ML 模型
        try:
            from ml.model import MLScorer, MLModel
            self._ml_scorer = MLScorer(MLModel())
        except Exception as e:
            logger.info(f"ML scorer not available: {e}")
    
    def score(
        self,
        symbol: str,
        direction: str,
        ohlcv: List[List],
        external_data: Optional[Dict] = None,
        prefer: str = "auto",
    ) -> UnifiedScoreResult:
        """
        统一评分
        
        Args:
            symbol: 交易对
            direction: 方向 (SHORT/LONG)
            ohlcv: K线数据
            external_data: 外部数据
            prefer: 偏好 ('auto' | 'ml' | 'multifactor' | 'linear')
        
        Returns:
            统一评分结果
        """
        ml_result = None
        multifactor_result = None
        linear_result = None
        
        # 1. 尝试 ML
        if prefer in ("auto", "ml") and self._ml_scorer:
            try:
                ml_result = self._ml_scorer.score(ohlcv, external_data)
                if ml_result and ml_result.get("confidence", 0) > 0.6:
                    return UnifiedScoreResult(
                        symbol=symbol,
                        direction=direction,
                        score=ml_result["score"],
                        grade=self._determine_grade(ml_result["score"]),
                        source="ml",
                        ml_result=ml_result,
                        confidence=ml_result["confidence"],
                    )
            except Exception as e:
                logger.debug(f"ML scoring failed: {e}")
        
        # 2. 尝试多因子
        if prefer in ("auto", "multifactor"):
            try:
                multifactor_result = self._multifactor_scorer.score(
                    symbol, direction, ohlcv, external_data
                )
                
                if multifactor_result and multifactor_result.confidence > 0.5:
                    return UnifiedScoreResult(
                        symbol=symbol,
                        direction=direction,
                        score=multifactor_result.total_score,
                        grade=multifactor_result.grade,
                        source="multifactor",
                        ml_result=ml_result,
                        multifactor_result=multifactor_result,
                        confidence=multifactor_result.confidence,
                    )
            except Exception as e:
                logger.debug(f"Multifactor scoring failed: {e}")
        
        # 3. 线性评分 (兜底)
        linear_result = self._linear_score(ohlcv, direction)
        
        return UnifiedScoreResult(
            symbol=symbol,
            direction=direction,
            score=linear_result["score"],
            grade=self._determine_grade(linear_result["score"]),
            source="linear",
            ml_result=ml_result,
            multifactor_result=multifactor_result,
            linear_result=linear_result,
            confidence=0.3,
        )
    
    def _linear_score(
        self,
        ohlcv: List[List],
        direction: str,
    ) -> Dict[str, Any]:
        """线性评分 (简单 RSI + 涨幅)"""
        if len(ohlcv) < 14:
            return {"score": 50, "rsi": 50, "pct_24h": 0}
        
        closes = [c[4] for c in ohlcv]
        
        # RSI
        rsi = self._rsi(closes, 14)
        
        # 24h 涨幅
        pct_24h = (closes[-1] - closes[-2]) / closes[-2] * 100 if len(closes) > 1 else 0
        
        # 评分
        score = 0
        
        if direction == "SHORT":
            # 做空：RSI 越高分越高
            if rsi >= 80:
                score += 40
            elif rsi >= 70:
                score += 30
            elif rsi >= 65:
                score += 20
            
            # 涨幅越大分越高
            if pct_24h >= 20:
                score += 30
            elif pct_24h >= 10:
                score += 20
            elif pct_24h >= 5:
                score += 10
        else:
            # 做多：RSI 越低分越高
            if rsi <= 20:
                score += 40
            elif rsi <= 30:
                score += 30
            elif rsi <= 35:
                score += 20
            
            # 跌幅越大分越高
            if pct_24h <= -20:
                score += 30
            elif pct_24h <= -10:
                score += 20
            elif pct_24h <= -5:
                score += 10
        
        return {"score": score, "rsi": rsi, "pct_24h": pct_24h}
    
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
    
    def _determine_grade(self, score: int) -> str:
        """确定等级"""
        if score >= 80:
            return "A"
        elif score >= 60:
            return "B"
        elif score >= 40:
            return "C"
        return "SKIP"


# 全局单例
_scorer: Optional[UnifiedScorer] = None


def get_scorer() -> UnifiedScorer:
    """获取全局评分器"""
    global _scorer
    if _scorer is None:
        _scorer = UnifiedScorer()
    return _scorer


def score_signal(
    symbol: str,
    direction: str,
    ohlcv: List[List],
    external_data: Optional[Dict] = None,
    prefer: str = "auto",
) -> UnifiedScoreResult:
    """
    统一评分入口函数
    
    用法:
        from scoring import score_signal
        result = score_signal("PEPE/USDT", "SHORT", ohlcv_data)
    """
    return get_scorer().score(symbol, direction, ohlcv, external_data, prefer)
