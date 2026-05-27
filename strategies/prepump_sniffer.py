"""
异动捕获策略 (PrePumpSniffer)
"""

import logging
from typing import Any, Dict, List, Optional

from .base import BaseStrategy

logger = logging.getLogger("nexus.strategy.prepump_sniffer")


class PrePumpSnifferStrategy(BaseStrategy):
    """
    异动捕获策略
    
    逻辑：
    1. 扫描量价背离 + OI 突增的标的
    2. 7 维度评分：量比、OI变化、资金费率、RSI、价格位置、波动率、趋势
    3. 捕获爆发前的异动信号
    
    适用场景：
    - 小币种爆发前的异动检测
    - 大户建仓信号捕捉
    """
    
    name = "prepump_sniffer"
    direction = "LONG"
    description = "异动捕获策略"
    
    def __init__(self, datafeed=None, config=None):
        super().__init__(datafeed, config)
        
        # 默认配置
        self._config = {
            # 扫描参数
            "vol_ratio_min": 2.0,       # 最小量比
            "oi_change_min": 10.0,      # 最小 OI 变化 (%)
            "price_max": 50.0,          # 最大价格
            "vol_min": 300000,          # 最小成交量
            
            # 评分阈值
            "score_threshold": 60,      # 入选阈值
            
            # 止盈止损
            "tp1_pct": 8,
            "tp2_pct": 15,
            "hard_stop_pct": 10,
        }
        self._config.update(config or {})
    
    async def scan(self) -> List[Dict[str, Any]]:
        """扫描异动标的"""
        if not self.datafeed:
            return []
        
        config = self._config
        candidates = []
        
        # 获取所有行情
        tickers = await self.datafeed.get_all_tickers()
        
        for symbol, ticker in tickers.items():
            try:
                # 基础过滤
                if not symbol.endswith("/USDT"):
                    continue
                
                price = ticker.get("last", 0)
                volume = ticker.get("quoteVolume", 0)
                pct_24h = ticker.get("percentage", 0)
                
                if not price or not volume:
                    continue
                
                if price > config["price_max"]:
                    continue
                
                if volume < config["vol_min"]:
                    continue
                
                # 获取 K 线
                ohlcv = await self.datafeed.get_ohlcv(symbol, "1h", limit=50)
                if not ohlcv or len(ohlcv) < 20:
                    continue
                
                # 计算量比
                vol_ratio = self._calculate_volume_ratio(ohlcv)
                if vol_ratio < config["vol_ratio_min"]:
                    continue
                
                # 获取 OI 数据
                oi_change = 0
                try:
                    oi_data = await self.datafeed.get_open_interest(symbol)
                    if oi_data:
                        oi_change = oi_data.get("percentage", 0)
                except:
                    pass
                
                # 7 维度评分
                score_details = self._calculate_7d_score(
                    ohlcv=ohlcv,
                    vol_ratio=vol_ratio,
                    oi_change=oi_change,
                    pct_24h=pct_24h,
                    price=price,
                )
                
                total_score = score_details["total"]
                
                if total_score < config["score_threshold"]:
                    continue
                
                candidates.append({
                    "symbol": symbol,
                    "price": price,
                    "volume": volume,
                    "pct_24h": pct_24h,
                    "vol_ratio": vol_ratio,
                    "oi_change": oi_change,
                    "score": total_score,
                    "score_details": score_details,
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
        
        # 获取 4 小时 K 线确认
        ohlcv_4h = await self.datafeed.get_ohlcv(symbol, "4h", limit=50, exchange=exchange)
        if not ohlcv_4h:
            return None
        
        # 检查趋势是否向上
        ma_cross = self._check_ma_cross(ohlcv_4h)
        if ma_cross < 0:  # 死叉不入场
            return None
        
        # 获取资金费率
        funding_rate = 0
        try:
            funding = await self.datafeed.get_funding_rate(symbol, exchange)
            if funding:
                funding_rate = funding.get("fundingRate", 0)
        except:
            pass
        
        return {
            "symbol": symbol,
            "direction": self.direction,
            "strategy": self.name,
            "price": candidate["price"],
            "pct_24h": candidate.get("pct_24h", 0),
            "vol_ratio": candidate.get("vol_ratio", 0),
            "oi_change": candidate.get("oi_change", 0),
            "funding_rate": funding_rate,
            "ma_cross": ma_cross,
            "score": candidate.get("score", 0),
            "score_details": candidate.get("score_details", {}),
            "exchange": exchange,
            "tp1_pct": config["tp1_pct"],
            "tp2_pct": config["tp2_pct"],
            "hard_stop_pct": config["hard_stop_pct"],
        }
    
    def get_multiplier(self, regime: str = "ranging") -> float:
        """市场状态乘数"""
        multipliers = {
            "trending_up": 1.3,
            "trending_down": 0.3,
            "ranging": 1.0,
            "high_vol": 1.2,      # 高波动异动多
            "crash": 0.0,
            "recovery": 1.5,      # 反弹行情异动最多
        }
        return multipliers.get(regime, 1.0)
    
    def _calculate_volume_ratio(self, ohlcv: List) -> float:
        """计算量比"""
        if len(ohlcv) < 7:
            return 1.0
        recent = ohlcv[-1][5]
        avg = sum(c[5] for c in ohlcv[-7:]) / 7
        return recent / avg if avg > 0 else 1.0
    
    def _check_ma_cross(self, ohlcv: List) -> float:
        """检查均线交叉"""
        if len(ohlcv) < 20:
            return 0.0
        
        closes = [c[4] for c in ohlcv]
        ma5 = sum(closes[-5:]) / 5
        ma20 = sum(closes[-20:]) / 20
        
        return (ma5 - ma20) / ma20 * 100 if ma20 > 0 else 0.0
    
    def _calculate_7d_score(
        self,
        ohlcv: List,
        vol_ratio: float,
        oi_change: float,
        pct_24h: float,
        price: float,
    ) -> Dict[str, Any]:
        """
        7 维度评分
        
        1. 量比 (0-20分)
        2. OI 变化 (0-20分)
        3. RSI (0-15分)
        4. 价格位置 (0-15分)
        5. 波动率 (0-10分)
        6. 趋势 (0-10分)
        7. 涨幅 (0-10分)
        """
        scores = {}
        
        # 1. 量比评分
        if vol_ratio >= 5:
            scores["vol_ratio"] = 20
        elif vol_ratio >= 3:
            scores["vol_ratio"] = 15
        elif vol_ratio >= 2:
            scores["vol_ratio"] = 10
        else:
            scores["vol_ratio"] = 5
        
        # 2. OI 变化评分
        if oi_change >= 30:
            scores["oi_change"] = 20
        elif oi_change >= 20:
            scores["oi_change"] = 15
        elif oi_change >= 10:
            scores["oi_change"] = 10
        else:
            scores["oi_change"] = 0
        
        # 3. RSI 评分
        rsi = self._calculate_rsi(ohlcv, 14)
        if 30 <= rsi <= 50:
            scores["rsi"] = 15  # 超卖区域
        elif 50 < rsi <= 65:
            scores["rsi"] = 10
        else:
            scores["rsi"] = 5
        
        # 4. 价格位置评分
        closes = [c[4] for c in ohlcv]
        high_20 = max(closes[-20:])
        low_20 = min(closes[-20:])
        position = (closes[-1] - low_20) / (high_20 - low_20) if high_20 != low_20 else 0.5
        if position <= 0.3:
            scores["price_position"] = 15  # 低位
        elif position <= 0.5:
            scores["price_position"] = 10
        else:
            scores["price_position"] = 5
        
        # 5. 波动率评分
        returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
        import numpy as np
        volatility = np.std(returns[-24:]) * 100 if len(returns) >= 24 else 0
        if volatility >= 5:
            scores["volatility"] = 10
        elif volatility >= 3:
            scores["volatility"] = 7
        else:
            scores["volatility"] = 3
        
        # 6. 趋势评分
        ma5 = sum(closes[-5:]) / 5
        ma20 = sum(closes[-20:]) / 20
        trend = (ma5 - ma20) / ma20 * 100 if ma20 > 0 else 0
        if trend > 2:
            scores["trend"] = 10
        elif trend > 0:
            scores["trend"] = 7
        else:
            scores["trend"] = 3
        
        # 7. 涨幅评分
        if 0 < pct_24h <= 10:
            scores["pct_24h"] = 10  # 温和上涨
        elif 10 < pct_24h <= 20:
            scores["pct_24h"] = 7
        else:
            scores["pct_24h"] = 3
        
        scores["total"] = sum(scores.values())
        return scores
    
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
