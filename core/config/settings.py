"""
Pydantic Settings 配置管理
类型安全、支持环境变量和YAML覆盖
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 预加载 .env 到 OS 环境变量，使子配置也能读取
load_dotenv(PROJECT_ROOT / ".env")


class DatabaseSettings(BaseSettings):
    """数据库配置"""
    model_config = SettingsConfigDict(env_prefix="DB_")
    
    url: str = "postgresql+asyncpg://altcoin:altcoin@localhost:5432/altcoin_nexus"
    echo: bool = False
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 1800


class RedisSettings(BaseSettings):
    """Redis配置"""
    model_config = SettingsConfigDict(env_prefix="REDIS_")
    
    url: str = "redis://localhost:6379/0"
    max_connections: int = 20
    socket_timeout: int = 10
    socket_connect_timeout: int = 5
    decode_responses: bool = True


class ExchangeSettings(BaseSettings):
    """交易所配置"""
    model_config = SettingsConfigDict(env_prefix="EXCHANGE_")
    
    # Binance
    binance_api_key: str = ""
    binance_api_secret: str = ""
    
    # OKX
    okx_api_key: str = ""
    okx_api_secret: str = ""
    okx_passphrase: str = ""
    
    # Bybit
    bybit_api_key: str = ""
    bybit_api_secret: str = ""
    
    # Gate.io
    gate_api_key: str = ""
    gate_api_secret: str = ""
    
    # Bitget
    bitget_api_key: str = ""
    bitget_api_secret: str = ""
    bitget_passphrase: str = ""
    
    # 交易参数
    primary_exchange: str = "binance"
    leverage: int = 10
    max_open_trades: int = 8
    position_mode: str = "one_way"
    
    # 代理（可选，本地开发用，服务器留空直连）
    proxy: str = ""
    
    # 滑点控制
    slippage_alert_pct: float = 0.5
    price_divergence_max_pct: float = 1.0


class RiskSettings(BaseSettings):
    """风控配置"""
    model_config = SettingsConfigDict(env_prefix="RISK_")
    
    # 日度限制
    max_daily_loss: float = 100.0
    max_daily_trades: int = 10
    max_daily_trades_short: int = 6
    max_daily_trades_long: int = 4
    
    # 连亏控制
    consecutive_loss_pause: int = 3
    pause_hours: int = 4
    
    # 仓位控制
    max_position_pct: float = 0.3
    default_stake: float = 33.0
    max_stake: float = 100.0
    
    # 冷却
    cooldown_hours: float = 1.0
    cooldown_scope: str = "symbol"


class StrategySettings(BaseSettings):
    """策略配置"""
    model_config = SettingsConfigDict(env_prefix="STRATEGY_")
    
    # 扫描参数
    vol_min: float = 500000.0
    price_max: float = 100.0
    pct_24h_min: float = 5.0
    
    # RSI参数
    rsi_period: int = 14
    daily_rsi_min: float = 70.0
    h4_rsi_enter: float = 65.0
    h4_rsi_drop: float = 10.0
    h4_rsi_peak_lookback: int = 12
    
    # 尧氏因子
    oi_change_min: float = 10.0
    funding_max: float = 0.01
    funding_min: float = -0.005
    funding_hot: float = 0.005
    
    # 弃盘点
    abandon_body_drop_pct: float = 3.0
    abandon_consecutive: int = 3
    abandon_oi_drop_pct: float = 20.0
    
    # 止盈止损
    tp1_pct: float = 3.0
    tp2_pct: float = 6.0
    tp1_close_ratio: float = 0.5
    hard_stop_pct: float = 5.0
    trail_activate_pct: float = 2.0
    trail_retrace_ratio: float = 0.5
    max_hold_hours: int = 24
    
    # 评分阈值
    score_full_threshold: int = 80
    score_half_threshold: int = 60
    score_skip_threshold: int = 40
    
    # BTC过滤
    btc_filter_enabled: bool = True
    btc_crash_threshold: float = -5.0
    btc_pump_threshold: float = 8.0


class MonitoringSettings(BaseSettings):
    """监控配置"""
    model_config = SettingsConfigDict(env_prefix="MONITOR_")
    
    # Prometheus
    prometheus_enabled: bool = True
    prometheus_port: int = 9090
    
    # 健康检查
    health_check_interval: int = 60
    api_timeout_threshold: int = 3
    ws_disconnect_alert_minutes: int = 1
    
    # 自动对账
    reconciliation_interval_minutes: int = 15


class TelegramSettings(BaseSettings):
    """Telegram配置"""
    model_config = SettingsConfigDict(env_prefix="TG_")
    
    bot_token: str = ""
    chat_id: str = ""
    enabled: bool = False


class OptimizationSettings(BaseSettings):
    """优化配置"""
    model_config = SettingsConfigDict(env_prefix="OPT_")
    
    # WFA参数
    wfa_enabled: bool = True
    wfa_schedule_day: str = "sunday"
    wfa_lookback_days: int = 30
    wfa_sharpe_threshold: float = 0.1
    wfa_max_drawdown_threshold: float = 0.05
    
    # 自动更新
    auto_update_enabled: bool = False
    auto_update_min_trades: int = 50


class Settings(BaseSettings):
    """主配置类 - 聚合所有子配置"""
    model_config = SettingsConfigDict(
        env_prefix="NEXUS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # 系统信息
    version: str = "4.0.0"
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    
    # 子配置
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    exchange: ExchangeSettings = Field(default_factory=ExchangeSettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    strategy: StrategySettings = Field(default_factory=StrategySettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    optimization: OptimizationSettings = Field(default_factory=OptimizationSettings)
    
    @field_validator("environment", mode="before")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = ["development", "testing", "production"]
        if v not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v
    
    def load_yaml_overrides(self, config_dir: Optional[Path] = None) -> None:
        """从YAML文件加载配置覆盖"""
        if config_dir is None:
            config_dir = PROJECT_ROOT / "config"
        
        if not config_dir.exists():
            return
        
        for yaml_file in config_dir.glob("*.yaml"):
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                self._apply_overrides(data, yaml_file.stem)
            except Exception as e:
                print(f"Warning: Failed to load {yaml_file}: {e}")
    
    def _apply_overrides(self, data: Dict[str, Any], section: str) -> None:
        """应用配置覆盖 - 支持嵌套结构"""
        if not isinstance(data, dict):
            return
        
        # 根据section名称映射到子配置
        section_map = {
            "database": self.database,
            "redis": self.redis,
            "exchange": self.exchange,
            "risk": self.risk,
            "strategy": self.strategy,
            "monitoring": self.monitoring,
            "telegram": self.telegram,
            "optimization": self.optimization,
        }
        
        if section in section_map:
            sub_settings = section_map[section]
            # 递归应用嵌套配置
            self._apply_nested(data, sub_settings)
    
    def _apply_nested(self, data: Dict[str, Any], target: Any) -> None:
        """递归应用嵌套配置"""
        for key, value in data.items():
            if isinstance(value, dict):
                # 嵌套对象 - 递归处理
                if hasattr(target, key):
                    sub_target = getattr(target, key)
                    if hasattr(sub_target, '__dict__'):
                        self._apply_nested(value, sub_target)
                    else:
                        setattr(target, key, value)
            else:
                # 叶子节点 - 直接设置
                if hasattr(target, key):
                    setattr(target, key, value)


@lru_cache()
def get_settings() -> Settings:
    """获取全局配置单例"""
    settings = Settings()
    settings.load_yaml_overrides()
    return settings


def reload_settings() -> Settings:
    """重新加载配置"""
    get_settings.cache_clear()
    return get_settings()
