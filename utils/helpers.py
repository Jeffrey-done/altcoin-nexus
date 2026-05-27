"""
工具函数
"""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import List, Optional


def generate_trade_id(prefix: str = "trade") -> str:
    """生成唯一交易ID"""
    unique = uuid.uuid4().hex[:12]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{prefix}_{timestamp}_{unique}"


def calculate_rsi(closes: List[float], period: int = 14) -> float:
    """
    计算 RSI
    
    Args:
        closes: 收盘价列表
        period: 周期
    
    Returns:
        RSI 值
    """
    if len(closes) < period + 1:
        return 50.0
    
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)


def calculate_slippage(
    expected_price: float,
    actual_price: float,
    direction: str = "SHORT",
) -> float:
    """
    计算滑点百分比
    
    Args:
        expected_price: 预期价格
        actual_price: 实际成交价格
        direction: 方向
    
    Returns:
        滑点百分比
    """
    if expected_price == 0:
        return 0.0
    
    if direction == "SHORT":
        # 做空：实际价格越高，滑点越大（负滑点表示亏损）
        slippage = (actual_price - expected_price) / expected_price * 100
    else:
        # 做多：实际价格越低，滑点越大
        slippage = (expected_price - actual_price) / expected_price * 100
    
    return round(slippage, 4)


def format_number(value: float, decimals: int = 2) -> str:
    """格式化数字"""
    if abs(value) >= 1e6:
        return f"{value / 1e6:.{decimals}f}M"
    elif abs(value) >= 1e3:
        return f"{value / 1e3:.{decimals}f}K"
    else:
        return f"{value:.{decimals}f}"


def is_within_hours(dt: datetime, hours: float) -> bool:
    """检查时间是否在指定小时数内"""
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    return delta.total_seconds() < hours * 3600


def safe_float(value: any, default: float = 0.0) -> float:
    """安全转换为浮点数"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: any, default: int = 0) -> int:
    """安全转换为整数"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
