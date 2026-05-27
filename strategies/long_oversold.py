"""
超跌反弹策略 (LongOversold)
"""

import logging
from typing import Any, Dict, List, Optional

from .base import BaseStrategy

logger = logging.getLogger("nexus.strategy.long_oversold")


class LongOversoldStrategy(BaseStrategy):
    """
    超跌反弹策略
    
    逻辑：
    1. 扫描 RSI 超卖 + 大幅下跌的标的
    2. 确认成交量放大 + 资金费率转负
    3. 做多入场，等待反弹
    
    市场状态乘数：
    - trending_up: 1.5 (顺势做多)
    - ranging: 1.0
    - trending_down: 0.5 (逆势谨慎)
    - crash: 0.0 (暂停)
    """
    
    name = "long_oversold"
    direction = "LONG"
    description = "超跌反弹策略"
    
    def __init__(self, datafeed=None, config=None):
        super().__init__(datafeed, config)
        
        # 默认配置
        self._config = {
            # 扫描参数
            "rsi_period": 14,
            "rsi_oversold": 30,        # RSI 超卖阈值
            "pct_24h_min": -15,        # 最小跌幅 (负数)
            "pct_24h_max": -5,         # 最大跌幅
            "vol_min": 500000,         # 最小成交量
            
            # 确认参数
            "rsi_4h_oversold": 35,     # 4小时 RSI 超卖
            "funding_rate_max": -0.001, # 资金费率阈值 (负值表示空头拥挤)
            "vol_ratio_min": 1.5,      # 成交量放大倍数
            
            # 止盈止损
            "tp1_pct": 5,
            "tp2_pct": 10,
            "hard_stop_pct": 8,
            "trail_activate_pct": 3,
        }
        self._config.update(config or {})
    
    async def scan(self) -> List[Dict[str, Any]]:
        """扫描超跌标的"""
        if not self.datafeed:
            return []
        
        config = self._config
        candidates = []
        
        # 获取所有行情
        tickers = await self.datafeed.get_all_tickers()
        
        for symbol, ticker in tickers.items():
            try:
                # 过滤条件
                if not symbol.endswith("/USDT"):
                    continue
                
                price = ticker.get("last", 0)
                volume = ticker.get("quoteVolume", 0)
                pct_24h = ticker.get("percentage", 0)
                
                if not price or not volume:
                    continue
                
                # 跌幅过滤
                if pct_24h > config["pct_24h_max"] or pct_24h < config["pct_24h_min"]:
                    continue
                
                # 成交量过滤
                if volume < config["vol_min"]:
                    continue
                
                # 计算 RSI
                ohlcv = await self.datafeed.get_ohlcv(symbol, "1d", limit=20)
                if not ohlcv:
                    continue
                
                rsi = self._calculate_rsi(ohlcv, config["rsi_period"])
                
                # RSI 超卖过滤
                if rsi > config["rsi_oversold"]:
                    continue
                
                # 计算评分
                score = self._calculate_score(rsi, pct_24h, volume)
                
                candidates.append({
                    "symbol": symbol,
                    "price": price,
                    "volume": volume,
                    "pct_24h": pct_24h,
                    "rsi_1d": rsi,
                    "score": score,
                    "direction": self.direction,
                    "strategy": self.name,
                })
            
            except Exception as e:
                logger.debug(f"Error scanning {symbol}: {e}")
                continue
        
        # 按评分排序
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:10]
    
    async def confirm(self, candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """确认候选"""
        if not self.datafeed:
            return None
        
        config = self._config
        symbol = candidate["symbol"]
        exchange = candidate.get("exchange", "binance")
        
        # 获取 4 小时 K 线
        ohlcv_4h = await self.datafeed.get_ohlcv(symbol, "4h", limit=50, exchange=exchange)
        if not ohlcv_4h:
            return None
        
        # 计算 4 小时 RSI
        rsi_4h = self._calculate_rsi(ohlcv_4h, config["rsi_period"])
        if rsi_4h > config["rsi_4h_oversold"]:
            return None
        
        # 检查成交量放大
        vol_ratio = self._calculate_volume_ratio(ohlcv_4h)
        if vol_ratio < config["vol_ratio_min"]:
            return None
        
        # 检查资金费率 (可选)
        funding_rate = 0
        if self.datafeed:
            try:
                funding = await self.datafeed.get_funding_rate(symbol, exchange)
                if funding:
                    funding_rate = funding.get("fundingRate", 0)
            except:
                pass
        
        # 资金费率过低说明空头拥挤，反弹概率大
        # 但也不能太低（可能有爆仓风险）
        
        return {
            "symbol": symbol,
            "direction": self.direction,
            "strategy": self.name,
            "price": candidate["price"],
            "rsi_1d": candidate.get("rsi_1d", 0),
            "rsi_4h": rsi_4h,
            "pct_24h": candidate.get("pct_24h", 0),
            "funding_rate": funding_rate,
            "vol_ratio": vol_ratio,
            "score": candidate.get("score", 0),
            "exchange": exchange,
            "tp1_pct": config["tp1_pct"],
            "tp2_pct": config["tp2_pct"],
            "hard_stop_pct": config["hard_stop_pct"],
        }
    
    def get_multiplier(self, regime: str = "ranging") -> float:
        """市场状态乘数"""
        multipliers = {
            "trending_up": 1.5,      # 顺势做多
            "trending_down": 0.5,    # 逆势谨慎
            "ranging": 1.0,
            "high_vol": 0.8,
            "crash": 0.0,            # 崩盘暂停
            "recovery": 1.2,         # 反弹行情加码
        }
        return multipliers.get(regime, 1.0)
    
    def _calculate_rsi(self, ohlcv: List, period: int = 14) -> float:
        """计算 RSI"""
        if len(ohlcv) < period + 1:
            return 50.0
        
        closes = [c[4] for c in ohlcv]
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def _calculate_volume_ratio(self, ohlcv: List) -> float:
        """计算成交量比率"""
        if len(ohlcv) < 7:
            return 1.0
        
        recent_vol = ohlcv[-1][5]
        avg_vol = sum(c[5] for c in ohlcv[-7:]) / 7
        
        return recent_vol / avg_vol if avg_vol > 0 else 1.0
    
    def _calculate_score(
        self,
        rsi: float,
        pct_24h: float,
        volume: float,
    ) -> int:
        """计算评分"""
        score = 0
        
        # RSI 超卖程度
        if rsi <= 20:
            score += 40
        elif rsi <= 25:
            score += 30
        elif rsi <= 30:
            score += 20
        
        # 跌幅程度
        if pct_24h <= -15:
            score += 30
        elif pct_24h <= -10:
            score += 25
        elif pct_24h <= -5:
            score += 15
        
        # 成交量
        if volume >= 5000000:
            score += 20
        elif volume >= 2000000:
            score += 15
        elif volume >= 500000:
            score += 10
        
        return min(score, 100)
