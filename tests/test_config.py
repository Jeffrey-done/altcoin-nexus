"""
核心模块测试
"""

import pytest
from core.config import Settings


def test_settings_default():
    """测试默认配置"""
    settings = Settings()
    assert settings.version == "4.0.0"
    assert settings.environment in ["development", "testing", "production"]


def test_risk_settings():
    """测试风控配置"""
    settings = Settings()
    assert settings.risk.max_daily_loss > 0
    assert settings.risk.max_daily_trades > 0
    assert settings.risk.consecutive_loss_pause > 0


def test_strategy_settings():
    """测试策略配置"""
    settings = Settings()
    assert settings.strategy.vol_min > 0
    assert settings.strategy.daily_rsi_min > 0
    assert settings.strategy.hard_stop_pct > 0
