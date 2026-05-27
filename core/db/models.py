"""
SQLAlchemy ORM 模型定义
纯异步、PostgreSQL优化
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """基类"""
    pass


class TradeModel(Base):
    """交易记录表"""
    __tablename__ = "trades"
    
    id = Column(String(128), primary_key=True)
    symbol = Column(String(32), nullable=False, index=True)
    direction = Column(String(8), nullable=False, default="SHORT")
    strategy = Column(String(64), nullable=False, default="short_overbought", index=True)
    status = Column(String(16), nullable=False, default="open", index=True)
    
    # 价格 & 仓位
    entry_price = Column(Float, nullable=False)
    stake = Column(Float, nullable=False)
    leverage = Column(Integer, nullable=False, default=10)
    notional = Column(Float, nullable=False, default=0.0)
    shares = Column(Float, nullable=False, default=0.0)
    
    # 止盈档位
    take_profit_1 = Column(Float, default=0.0)
    take_profit_2 = Column(Float, default=0.0)
    tp1_triggered = Column(Boolean, default=False)
    tp1_locked_pnl = Column(Float, default=0.0)
    stake_remaining = Column(Float, default=0.0)
    
    # 硬止损
    hard_stop_price = Column(Float, nullable=True)
    
    # 移动止损
    best_pnl_pct = Column(Float, default=0.0)
    trail_stop_price = Column(Float, nullable=True)
    
    # 其他止损
    stop_loss = Column(Float, nullable=True)
    max_hold_hours = Column(Integer, default=24)
    
    # 结算
    pnl = Column(Float, default=0.0)
    current_price = Column(Float, nullable=True)
    close_reason = Column(Text, nullable=True)
    close_type = Column(String(32), nullable=True)
    
    # 实盘路由
    exchange = Column(String(16), nullable=False, default="shadow")
    live_order_id = Column(String(128), nullable=True)
    close_order_id = Column(String(128), nullable=True)
    tp1_close_order_id = Column(String(128), nullable=True)
    client_order_id = Column(String(128), default="")
    
    # 多账户隔离
    account_id = Column(String(64), nullable=False, default="", index=True)
    
    # 滑点追踪
    ref_price_at_order = Column(Float, default=0.0)
    slippage_pct = Column(Float, default=0.0)
    exit_ref_price = Column(Float, default=0.0)
    exit_slippage_pct = Column(Float, default=0.0)
    
    # 元信息
    source = Column(String(128), default="auto")
    reason = Column(Text, default="")
    opened_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    
    __table_args__ = (
        Index("ix_trades_status_account", "status", "account_id"),
        Index("ix_trades_symbol_status", "symbol", "status"),
        Index("ix_trades_strategy_status", "strategy", "status"),
        Index("ix_trades_opened_at", "opened_at"),
    )


class CandidateModel(Base):
    """候选币表"""
    __tablename__ = "candidates"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), nullable=False, index=True)
    strategy = Column(String(64), nullable=False, default="short_overbought", index=True)
    direction = Column(String(8), nullable=False, default="SHORT")
    
    price = Column(Float, nullable=False)
    vol24h = Column(Float, default=0.0)
    pct24h = Column(Float, default=0.0)
    score = Column(Float, default=0.0)
    
    # 通用指标
    rsi_1d = Column(Float, default=50.0)
    rsi_4h = Column(Float, nullable=True)
    oi_change = Column(Float, default=0.0)
    funding_rate = Column(Float, default=0.0)
    
    # 策略自定义元数据
    metadata_json = Column(Text, nullable=True)
    
    triggered = Column(Boolean, default=False)
    trigger_type = Column(String(16), nullable=True)
    trigger_reason = Column(Text, nullable=True)
    
    # 待开仓状态
    pending_open = Column(Boolean, default=False)
    pending_opened_at = Column(DateTime(timezone=True), nullable=True)
    pending_open_retries = Column(Integer, default=0)
    
    # 时间
    added_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    
    __table_args__ = (
        Index("ix_candidates_symbol_strategy", "symbol", "strategy", unique=True),
        Index("ix_candidates_triggered", "triggered"),
    )


class RiskStateModel(Base):
    """风控状态表"""
    __tablename__ = "risk_states"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(String(64), nullable=False, index=True)
    date = Column(String(10), nullable=False)
    
    daily_loss = Column(Float, default=0.0)
    daily_trades_opened = Column(Integer, default=0)
    consecutive_losses = Column(Integer, default=0)
    paused_until = Column(DateTime(timezone=True), nullable=True)
    total_open_stake = Column(Float, default=0.0)
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    
    __table_args__ = (
        Index("ix_risk_account_date", "account_id", "date", unique=True),
    )


class ExecutionEventModel(Base):
    """执行事件表"""
    __tablename__ = "execution_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(64), nullable=False, index=True)
    exchange = Column(String(16), nullable=True)
    symbol = Column(String(32), nullable=True, index=True)
    direction = Column(String(8), nullable=True)
    account_id = Column(String(64), nullable=True, index=True)
    client_order_id = Column(String(128), nullable=True)
    order_id = Column(String(128), nullable=True)
    
    # 灵活数据字段
    stake = Column(Float, nullable=True)
    leverage = Column(Integer, nullable=True)
    fill_price = Column(Float, nullable=True)
    fill_amount = Column(Float, nullable=True)
    error = Column(Text, nullable=True)
    error_code = Column(String(64), nullable=True)
    extra_data = Column(Text, nullable=True)
    
    timestamp = Column(DateTime(timezone=True), nullable=False, default=_utcnow, index=True)
    
    __table_args__ = (
        Index("ix_events_type_ts", "event_type", "timestamp"),
    )


class SignalLogModel(Base):
    """信号评分日志"""
    __tablename__ = "signal_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), nullable=False, index=True)
    strategy = Column(String(64), nullable=False, default="short_overbought")
    
    score = Column(Integer, nullable=False)
    grade = Column(String(4), nullable=False)
    rsi_score = Column(Float, default=0.0)
    trigger_score = Column(Float, default=0.0)
    
    # 原始指标
    rsi_1d = Column(Float, nullable=True)
    rsi_4h = Column(Float, nullable=True)
    pct_24h = Column(Float, nullable=True)
    oi_change = Column(Float, nullable=True)
    funding_rate = Column(Float, nullable=True)
    btc_24h_pct = Column(Float, nullable=True)
    trigger_type = Column(String(16), nullable=True)
    
    # 结果
    triggered_open = Column(Boolean, default=False)
    trade_id = Column(String(128), nullable=True)
    
    timestamp = Column(DateTime(timezone=True), nullable=False, default=_utcnow, index=True)
    
    __table_args__ = (
        Index("ix_signal_logs_symbol_ts", "symbol", "timestamp"),
    )


class SystemStateModel(Base):
    """系统状态表"""
    __tablename__ = "system_states"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(128), nullable=False, unique=True, index=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)


class ConfigOverrideModel(Base):
    """运行时配置覆盖表"""
    __tablename__ = "config_overrides"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(128), nullable=False, unique=True, index=True)
    value = Column(Text, nullable=False)
    source = Column(String(64), default="admin")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
