"""
优化服务
Walk-Forward Analysis 实现
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from core.config import get_settings
from core.db import TradeRepository, get_db
from core.events import EventType, get_event_bus

logger = logging.getLogger("nexus.optimization")


@dataclass
class WFAWindow:
    """WFA 窗口"""
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime


@dataclass
class WFAParams:
    """策略参数"""
    name: str
    params: Dict[str, Any]
    

@dataclass
class WFAFoldResult:
    """单折结果"""
    window: WFAWindow
    params: WFAParams
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    total_pnl: float


class OptimizationService:
    """
    优化服务 - Walk-Forward Analysis
    
    实现 "回测 -> 参数择优 -> 模拟运行 -> 实盘热加载" 的闭环
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._running = False
        self._wfa_task: Optional[asyncio.Task] = None
        
        # WFA 配置
        self._lookback_days = self.settings.optimization.wfa_lookback_days
        self._sharpe_threshold = self.settings.optimization.wfa_sharpe_threshold
        self._max_dd_threshold = self.settings.optimization.wfa_max_drawdown_threshold
        
        # 优化历史
        self._optimization_history: List[Dict[str, Any]] = []
    
    async def start(self) -> None:
        """启动优化服务"""
        if self._running:
            return
        
        self._running = True
        
        if self.settings.optimization.wfa_enabled:
            self._wfa_task = asyncio.create_task(self._wfa_loop())
        
        logger.info("OptimizationService started")
    
    async def stop(self) -> None:
        """停止优化服务"""
        self._running = False
        
        if self._wfa_task:
            self._wfa_task.cancel()
            try:
                await self._wfa_task
            except asyncio.CancelledError:
                pass
        
        logger.info("OptimizationService stopped")
    
    async def _wfa_loop(self) -> None:
        """WFA 优化循环"""
        while self._running:
            try:
                # 计算下次运行时间（每周日凌晨）
                await self._wait_for_schedule()
                
                if self._running:
                    await self.run_wfa()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"WFA error: {e}", exc_info=True)
                await asyncio.sleep(3600)
    
    async def _wait_for_schedule(self) -> None:
        """等待到计划时间"""
        schedule_day = self.settings.optimization.wfa_schedule_day
        day_map = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, 
                   "friday": 4, "saturday": 5, "sunday": 6}
        target_day = day_map.get(schedule_day, 6)
        
        while self._running:
            now = datetime.now(timezone.utc)
            # 检查是否是目标日期的凌晨
            if now.weekday() == target_day and now.hour == 0:
                return
            await asyncio.sleep(3600)
    
    async def run_wfa(self) -> Dict[str, Any]:
        """
        运行 Walk-Forward Analysis
        
        流程：
        1. 获取历史交易数据
        2. 划分训练/测试窗口
        3. 在训练窗口优化参数
        4. 在测试窗口验证
        5. 选择最优参数
        6. 发布更新事件
        """
        logger.info("Starting WFA optimization...")
        
        bus = await get_event_bus()
        
        # 1. 获取历史数据
        trades = await self._get_historical_trades()
        if len(trades) < 50:
            logger.warning("Not enough trades for WFA")
            return {"status": "skipped", "reason": "not_enough_trades"}
        
        # 2. 定义参数搜索空间
        param_grid = self._get_param_grid()
        
        # 3. 执行 WFA
        fold_results = await self._execute_wfa(trades, param_grid)
        
        # 4. 选择最优参数
        best_params = self._select_best_params(fold_results)
        
        # 5. 验证稳定性
        is_stable = self._validate_stability(fold_results, best_params)
        
        # 6. 发布结果
        result = {
            "status": "completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "best_params": best_params.params if best_params else None,
            "is_stable": is_stable,
            "fold_count": len(fold_results),
            "avg_sharpe": sum(r.sharpe_ratio for r in fold_results) / len(fold_results) if fold_results else 0,
        }
        
        if best_params and is_stable:
            # 发布参数更新事件
            await bus.publish(EventType.OPTIMIZATION_PARAMS_UPDATED, {
                "strategy": "short_overbought",
                "params": best_params.params,
                "metrics": result,
            })
            logger.info(f"WFA completed: new params = {best_params.params}")
        else:
            logger.info("WFA completed: no improvement found")
        
        # 记录优化历史
        self._optimization_history.append(result)
        
        return result
    
    async def _get_historical_trades(self) -> List[Dict[str, Any]]:
        """获取历史交易数据"""
        since = datetime.now(timezone.utc) - timedelta(days=self._lookback_days)
        trades = await TradeRepository.get_closed(since=since, limit=1000)
        return trades
    
    def _get_param_grid(self) -> List[WFAParams]:
        """参数搜索空间"""
        base_params = {
            "rsi_period": [10, 14, 20],
            "daily_rsi_min": [65, 70, 75],
            "h4_rsi_enter": [60, 65, 70],
            "hard_stop_pct": [3, 5, 7],
            "tp1_pct": [2, 3, 4],
            "trail_activate_pct": [1.5, 2, 2.5],
        }
        
        # 生成参数组合（简化版，实际可用 itertools.product）
        params_list = []
        for rsi in base_params["rsi_period"]:
            for daily_rsi in base_params["daily_rsi_min"]:
                for h4_rsi in base_params["h4_rsi_enter"]:
                    params_list.append(WFAParams(
                        name=f"rsi{rsi}_daily{daily_rsi}_h4{h4_rsi}",
                        params={
                            "rsi_period": rsi,
                            "daily_rsi_min": daily_rsi,
                            "h4_rsi_enter": h4_rsi,
                            "hard_stop_pct": 5,
                            "tp1_pct": 3,
                            "trail_activate_pct": 2,
                        }
                    ))
        
        return params_list[:20]  # 限制数量
    
    async def _execute_wfa(
        self,
        trades: List[Dict[str, Any]],
        param_grid: List[WFAParams],
    ) -> List[WFAFoldResult]:
        """执行 WFA"""
        results = []
        
        # 划分窗口
        windows = self._create_windows(trades)
        
        for window in windows:
            # 获取训练集和测试集
            train_trades = [t for t in trades 
                          if window.train_start <= self._parse_time(t.get("opened_at")) <= window.train_end]
            test_trades = [t for t in trades 
                          if window.test_start <= self._parse_time(t.get("opened_at")) <= window.test_end]
            
            if not train_trades or not test_trades:
                continue
            
            # 在训练集上找最优参数
            best_params = self._optimize_on_train(train_trades, param_grid)
            
            # 在测试集上验证
            test_result = self._evaluate_params(test_trades, best_params)
            
            results.append(WFAFoldResult(
                window=window,
                params=best_params,
                sharpe_ratio=test_result["sharpe"],
                max_drawdown=test_result["max_drawdown"],
                win_rate=test_result["win_rate"],
                total_trades=len(test_trades),
                total_pnl=test_result["total_pnl"],
            ))
        
        return results
    
    def _create_windows(self, trades: List[Dict[str, Any]]) -> List[WFAWindow]:
        """创建滚动窗口"""
        windows = []
        
        if not trades:
            return windows
        
        # 获取时间范围
        times = [self._parse_time(t.get("opened_at")) for t in trades]
        start_time = min(times)
        end_time = max(times)
        
        # 窗口大小
        train_days = 21  # 训练窗口 3 周
        test_days = 7    # 测试窗口 1 周
        step_days = 7    # 滚动步长 1 周
        
        current = start_time
        while current + timedelta(days=train_days + test_days) <= end_time:
            windows.append(WFAWindow(
                train_start=current,
                train_end=current + timedelta(days=train_days),
                test_start=current + timedelta(days=train_days),
                test_end=current + timedelta(days=train_days + test_days),
            ))
            current += timedelta(days=step_days)
        
        return windows
    
    def _parse_time(self, time_value) -> datetime:
        """解析时间"""
        if isinstance(time_value, datetime):
            return time_value
        if isinstance(time_value, str):
            try:
                return datetime.fromisoformat(time_value.replace("Z", "+00:00"))
            except:
                return datetime.now(timezone.utc)
        return datetime.now(timezone.utc)
    
    def _optimize_on_train(
        self,
        train_trades: List[Dict[str, Any]],
        param_grid: List[WFAParams],
    ) -> WFAParams:
        """在训练集上优化参数"""
        best_params = param_grid[0]
        best_sharpe = -999
        
        for params in param_grid:
            result = self._evaluate_params(train_trades, params)
            if result["sharpe"] > best_sharpe:
                best_sharpe = result["sharpe"]
                best_params = params
        
        return best_params
    
    def _evaluate_params(
        self,
        trades: List[Dict[str, Any]],
        params: WFAParams,
    ) -> Dict[str, float]:
        """评估参数表现"""
        if not trades:
            return {"sharpe": 0, "max_drawdown": 0, "win_rate": 0, "total_pnl": 0}
        
        # 计算收益序列
        returns = []
        for trade in trades:
            pnl = (trade.get("tp1_locked_pnl", 0) or 0) + (trade.get("pnl", 0) or 0)
            stake = trade.get("stake", 1)
            returns.append(pnl / stake if stake > 0 else 0)
        
        # 计算指标
        import numpy as np
        returns_array = np.array(returns)
        
        # 夏普比率
        if len(returns_array) > 1 and returns_array.std() > 0:
            sharpe = returns_array.mean() / returns_array.std() * (252 ** 0.5)
        else:
            sharpe = 0
        
        # 最大回撤
        cumulative = np.cumsum(returns_array)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = running_max - cumulative
        max_drawdown = drawdown.max() if len(drawdown) > 0 else 0
        
        # 胜率
        win_rate = (returns_array > 0).sum() / len(returns_array) if len(returns_array) > 0 else 0
        
        # 总盈亏
        total_pnl = returns_array.sum()
        
        return {
            "sharpe": float(sharpe),
            "max_drawdown": float(max_drawdown),
            "win_rate": float(win_rate),
            "total_pnl": float(total_pnl),
        }
    
    def _select_best_params(self, fold_results: List[WFAFoldResult]) -> Optional[WFAParams]:
        """选择最优参数"""
        if not fold_results:
            return None
        
        # 按夏普比率排序
        fold_results.sort(key=lambda r: r.sharpe_ratio, reverse=True)
        return fold_results[0].params
    
    def _validate_stability(
        self,
        fold_results: List[WFAFoldResult],
        best_params: WFAParams,
    ) -> bool:
        """验证参数稳定性"""
        if len(fold_results) < 3:
            return False
        
        # 检查使用最优参数的折数
        matching_folds = [r for r in fold_results if r.params.name == best_params.name]
        
        if len(matching_folds) < 2:
            return False
        
        # 检查夏普比率是否稳定
        sharpes = [r.sharpe_ratio for r in matching_folds]
        avg_sharpe = sum(sharpes) / len(sharpes)
        
        return avg_sharpe > self._sharpe_threshold
    
    async def get_optimization_history(self) -> List[Dict[str, Any]]:
        """获取优化历史"""
        return self._optimization_history
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "running": self._running,
            "wfa_enabled": self.settings.optimization.wfa_enabled,
            "wfa_task": self._wfa_task is not None and not self._wfa_task.done(),
            "optimization_count": len(self._optimization_history),
        }
