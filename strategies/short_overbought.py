"""
Short Overbought Strategy (short_overbought)
Scans for overbought altcoins to short.
"""

import logging
from typing import Any, Dict, List, Optional

from .base import BaseStrategy

logger = logging.getLogger("nexus.strategy.short_overbought")


class ShortOverboughtStrategy(BaseStrategy):
    """
    Short Overbought Strategy
    
    Logic:
    1. Scan 24h volume + pct change filters
    2. Confirm with 4h RSI overbought + funding rate
    3. BTC filter to avoid extreme conditions
    
    Market regime multipliers:
    - trending_down: 1.5 (short with trend)
    - ranging: 1.0
    - trending_up: 0.3 (counter-trend caution)
    - crash: 0.0 (pause)
    """
    
    name = "short_overbought"
    direction = "SHORT"
    description = "Short overbought altcoins"
    
    def __init__(self, datafeed=None, config=None):
        super().__init__(datafeed, config)
        
        # Default config
        self._config = {
            # Scan params
            "vol_min": 500000,
            "price_max": 100.0,
            "pct_24h_min": 5.0,
            
            # RSI params
            "rsi_period": 14,
            "daily_rsi_min": 70,
            "h4_rsi_enter": 65,
            "h4_rsi_drop": 10,
            "h4_rsi_peak_lookback": 12,
            
            # Funding params
            "funding_min": -0.005,
            "funding_max": 0.01,
            
            # BTC filter
            "btc_filter_enabled": True,
            "btc_crash_threshold": -5.0,
            "btc_pump_threshold": 8.0,
            
            # Scoring thresholds
            "score_full_threshold": 80,
            "score_half_threshold": 60,
            
            # TP/SL
            "tp1_pct": 3.0,
            "tp2_pct": 6.0,
            "hard_stop_pct": 5.0,
            "trail_activate_pct": 2.0,
        }
        self._config.update(config or {})
    
    async def scan(self) -> List[Dict[str, Any]]:
        """Scan overbought targets - multi-exchange aggregation"""
        if not self.datafeed:
            return []
        
        config = self._config
        
        # Scan all connected exchanges
        candidates = await self.datafeed.scan_potential_symbols(
            min_volume=config["vol_min"],
            min_pct_change=config["pct_24h_min"],
            max_price=config["price_max"],
            exchange=None,
        )
        
        # Filter and score
        scored_candidates = []
        for candidate in candidates:
            try:
                ohlcv = await self.datafeed.get_ohlcv(
                    candidate["symbol"],
                    "1d",
                    limit=20,
                    exchange=candidate["exchange"],
                )
                if not ohlcv:
                    continue
                
                rsi = self._calculate_rsi(ohlcv, config["rsi_period"])
                if rsi < config["daily_rsi_min"]:
                    continue
                
                score = self._calculate_score(
                    rsi=rsi,
                    pct_change=candidate["pct_change"],
                    volume=candidate["volume"],
                )
                
                candidate["rsi_1d"] = rsi
                candidate["score"] = score
                
                scored_candidates.append(candidate)
            except Exception as e:
                logger.debug(f"Error scoring {candidate['symbol']}: {e}")
                continue
        
        scored_candidates.sort(key=lambda x: x["score"], reverse=True)
        return scored_candidates[:10]
    
    async def confirm(self, candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Confirm candidate"""
        if not self.datafeed:
            return None
        
        config = self._config
        symbol = candidate["symbol"]
        exchange = candidate.get("exchange", "binance")
        
        # Get 4h K-line
        ohlcv_4h = await self.datafeed.get_ohlcv(
            symbol, "4h", limit=50, exchange=exchange
        )
        if not ohlcv_4h:
            return None
        
        rsi_4h = self._calculate_rsi(ohlcv_4h, config["rsi_period"])
        if rsi_4h < config["h4_rsi_enter"]:
            return None
        
        # Funding rate
        funding = await self.datafeed.get_funding_rate(symbol, exchange)
        funding_rate = funding.get("fundingRate", 0) if funding else 0
        
        if funding_rate < config["funding_min"] or funding_rate > config["funding_max"]:
            return None
        
        # BTC filter
        if config["btc_filter_enabled"]:
            primary_exchange = self.settings.exchange.primary_exchange if hasattr(self, 'settings') else "binance"
            btc_ticker = await self.datafeed.get_ticker("BTC/USDT", primary_exchange)
            if btc_ticker:
                btc_pct = btc_ticker.get("percentage", 0)
                if btc_pct < config["btc_crash_threshold"] or btc_pct > config["btc_pump_threshold"]:
                    return None
        
        # Smart exchange selection
        target_exchange = await self._select_best_exchange(symbol, exchange)
        
        return {
            "symbol": symbol,
            "direction": self.direction,
            "strategy": self.name,
            "rsi_1d": candidate.get("rsi_1d", 0),
            "rsi_4h": rsi_4h,
            "funding_rate": funding_rate,
            "score": candidate.get("score", 0),
            "price": candidate["price"],
            "exchange": target_exchange,
            "tp1_pct": config["tp1_pct"],
            "tp2_pct": config["tp2_pct"],
            "hard_stop_pct": config["hard_stop_pct"],
            "trail_activate_pct": config["trail_activate_pct"],
        }
    
    async def _select_best_exchange(self, symbol: str, scan_exchange: str) -> str:
        """Smart exchange selection for execution"""
        if not self.datafeed:
            return scan_exchange
        
        primary = "binance"
        if hasattr(self, 'settings'):
            primary = self.settings.exchange.primary_exchange
        
        primary_ticker = await self.datafeed.get_ticker(symbol, primary)
        if primary_ticker:
            scan_ticker = await self.datafeed.get_ticker(symbol, scan_exchange)
            if scan_ticker:
                primary_vol = primary_ticker.get("quoteVolume", 0)
                scan_vol = scan_ticker.get("quoteVolume", 0)
                if primary_vol > scan_vol * 0.5:
                    return primary
            return primary
        
        return scan_exchange
    
    def get_multiplier(self, regime: str = "ranging") -> float:
        """Market regime multiplier"""
        multipliers = {
            "trending_up": 0.3,
            "trending_down": 1.5,
            "ranging": 1.0,
            "high_vol": 0.5,
            "crash": 0.0,
            "recovery": 0.5,
        }
        return multipliers.get(regime, 1.0)
    
    def _calculate_rsi(self, ohlcv: List, period: int = 14) -> float:
        """Calculate RSI"""
        if len(ohlcv) < period + 1:
            return 50.0
        
        closes = [candle[4] for candle in ohlcv]
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 2)
    
    def _calculate_score(self, rsi: float, pct_change: float, volume: float) -> int:
        """Calculate composite score"""
        score = 0
        
        if rsi >= 80:
            score += 40
        elif rsi >= 70:
            score += 30
        elif rsi >= 65:
            score += 20
        
        if pct_change >= 20:
            score += 30
        elif pct_change >= 15:
            score += 25
        elif pct_change >= 10:
            score += 20
        elif pct_change >= 5:
            score += 15
        
        if volume >= 5000000:
            score += 20
        elif volume >= 2000000:
            score += 15
        elif volume >= 1000000:
            score += 10
        elif volume >= 500000:
            score += 5
        
        return min(score, 100)
