"""
蒙特卡洛模拟
评估策略稳健性
"""

import logging
import numpy as np
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger("nexus.backtesting")


@dataclass
class MonteCarloResult:
    """蒙特卡洛模拟结果"""
    # 基础统计
    total_simulations: int
    total_trades_per_sim: int
    
    # 收益统计
    mean_return: float
    median_return: float
    std_return: float
    
    # 分位数
    percentile_5: float    # 5% 分位 (最差情况)
    percentile_25: float
    percentile_75: float
    percentile_95: float   # 95% 分位 (最好情况)
    
    # 风险指标
    max_drawdown_mean: float
    max_drawdown_worst: float
    var_95: float          # 95% VaR
    
    # 胜率
    win_rate_mean: float
    win_rate_std: float
    
    # 盈亏比
    profit_factor_mean: float
    
    # 稳健性评分 (0-100)
    robustness_score: float
    
    # 模拟详情
    simulation_returns: List[float] = field(default_factory=list)
    simulation_drawdowns: List[float] = field(default_factory=list)
    
    def summary(self) -> str:
        """生成摘要"""
        lines = [
            "=" * 60,
            "  蒙特卡洛模拟报告",
            f"  模拟次数: {self.total_simulations} | 每次交易数: {self.total_trades_per_sim}",
            "=" * 60,
            "",
            "  收益统计:",
            f"    均值: {self.mean_return:.2f}%",
            f"    中位数: {self.median_return:.2f}%",
            f"    标准差: {self.std_return:.2f}%",
            "",
            "  分位数:",
            f"    5%分位 (最差): {self.percentile_5:.2f}%",
            f"    25%分位: {self.percentile_25:.2f}%",
            f"    75%分位: {self.percentile_75:.2f}%",
            f"    95%分位 (最好): {self.percentile_95:.2f}%",
            "",
            "  风险指标:",
            f"    平均最大回撤: {self.max_drawdown_mean:.2f}%",
            f"    最差最大回撤: {self.max_drawdown_worst:.2f}%",
            f"    95% VaR: {self.var_95:.2f}%",
            "",
            "  交易统计:",
            f"    平均胜率: {self.win_rate_mean:.1f}% (±{self.win_rate_std:.1f}%)",
            f"    平均盈亏比: {self.profit_factor_mean:.2f}",
            "",
            f"  稳健性评分: {self.robustness_score:.0f}/100",
            "=" * 60,
        ]
        
        return "\n".join(lines)
    
    def is_robust(self, min_score: float = 60) -> bool:
        """判断策略是否稳健"""
        return self.robustness_score >= min_score


class MonteCarloSimulator:
    """
    蒙特卡洛模拟器
    
    通过随机重采样历史交易，评估策略在不同市场条件下的表现
    """
    
    def __init__(self, n_simulations: int = 1000):
        self.n_simulations = n_simulations
    
    def simulate(
        self,
        trades: List[Dict[str, Any]],
        trades_per_sim: Optional[int] = None,
    ) -> MonteCarloResult:
        """
        运行蒙特卡洛模拟
        
        Args:
            trades: 历史交易列表
            trades_per_sim: 每次模拟的交易数 (默认=len(trades))
        
        Returns:
            模拟结果
        """
        if not trades:
            return self._empty_result()
        
        # 提取收益序列
        returns = []
        for trade in trades:
            pnl = (trade.get("tp1_locked_pnl", 0) or 0) + (trade.get("pnl", 0) or 0)
            stake = trade.get("stake", 1)
            ret = pnl / stake * 100 if stake > 0 else 0
            returns.append(ret)
        
        returns = np.array(returns)
        
        if trades_per_sim is None:
            trades_per_sim = len(returns)
        
        # 运行模拟
        sim_returns = []
        sim_drawdowns = []
        sim_win_rates = []
        sim_profit_factors = []
        
        for _ in range(self.n_simulations):
            # 随机重采样
            sampled = np.random.choice(returns, size=trades_per_sim, replace=True)
            
            # 计算累计收益
            cumulative = np.cumsum(sampled)
            
            # 计算最大回撤
            running_max = np.maximum.accumulate(cumulative)
            drawdown = running_max - cumulative
            max_drawdown = drawdown.max()
            
            # 计算胜率
            win_rate = (sampled > 0).sum() / len(sampled) * 100
            
            # 计算盈亏比
            wins = sampled[sampled > 0]
            losses = sampled[sampled < 0]
            avg_win = wins.mean() if len(wins) > 0 else 0
            avg_loss = abs(losses.mean()) if len(losses) > 0 else 1
            profit_factor = avg_win / avg_loss if avg_loss > 0 else 0
            
            sim_returns.append(cumulative[-1])
            sim_drawdowns.append(max_drawdown)
            sim_win_rates.append(win_rate)
            sim_profit_factors.append(profit_factor)
        
        sim_returns = np.array(sim_returns)
        sim_drawdowns = np.array(sim_drawdowns)
        sim_win_rates = np.array(sim_win_rates)
        sim_profit_factors = np.array(sim_profit_factors)
        
        # 计算稳健性评分
        robustness_score = self._calculate_robustness(
            sim_returns, sim_drawdowns, sim_win_rates
        )
        
        return MonteCarloResult(
            total_simulations=self.n_simulations,
            total_trades_per_sim=trades_per_sim,
            mean_return=float(sim_returns.mean()),
            median_return=float(np.median(sim_returns)),
            std_return=float(sim_returns.std()),
            percentile_5=float(np.percentile(sim_returns, 5)),
            percentile_25=float(np.percentile(sim_returns, 25)),
            percentile_75=float(np.percentile(sim_returns, 75)),
            percentile_95=float(np.percentile(sim_returns, 95)),
            max_drawdown_mean=float(sim_drawdowns.mean()),
            max_drawdown_worst=float(sim_drawdowns.max()),
            var_95=float(np.percentile(sim_returns, 5)),
            win_rate_mean=float(sim_win_rates.mean()),
            win_rate_std=float(sim_win_rates.std()),
            profit_factor_mean=float(sim_profit_factors.mean()),
            robustness_score=robustness_score,
            simulation_returns=sim_returns.tolist(),
            simulation_drawdowns=sim_drawdowns.tolist(),
        )
    
    def _calculate_robustness(
        self,
        returns: np.ndarray,
        drawdowns: np.ndarray,
        win_rates: np.ndarray,
    ) -> float:
        """
        计算稳健性评分 (0-100)
        
        评分维度：
        1. 正收益概率 (30分)
        2. 回撤控制 (30分)
        3. 胜率稳定性 (20分)
        4. 收益稳定性 (20分)
        """
        score = 0.0
        
        # 1. 正收益概率
        positive_rate = (returns > 0).sum() / len(returns)
        score += positive_rate * 30
        
        # 2. 回撤控制
        avg_drawdown = drawdowns.mean()
        if avg_drawdown < 5:
            score += 30
        elif avg_drawdown < 10:
            score += 25
        elif avg_drawdown < 15:
            score += 20
        elif avg_drawdown < 20:
            score += 15
        else:
            score += 10
        
        # 3. 胜率稳定性
        win_rate_cv = win_rates.std() / win_rates.mean() if win_rates.mean() > 0 else 1
        if win_rate_cv < 0.1:
            score += 20
        elif win_rate_cv < 0.2:
            score += 15
        elif win_rate_cv < 0.3:
            score += 10
        else:
            score += 5
        
        # 4. 收益稳定性
        return_cv = returns.std() / abs(returns.mean()) if returns.mean() != 0 else 1
        if return_cv < 0.5:
            score += 20
        elif return_cv < 1.0:
            score += 15
        elif return_cv < 1.5:
            score += 10
        else:
            score += 5
        
        return min(score, 100)
    
    def _empty_result(self) -> MonteCarloResult:
        """空结果"""
        return MonteCarloResult(
            total_simulations=0,
            total_trades_per_sim=0,
            mean_return=0, median_return=0, std_return=0,
            percentile_5=0, percentile_25=0, percentile_75=0, percentile_95=0,
            max_drawdown_mean=0, max_drawdown_worst=0, var_95=0,
            win_rate_mean=0, win_rate_std=0, profit_factor_mean=0,
            robustness_score=0,
        )
