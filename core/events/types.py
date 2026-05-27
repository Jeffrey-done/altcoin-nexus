"""
事件类型定义
"""

from enum import Enum
from typing import Callable, Any

from .bus import Event

# 事件回调类型
EventCallback = Callable[[Event], Any]


class EventType(str, Enum):
    """系统事件类型枚举"""
    
    # 交易事件
    TRADE_OPENED = "trade.opened"
    TRADE_CLOSED = "trade.closed"
    TRADE_UPDATED = "trade.updated"
    TRADE_TP1 = "trade.tp1"
    TRADE_STOPPED = "trade.stopped"
    
    # 候选事件
    CANDIDATE_ADDED = "candidate.added"
    CANDIDATE_TRIGGERED = "candidate.triggered"
    CANDIDATE_REMOVED = "candidate.removed"
    
    # 风控事件
    RISK_ALERT = "risk.alert"
    RISK_STATE_CHANGED = "risk.state_changed"
    RISK_PAUSED = "risk.paused"
    RISK_RESUMED = "risk.resumed"
    
    # 对账事件
    POSITION_MISMATCH = "position.mismatch"  # 持仓不一致
    RECONCILIATION_COMPLETED = "reconciliation.completed"  # 对账完成
    
    # 信号事件
    SIGNAL_SCORED = "signal.scored"
    SIGNAL_TRIGGERED = "signal.triggered"
    
    # 系统事件
    SYSTEM_HEALTH = "system.health"
    SYSTEM_PANIC = "system.panic"
    SYSTEM_RECOVER = "system.recover"
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    
    # 配置事件
    CONFIG_CHANGED = "config.changed"
    CONFIG_RELOADED = "config.reloaded"
    
    # 执行事件
    EXECUTION_ORDER_SENT = "execution.order_sent"
    EXECUTION_ORDER_FILLED = "execution.order_filled"
    EXECUTION_ORDER_FAILED = "execution.order_failed"
    
    # 市场状态事件
    MARKET_REGIME_CHANGED = "market.regime_changed"
    
    # 优化事件
    OPTIMIZATION_COMPLETED = "optimization.completed"
    OPTIMIZATION_PARAMS_UPDATED = "optimization.params_updated"
