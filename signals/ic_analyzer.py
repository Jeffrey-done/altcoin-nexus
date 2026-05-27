"""
因子 IC/IR 分析框架
"""

import logging
import numpy as np
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .factors import FactorRegistry

logger = logging.getLogger("nexus.ic_analyzer")


@dataclass
class ICResult:
    """单因子 IC 分析结果"""
    factor_name: str
    category: str
    
    # IC 统计
    ic_mean: float
    ic_std: float
    ic_ir: float  # IC / IC_std
    
    # 显著性
    t_stat: float
    p_value: float
    is_significant: bool  # |IC| > 0.05
    
    # 方向
    direction: str  # positive / negative / neutral
    
    # 质量评级
    quality: str  # strong / useful / weak / noise
    
    # 样本量
    sample_count: int
    
    # 衰减检测
    is_decaying: bool = False
    recent_ic: float = 0.0  # 最近 N 天的 IC


@dataclass
class ICAnalysisReport:
    """IC 分析报告"""
    timestamp: str
    data_bars: int
    total_factors: int
    useful_factors: int
    
    results: List[ICResult] = field(default_factory=list)
    
    # 汇总统计
    avg_ic: float = 0.0
    avg_ir: float = 0.0
    
    def summary(self) -> str:
        """生成摘要"""
        lines = [
            "=" * 70,
            "  因子 IC/IR 分析报告",
            f"  数据量: {self.data_bars} bars | 因子数: {self.total_factors} | 有效因子: {self.useful_factors}",
            "=" * 70,
            "",
            f"{'因子':<25} {'分类':<12} {'IC均值':>8} {'IR':>6} {'质量':<10} {'方向':<10} {'衰减':<6}",
            "-" * 70,
        ]
        
        for r in sorted(self.results, key=lambda x: abs(x.ic_mean), reverse=True):
            decay_mark = "⚠️" if r.is_decaying else ""
            lines.append(
                f"{r.factor_name:<25} {r.category:<12} {r.ic_mean:>8.4f} {r.ic_ir:>6.2f} "
                f"{r.quality:<10} {r.direction:<10} {decay_mark:<6}"
            )
        
        lines.extend([
            "",
            "-" * 70,
            f"  平均 IC: {self.avg_ic:.4f} | 平均 IR: {self.avg_ir:.2f}",
            "",
            "  解读:",
            "  IC均值: 因子值与未来收益的秩相关 (|IC|>0.05 有用, >0.07 强)",
            "  IR: IC / IC标准差 (IR>0.5 优秀, >1.0 卓越)",
            "  衰减⚠️: 该因子近期 IC 在下降，可能需要降权",
            "=" * 70,
        ])
        
        return "\n".join(lines)
    
    def get_weight_suggestions(self) -> Dict[str, float]:
        """生成权重建议"""
        suggestions = {}
        
        for r in self.results:
            if r.quality == "noise":
                suggestions[r.factor_name] = 0.0
            elif r.is_decaying:
                suggestions[r.factor_name] = 0.5  # 衰减因子降权
            elif r.quality == "strong":
                suggestions[r.factor_name] = abs(r.ic_mean) * (1 + r.ic_ir)
            elif r.quality == "useful":
                suggestions[r.factor_name] = abs(r.ic_mean)
            else:
                suggestions[r.factor_name] = 0.3
        
        return suggestions


class ICAnalyzer:
    """
    因子 IC/IR 分析器
    
    对所有注册因子跑 IC 分析，评估因子有效性
    """
    
    def __init__(self, registry: Optional[FactorRegistry] = None):
        self.registry = registry or FactorRegistry()
        
        # 显著性阈值
        self.significant_threshold = 0.05
        self.strong_threshold = 0.07
        self.ir_excellent = 0.5
        self.decay_window = 20  # 衰减检测窗口
    
    def analyze(
        self,
        ohlcv_data: List[List],
        future_returns: List[float],
        direction: str = "short",
    ) -> ICAnalysisReport:
        """
        执行 IC 分析
        
        Args:
            ohlcv_data: K线数据
            future_returns: 未来收益序列
            direction: 交易方向
        
        Returns:
            分析报告
        """
        results = []
        
        # 计算所有因子
        factor_values = {}
        for name in self.registry.factor_names:
            values = []
            for i in range(len(ohlcv_data)):
                try:
                    v = self.registry.get_factor(name).compute_func(
                        ohlcv_data[:i+1], None
                    )
                    values.append(v)
                except:
                    values.append(0.0)
            factor_values[name] = values
        
        # 对每个因子计算 IC
        for name, values in factor_values.items():
            try:
                ic_result = self._compute_factor_ic(
                    name, values, future_returns, direction
                )
                results.append(ic_result)
                
                # 更新注册中心的 IC 统计
                self.registry.update_ic_stats(name, ic_result.ic_mean)
            
            except Exception as e:
                logger.warning(f"IC analysis failed for {name}: {e}")
        
        # 生成报告
        useful_count = sum(1 for r in results if r.quality != "noise")
        
        avg_ic = np.mean([abs(r.ic_mean) for r in results]) if results else 0
        avg_ir = np.mean([r.ic_ir for r in results if r.quality != "noise"]) if results else 0
        
        report = ICAnalysisReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            data_bars=len(ohlcv_data),
            total_factors=len(results),
            useful_factors=useful_count,
            results=results,
            avg_ic=avg_ic,
            avg_ir=avg_ir,
        )
        
        # 更新因子权重
        self.registry.update_weights()
        
        return report
    
    def _compute_factor_ic(
        self,
        factor_name: str,
        factor_values: List[float],
        future_returns: List[float],
        direction: str,
    ) -> ICResult:
        """计算单因子 IC"""
        factor = self.registry.get_factor(factor_name)
        
        # 对齐长度
        min_len = min(len(factor_values), len(future_returns))
        fv = np.array(factor_values[:min_len])
        fr = np.array(future_returns[:min_len])
        
        # 移除 NaN
        mask = ~(np.isnan(fv) | np.isnan(fr))
        fv = fv[mask]
        fr = fr[mask]
        
        if len(fv) < 10:
            return ICResult(
                factor_name=factor_name,
                category=factor.category.value,
                ic_mean=0, ic_std=0, ic_ir=0,
                t_stat=0, p_value=1, is_significant=False,
                direction="neutral", quality="noise",
                sample_count=len(fv),
            )
        
        # 计算秩相关 (Spearman)
        from scipy import stats
        ic, p_value = stats.spearmanr(fv, fr)
        
        # 计算 IC 统计
        ic_mean = ic
        ic_std = abs(ic) * 0.5  # 简化
        ic_ir = ic_mean / ic_std if ic_std > 0 else 0
        
        # t 检验
        t_stat = ic * np.sqrt((len(fv) - 2) / (1 - ic**2)) if abs(ic) < 1 else 0
        
        # 判断方向
        if direction == "short":
            expected_negative = factor.direction == "negative"
            actual_negative = ic < 0
            is_aligned = expected_negative == actual_negative
        else:
            expected_positive = factor.direction == "positive"
            actual_positive = ic > 0
            is_aligned = expected_positive == actual_positive
        
        if abs(ic) < 0.02:
            direction_str = "neutral"
        elif is_aligned:
            direction_str = "aligned"
        else:
            direction_str = "misaligned"
        
        # 质量评级
        if abs(ic) >= self.strong_threshold and abs(ic_ir) >= self.ir_excellent:
            quality = "strong"
        elif abs(ic) >= self.significant_threshold:
            quality = "useful"
        elif abs(ic) >= 0.02:
            quality = "weak"
        else:
            quality = "noise"
        
        # 衰减检测
        is_decaying = False
        recent_ic = ic
        if len(fv) > self.decay_window * 2:
            old_fv = fv[:-self.decay_window]
            old_fr = fr[:-self.decay_window]
            new_fv = fv[-self.decay_window:]
            new_fr = fr[-self.decay_window:]
            
            if len(old_fv) > 5 and len(new_fv) > 5:
                old_ic, _ = stats.spearmanr(old_fv, old_fr)
                new_ic, _ = stats.spearmanr(new_fv, new_fr)
                recent_ic = new_ic
                
                # 如果新 IC 显著低于旧 IC，判定为衰减
                if old_ic > 0.05 and new_ic < 0.03:
                    is_decaying = True
        
        return ICResult(
            factor_name=factor_name,
            category=factor.category.value,
            ic_mean=ic_mean,
            ic_std=ic_std,
            ic_ir=ic_ir,
            t_stat=t_stat,
            p_value=p_value,
            is_significant=abs(ic) >= self.significant_threshold,
            direction=direction_str,
            quality=quality,
            sample_count=len(fv),
            is_decaying=is_decaying,
            recent_ic=recent_ic,
        )
