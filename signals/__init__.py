"""
信号处理模块
多因子评分系统
"""

from .factors import FactorRegistry, Factor, FactorCategory
from .scorer import MultiFactorScorer, ScoreResult
from .ic_analyzer import ICAnalyzer, ICResult

__all__ = [
    "FactorRegistry",
    "Factor",
    "FactorCategory",
    "MultiFactorScorer",
    "ScoreResult",
    "ICAnalyzer",
    "ICResult",
]
