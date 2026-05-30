"""
Momentum Scalping Strategy (momentum_scalp)
High-frequency momentum capture using orderbook pressure + volume surge.

For $100 capital: targets 1-5% moves within minutes to hours.
Uses orderbook imbalance for entry timing.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import numpy as np

from .base import BaseStrategy

logger = logging.getLogger("nexus.strategy.momentum_scalp")


class MomentumScalpStrategy(BaseStrategy):
    """
    Momentum Scalping Strategy
    
    Logic:
    1. Scan for sudden volume spikes (vol_ratio > 3x)
    2. Check RSI divergence and Bollinger Band squeeze breakout
    3. Orderbook imbalance: bid/ask ratio > 2.0 = bullish pressure
    4. Enter on momentum confirmation, exit on reversal signals
    
    Risk: tight stops (2-3%), quick partial profits at 3%, full exit at 6%
    """
    
    name = "momentum_scalp"
    direction = "LONG"
    description = "Momentum scalping with orderbook pressure"
    
    def __init__(self, datafeed=None, config=None):
        super().__init__(datafeed, config)
        
        self._config = {
            # Scan filters
            "min_volume_usdt": 300000,
            "max_price": 30.0,
            "vol_ratio_min": 2.5,         # Volume surge threshold
            "pct_1h_min": 2.0,            # Minimum 1h change
            
            # Orderbook imbalance
            "bid_ask_ratio_min": 1.5,     # Bid volume / Ask volume
            "depth_levels": 10,           # Orderbook depth to check
            
            # Momentum indicators
            "rsi_period": 7,              # Short RSI for scalping
            "rsi_oversold": 35,
            "rsi_overbought": 75,
            "bb_period": 20,
            "bb_squeeze_threshold": 0.02, # BB width < 2% = squeeze
            
            # TP/SL (aggressive for scalping)
            "tp1_pct": 3.0,
            "tp2_pct": 6.0,
            "hard_stop_pct": 3.0,         # Tight stop
            "trail_activate_pct": 1.5,
            "max_hold_minutes": 120,      # 2 hour max hold
            
            # Position sizing
            "default_stake_pct": 0.20,    # 20% of capital
            "leverage": 10,
        }
        self._config.update(config or {})
        
        # Cache for multi-timeframe analysis
        self._momentum_cache: Dict[str, Dict] = {}
    
    async def scan(self) -> List[Dict[str, Any]]:
        """Scan for momentum breakout opportunities"""
        if not self.datafeed:
            return []
        
        config = self._config
        candidates = []
        
        # Get all USDT pairs
        exchanges = list(self.datafeed._exchanges.keys())
        if not exchanges:
            return []
        
        primary = exchanges[0]
        tickers = await self.datafeed.get_all_tickers(primary)
        
        for symbol, ticker in tickers.items():
            try:
                if not symbol.endswith("/USDT"):
                    continue
                
                price = ticker.get("last", 0)
                volume = ticker.get("quoteVolume", 0)
                pct_24h = ticker.get("percentage", 0)
                
                if not price or not volume:
                    continue
                if price > config["max_price"] or price < 0.001:
                    continue
                if volume < config["min_volume_usdt"]:
                    continue
                
                # Get 1h OHLCV for momentum analysis
                ohlcv_1h = await self.datafeed.get_ohlcv(symbol, "1h", limit=50, exchange=primary)
                if not ohlcv_1h or len(ohlcv_1h) < 20:
                    continue
                
                # Calculate volume ratio
                vol_ratio = self._calculate_volume_ratio(ohlcv_1h)
                if vol_ratio < config["vol_ratio_min"]:
                    continue
                
                # Calculate 1h price change
                if len(ohlcv_1h) >= 2:
                    pct_1h = (ohlcv_1h[-1][4] - ohlcv_1h[-2][4]) / ohlcv_1h[-2][4] * 100
                else:
                    pct_1h = 0
                
                if pct_1h < config["pct_1h_min"]:
                    continue
                
                # Calculate short RSI (7-period for scalping)
                rsi_7 = self._calculate_rsi(ohlcv_1h, config["rsi_period"])
                
                # Skip if already overbought
                if rsi_7 > config["rsi_overbought"]:
                    continue
                
                # Calculate Bollinger Bands
                bb_data = self._calculate_bb(ohlcv_1h, config["bb_period"])
                
                # Orderbook imbalance check
                ob_ratio = await self._check_orderbook_imbalance(symbol, primary)
                
                # Calculate composite score
                score = self._calculate_momentum_score(
                    vol_ratio=vol_ratio,
                    pct_1h=pct_1h,
                    rsi=rsi_7,
                    bb_width=bb_data["width"],
                    ob_ratio=ob_ratio,
                )
                
                if score < 50:
                    continue
                
                # Cache momentum data
                self._momentum_cache[symbol] = {
                    "vol_ratio": vol_ratio,
                    "pct_1h": pct_1h,
                    "rsi_7": rsi_7,
                    "bb": bb_data,
                    "ob_ratio": ob_ratio,
                    "timestamp": asyncio.get_event_loop().time(),
                }
                
                candidates.append({
                    "symbol": symbol,
                    "price": price,
                    "volume": volume,
                    "pct_change": pct_24h,
                    "pct_1h": pct_1h,
                    "vol_ratio": vol_ratio,
                    "rsi_7": rsi_7,
                    "ob_ratio": ob_ratio,
                    "bb_width": bb_data["width"],
                    "bb_upper": bb_data["upper"],
                    "bb_lower": bb_data["lower"],
                    "score": score,
                    "direction": self.direction,
                    "strategy": self.name,
                    "exchange": primary,
                })
            
            except Exception as e:
                logger.debug(f"Momentum scan error {symbol}: {e}")
                continue
        
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:10]
    
    async def confirm(self, candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Confirm momentum with real-time orderbook analysis"""
        if not self.datafeed:
            return None
        
        config = self._config
        symbol = candidate["symbol"]
        exchange = candidate.get("exchange", "binance")
        
        # Real-time orderbook confirmation
        ob_ratio = await self._check_orderbook_imbalance(symbol, exchange)
        if ob_ratio < config["bid_ask_ratio_min"]:
            return None
        
        # Verify volume still elevated (avoid false signals)
        ohlcv_1h = await self.datafeed.get_ohlcv(symbol, "1h", limit=20, exchange=exchange)
        if not ohlcv_1h or len(ohlcv_1h) < 5:
            return None
        
        vol_ratio = self._calculate_volume_ratio(ohlcv_1h)
        if vol_ratio < config["vol_ratio_min"] * 0.7:  # Allow some decay
            return None
        
        # Check 15m candles for momentum continuation
        ohlcv_15m = await self.datafeed.get_ohlcv(symbol, "15m", limit=20, exchange=exchange)
        if ohlcv_15m and len(ohlcv_15m) >= 3:
            # Last 3 candles should show upward momentum
            recent_closes = [c[4] for c in ohlcv_15m[-3:]]
            if recent_closes[-1] <= recent_closes[0]:
                # Momentum fading
                if ob_ratio < config["bid_ask_ratio_min"] * 1.5:
                    return None
        
        # Calculate entry details
        ticker = await self.datafeed.get_ticker(symbol, exchange)
        current_price = ticker.get("last", candidate["price"]) if ticker else candidate["price"]
        
        return {
            "symbol": symbol,
            "direction": self.direction,
            "strategy": self.name,
            "score": candidate.get("score", 0),
            "price": current_price,
            "exchange": exchange,
            "vol_ratio": candidate.get("vol_ratio", 0),
            "ob_ratio": ob_ratio,
            "rsi_7": candidate.get("rsi_7", 50),
            "pct_1h": candidate.get("pct_1h", 0),
            "tp1_pct": config["tp1_pct"],
            "tp2_pct": config["tp2_pct"],
            "hard_stop_pct": config["hard_stop_pct"],
            "trail_activate_pct": config["trail_activate_pct"],
            "max_hold_minutes": config["max_hold_minutes"],
            "default_stake_pct": config["default_stake_pct"],
            "leverage": config["leverage"],
        }
    
    async def _check_orderbook_imbalance(
        self,
        symbol: str,
        exchange: str,
    ) -> float:
        """
        Calculate orderbook bid/ask imbalance ratio.
        Ratio > 1.0 means more buying pressure (bullish).
        """
        config = self._config
        
        try:
            orderbook = await self.datafeed.get_orderbook(
                symbol, limit=config["depth_levels"], exchange=exchange
            )
            
            if not orderbook:
                return 1.0
            
            bids = orderbook.get("bids", [])
            asks = orderbook.get("asks", [])
            
            if not bids or not asks:
                return 1.0
            
            bid_volume = sum(b[1] for b in bids[:config["depth_levels"]])
            ask_volume = sum(a[1] for a in asks[:config["depth_levels"]])
            
            if ask_volume <= 0:
                return 10.0  # Strong bullish
            
            return bid_volume / ask_volume
        
        except Exception as e:
            logger.debug(f"Orderbook check failed for {symbol}: {e}")
            return 1.0
    
    def _calculate_volume_ratio(self, ohlcv: List) -> float:
        """Calculate current volume vs average"""
        if len(ohlcv) < 7:
            return 1.0
        recent = ohlcv[-1][5]
        avg = sum(c[5] for c in ohlcv[-7:]) / 7
        return recent / avg if avg > 0 else 1.0
    
    def _calculate_bb(self, ohlcv: List, period: int = 20) -> Dict[str, float]:
        """Calculate Bollinger Bands"""
        if len(ohlcv) < period:
            return {"upper": 0, "middle": 0, "lower": 0, "width": 1.0}
        
        closes = np.array([c[4] for c in ohlcv[-period:]])
        middle = closes.mean()
        std = closes.std()
        
        upper = middle + 2 * std
        lower = middle - 2 * std
        width = (upper - lower) / middle if middle > 0 else 1.0
        
        return {
            "upper": float(upper),
            "middle": float(middle),
            "lower": float(lower),
            "width": float(width),
        }
    
    def _calculate_rsi(self, ohlcv: List, period: int = 7) -> float:
        """Calculate short-period RSI for scalping"""
        if len(ohlcv) < period + 1:
            return 50.0
        
        closes = [c[4] for c in ohlcv]
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 2)
    
    def _calculate_momentum_score(
        self,
        vol_ratio: float,
        pct_1h: float,
        rsi: float,
        bb_width: float,
        ob_ratio: float,
    ) -> int:
        """Calculate momentum composite score (0-100)"""
        score = 0
        
        # Volume surge (0-25)
        if vol_ratio >= 5:
            score += 25
        elif vol_ratio >= 3:
            score += 20
        elif vol_ratio >= 2.5:
            score += 15
        elif vol_ratio >= 2:
            score += 10
        
        # 1h price momentum (0-25)
        if pct_1h >= 8:
            score += 25
        elif pct_1h >= 5:
            score += 20
        elif pct_1h >= 3:
            score += 15
        elif pct_1h >= 2:
            score += 10
        
        # RSI position (0-15)
        if 40 <= rsi <= 60:
            score += 15  # Neutral, room to move
        elif 30 <= rsi < 40:
            score += 12  # Slightly oversold
        elif 60 < rsi <= 70:
            score += 10  # Bullish but not overbought
        else:
            score += 5
        
        # Bollinger squeeze (0-15)
        if bb_width < 0.02:
            score += 15  # Tight squeeze
        elif bb_width < 0.04:
            score += 10
        elif bb_width < 0.06:
            score += 7
        else:
            score += 3
        
        # Orderbook imbalance (0-20)
        if ob_ratio >= 3.0:
            score += 20
        elif ob_ratio >= 2.0:
            score += 15
        elif ob_ratio >= 1.5:
            score += 10
        elif ob_ratio >= 1.2:
            score += 5
        
        return min(score, 100)
    
    def get_multiplier(self, regime: str = "ranging") -> float:
        """Momentum scalping works best in trending and high-vol markets"""
        multipliers = {
            "trending_up": 1.3,
            "trending_down": 0.5,
            "ranging": 0.8,
            "high_vol": 1.5,      # Best environment
            "crash": 0.0,         # Too risky
            "recovery": 1.2,
        }
        return multipliers.get(regime, 1.0)
