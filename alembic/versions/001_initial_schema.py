"""
Alembic 初始迁移
创建所有核心表
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建 trades 表
    op.create_table(
        "trades",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("symbol", sa.String(32), nullable=False, index=True),
        sa.Column("direction", sa.String(8), nullable=False, server_default="SHORT"),
        sa.Column("strategy", sa.String(64), nullable=False, server_default="short_overbought", index=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="open", index=True),
        sa.Column("entry_price", sa.Float, nullable=False),
        sa.Column("stake", sa.Float, nullable=False),
        sa.Column("leverage", sa.Integer, nullable=False, server_default="10"),
        sa.Column("notional", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("shares", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("take_profit_1", sa.Float, server_default="0.0"),
        sa.Column("take_profit_2", sa.Float, server_default="0.0"),
        sa.Column("tp1_triggered", sa.Boolean, server_default="false"),
        sa.Column("tp1_locked_pnl", sa.Float, server_default="0.0"),
        sa.Column("stake_remaining", sa.Float, server_default="0.0"),
        sa.Column("hard_stop_price", sa.Float, nullable=True),
        sa.Column("best_pnl_pct", sa.Float, server_default="0.0"),
        sa.Column("trail_stop_price", sa.Float, nullable=True),
        sa.Column("stop_loss", sa.Float, nullable=True),
        sa.Column("max_hold_hours", sa.Integer, server_default="24"),
        sa.Column("pnl", sa.Float, server_default="0.0"),
        sa.Column("current_price", sa.Float, nullable=True),
        sa.Column("close_reason", sa.Text, nullable=True),
        sa.Column("close_type", sa.String(32), nullable=True),
        sa.Column("exchange", sa.String(16), nullable=False, server_default="shadow"),
        sa.Column("live_order_id", sa.String(128), nullable=True),
        sa.Column("close_order_id", sa.String(128), nullable=True),
        sa.Column("tp1_close_order_id", sa.String(128), nullable=True),
        sa.Column("client_order_id", sa.String(128), server_default=""),
        sa.Column("account_id", sa.String(64), nullable=False, server_default="", index=True),
        sa.Column("ref_price_at_order", sa.Float, server_default="0.0"),
        sa.Column("slippage_pct", sa.Float, server_default="0.0"),
        sa.Column("exit_ref_price", sa.Float, server_default="0.0"),
        sa.Column("exit_slippage_pct", sa.Float, server_default="0.0"),
        sa.Column("source", sa.String(128), server_default="auto"),
        sa.Column("reason", sa.Text, server_default=""),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_trades_status_account", "trades", ["status", "account_id"])
    op.create_index("ix_trades_symbol_status", "trades", ["symbol", "status"])
    op.create_index("ix_trades_strategy_status", "trades", ["strategy", "status"])
    op.create_index("ix_trades_opened_at", "trades", ["opened_at"])

    # 创建 candidates 表
    op.create_table(
        "candidates",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(32), nullable=False, index=True),
        sa.Column("strategy", sa.String(64), nullable=False, server_default="short_overbought", index=True),
        sa.Column("direction", sa.String(8), nullable=False, server_default="SHORT"),
        sa.Column("price", sa.Float, nullable=False),
        sa.Column("vol24h", sa.Float, server_default="0.0"),
        sa.Column("pct24h", sa.Float, server_default="0.0"),
        sa.Column("score", sa.Float, server_default="0.0"),
        sa.Column("rsi_1d", sa.Float, server_default="50.0"),
        sa.Column("rsi_4h", sa.Float, nullable=True),
        sa.Column("oi_change", sa.Float, server_default="0.0"),
        sa.Column("funding_rate", sa.Float, server_default="0.0"),
        sa.Column("metadata_json", sa.Text, nullable=True),
        sa.Column("triggered", sa.Boolean, server_default="false"),
        sa.Column("trigger_type", sa.String(16), nullable=True),
        sa.Column("trigger_reason", sa.Text, nullable=True),
        sa.Column("pending_open", sa.Boolean, server_default="false"),
        sa.Column("pending_opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pending_open_retries", sa.Integer, server_default="0"),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_candidates_symbol_strategy", "candidates", ["symbol", "strategy"], unique=True)
    op.create_index("ix_candidates_triggered", "candidates", ["triggered"])

    # 创建 risk_states 表
    op.create_table(
        "risk_states",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.String(64), nullable=False, index=True),
        sa.Column("date", sa.String(10), nullable=False),
        sa.Column("daily_loss", sa.Float, server_default="0.0"),
        sa.Column("daily_trades_opened", sa.Integer, server_default="0"),
        sa.Column("consecutive_losses", sa.Integer, server_default="0"),
        sa.Column("paused_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_open_stake", sa.Float, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_risk_account_date", "risk_states", ["account_id", "date"], unique=True)

    # 创建 execution_events 表
    op.create_table(
        "execution_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(64), nullable=False, index=True),
        sa.Column("exchange", sa.String(16), nullable=True),
        sa.Column("symbol", sa.String(32), nullable=True, index=True),
        sa.Column("direction", sa.String(8), nullable=True),
        sa.Column("account_id", sa.String(64), nullable=True, index=True),
        sa.Column("client_order_id", sa.String(128), nullable=True),
        sa.Column("order_id", sa.String(128), nullable=True),
        sa.Column("stake", sa.Float, nullable=True),
        sa.Column("leverage", sa.Integer, nullable=True),
        sa.Column("fill_price", sa.Float, nullable=True),
        sa.Column("fill_amount", sa.Float, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("extra_data", sa.Text, nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, index=True),
    )
    op.create_index("ix_events_type_ts", "execution_events", ["event_type", "timestamp"])

    # 创建 signal_logs 表
    op.create_table(
        "signal_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(32), nullable=False, index=True),
        sa.Column("strategy", sa.String(64), nullable=False, server_default="short_overbought"),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("grade", sa.String(4), nullable=False),
        sa.Column("rsi_score", sa.Float, server_default="0.0"),
        sa.Column("trigger_score", sa.Float, server_default="0.0"),
        sa.Column("rsi_1d", sa.Float, nullable=True),
        sa.Column("rsi_4h", sa.Float, nullable=True),
        sa.Column("pct_24h", sa.Float, nullable=True),
        sa.Column("oi_change", sa.Float, nullable=True),
        sa.Column("funding_rate", sa.Float, nullable=True),
        sa.Column("btc_24h_pct", sa.Float, nullable=True),
        sa.Column("trigger_type", sa.String(16), nullable=True),
        sa.Column("triggered_open", sa.Boolean, server_default="false"),
        sa.Column("trade_id", sa.String(128), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, index=True),
    )
    op.create_index("ix_signal_logs_symbol_ts", "signal_logs", ["symbol", "timestamp"])

    # 创建 system_states 表
    op.create_table(
        "system_states",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(128), nullable=False, unique=True, index=True),
        sa.Column("value", sa.Text, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 创建 config_overrides 表
    op.create_table(
        "config_overrides",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(128), nullable=False, unique=True, index=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("source", sa.String(64), server_default="admin"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("config_overrides")
    op.drop_table("system_states")
    op.drop_table("signal_logs")
    op.drop_table("execution_events")
    op.drop_table("risk_states")
    op.drop_table("candidates")
    op.drop_table("trades")
