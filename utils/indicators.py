"""
技术指标计算工具
统一的指标计算实现，避免代码重复
"""

from typing import List, Optional
import numpy as np


def calculate_rsi(closes: List[float], period: int = 14) -> float:
    """
    计算 RSI (Wilder's Smoothing Method)
    
    与 TradingView/交易所一致的 RSI 实现
    
    Args:
        closes: 收盘价列表
        period: RSI 周期，默认14
    
    Returns:
        RSI 值 (0-100)
    """
    if len(closes) < period + 1:
        return 50.0
    
    # 计算价格变化
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [max(d, 0) for d in deltas]
    losses = [max(-d, 0) for d in deltas]
    
    # 初始平均值（SMA）
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    # Wilder's smoothing (EMA)
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_rsi_series(closes: List[float], period: int = 14) -> List[float]:
    """
    计算 RSI 序列
    
    Args:
        closes: 收盘价列表
        period: RSI 周期
    
    Returns:
        RSI 值列表（前 period 个值为 50.0）
    """
    if len(closes) < period + 1:
        return [50.0] * len(closes)
    
    rsi_values = [50.0] * period  # 前 period 个值用默认值
    
    # 计算价格变化
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [max(d, 0) for d in deltas]
    losses = [max(-d, 0) for d in deltas]
    
    # 初始平均值
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    # 计算第一个 RSI
    if avg_loss == 0:
        rsi_values.append(100.0)
    else:
        rs = avg_gain / avg_loss
        rsi_values.append(100 - (100 / (1 + rs)))
    
    # Wilder's smoothing 计算后续 RSI
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100 - (100 / (1 + rs)))
    
    return rsi_values


def calculate_rsi_peak(closes: List[float], period: int = 14, lookback: int = 50) -> float:
    """
    计算 RSI 峰值（增量计算，O(n) 复杂度）
    
    Args:
        closes: 收盘价列表
        period: RSI 周期
        lookback: 回看周期数
    
    Returns:
        RSI 峰值
    """
    if len(closes) < period + 1:
        return 50.0
    
    # 取最近 lookback 根 K 线
    recent_closes = closes[-lookback:] if len(closes) > lookback else closes
    
    # 计算 RSI 序列
    rsi_series = calculate_rsi_series(recent_closes, period)
    
    # 返回最大值
    return max(rsi_series[period:]) if len(rsi_series) > period else 50.0


def calculate_atr(highs: List[float], lows: List[float], closes: List[float], 
                  period: int = 14) -> float:
    """
    计算 ATR (Average True Range)
    
    Args:
        highs: 最高价列表
        lows: 最低价列表
        closes: 收盘价列表
        period: ATR 周期
    
    Returns:
        ATR 值
    """
    if len(closes) < period + 1:
        return 0.0
    
    # 计算 True Range
    tr_values = []
    for i in range(1, len(closes)):
        high = highs[i]
        low = lows[i]
        prev_close = closes[i-1]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_values.append(tr)
    
    if not tr_values:
        return 0.0
    
    # 初始 ATR (SMA)
    atr = sum(tr_values[:period]) / period
    
    # Wilder's smoothing
    for i in range(period, len(tr_values)):
        atr = (atr * (period - 1) + tr_values[i]) / period
    
    return atr


def calculate_ema(values: List[float], period: int) -> List[float]:
    """
    计算 EMA (Exponential Moving Average)
    
    Args:
        values: 数值列表
        period: EMA 周期
    
    Returns:
        EMA 值列表
    """
    if len(values) < period:
        return values.copy()
    
    multiplier = 2 / (period + 1)
    ema_values = values[:period-1].copy()  # 前 period-1 个值保持原样
    
    # 第一个 EMA 使用 SMA
    sma = sum(values[:period]) / period
    ema_values.append(sma)
    
    # 后续 EMA
    for i in range(period, len(values)):
        ema = (values[i] - ema_values[-1]) * multiplier + ema_values[-1]
        ema_values.append(ema)
    
    return ema_values
