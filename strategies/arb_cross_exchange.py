"""
Cross-Exchange Arbitrage Strategy (arb_cross_exchange)
Exploits price gaps between exchanges on volatile altcoins.

For $100 capital: targets 0.3-2% spreads on low-cap altcoins
where price divergence between exchanges is common.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .base import BaseStrategy

logger = logging.getLogger("nexus.strategy.arb_cross_exchange")


class CrossExchangeArbStrategy(BaseStrategy):
    """
    Cross-Exchange Arbitrage Strategy
    
    Logic:
    1. Scan for price divergence across exchanges (bid/ask spread)
    2. Filter by minimum spread > estimated fees + slippage
    3. Execute buy on cheaper exchange, sell on more expensive
    4. Risk: execution speed, transfer delays (use futures to avoid)
    
    For $100 capital on futures:
    - Use leveraged positions on both exchanges
    - Net exposure is zero (market neutral)
    - Profit = spread - fees - slippage
    """
    
    name = "arb_cross_exchange"
    direction = "BOTH"
    description = "Cross-exchange arbitrage on price divergences"
    
    def __init__(self, datafeed=None, config=None):
        super().__init__(datafeed, config)
        
        self._config = {
            # Minimum spread to consider (must exceed round-trip fees)
            "min_spread_pct": 0.15,       # 0.15% minimum
            "max_spread_pct": 5.0,        # Cap: >5% likely data error
            
            # Filters
            "min_volume_usdt": 200000,    # Minimum 24h volume
            "max_price": 50.0,            # Low-cap focus
            "min_price": 0.001,           # Avoid dust
            
            # Execution
            "stake_pct": 0.25,            # 25% of capital per side
            "leverage": 5,                # Conservative leverage for arb
            "max_slippage_pct": 0.3,
            
            # Scoring weights
            "spread_weight": 40,
            "volume_weight": 30,
            "volatility_weight": 20,
            "cross_exchange_count_weight": 10,
        }
        self._config.update(config or {})
        
        # Track recent spreads for stability check
        self._spread_history: Dict[str, List[float]] = {}
    
    async def scan(self) -> List[Dict[str, Any]]:
        """Scan for arbitrage opportunities across exchanges"""
        if not self.datafeed:
            return []
        
        config = self._config
        candidates = []
        
        # Get all USDT pairs from all exchanges
        all_symbols: Dict[str, Dict[str, Dict]] = {}  # symbol -> {exchange: ticker}
        
        exchanges = list(self.datafeed._exchanges.keys())
        if len(exchanges) < 2:
            logger.warning("Need at least 2 exchanges for arbitrage")
            return []
        
        # Parallel fetch from all exchanges
        fetch_tasks = []
        for ex in exchanges:
            fetch_tasks.append(self._fetch_exchange_tickers(ex))
        
        results = await asyncio.gather(*fetch_tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, dict):
                ex_name = exchanges[i]
                for symbol, ticker in result.items():
                    if not symbol.endswith("/USDT"):
                        continue
                    if symbol not in all_symbols:
                        all_symbols[symbol] = {}
                    all_symbols[symbol][ex_name] = ticker
        
        # Find arbitrage opportunities
        for symbol, exchange_tickers in all_symbols.items():
            if len(exchange_tickers) < 2:
                continue
            
            try:
                arb = self._find_arbitrage(symbol, exchange_tickers)
                if arb:
                    candidates.append(arb)
            except Exception as e:
                logger.debug(f"Arb analysis error for {symbol}: {e}")
                continue
        
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:15]
    
    async def _fetch_exchange_tickers(self, exchange: str) -> Dict[str, Any]:
        """Fetch all tickers from an exchange"""
        try:
            return await self.datafeed.get_all_tickers(exchange)
        except Exception as e:
            logger.warning(f"Failed to fetch tickers from {exchange}: {e}")
            return {}
    
    def _find_arbitrage(
        self,
        symbol: str,
        exchange_tickers: Dict[str, Dict],
    ) -> Optional[Dict[str, Any]]:
        """Find best arbitrage opportunity for a symbol"""
        config = self._config
        
        # Collect valid prices with volume filter
        valid_prices = []
        for ex_name, ticker in exchange_tickers.items():
            volume = ticker.get("quoteVolume", 0)
            if volume < config["min_volume_usdt"]:
                continue
            
            bid = ticker.get("bid", 0)
            ask = ticker.get("ask", 0)
            last = ticker.get("last", 0)
            price = last or ((bid + ask) / 2 if bid and ask else 0)
            
            if not price or price < config["min_price"] or price > config["max_price"]:
                continue
            
            valid_prices.append({
                "exchange": ex_name,
                "bid": bid,
                "ask": ask,
                "last": last,
                "price": price,
                "volume": volume,
                "spread_pct": ((ask - bid) / bid * 100) if bid and ask else 999,
            })
        
        if len(valid_prices) < 2:
            return None
        
        # Sort by price ascending (cheapest first)
        valid_prices.sort(key=lambda x: x["price"])
        
        cheapest = valid_prices[0]
        most_expensive = valid_prices[-1]
        
        # Calculate spread: buy at cheapest ask, sell at most expensive bid
        buy_price = cheapest["ask"]
        sell_price = most_expensive["bid"]
        
        if not buy_price or not sell_price or buy_price <= 0:
            return None
        
        spread_pct = (sell_price - buy_price) / buy_price * 100
        
        # Filter by spread thresholds
        if spread_pct < config["min_spread_pct"]:
            return None
        if spread_pct > config["max_spread_pct"]:
            return None
        
        # Estimate total costs (round-trip)
        exchange_fee_pct = 0.04 * 2  # 0.04% per side, twice
        est_slippage_pct = config["max_slippage_pct"] * 2
        total_cost_pct = exchange_fee_pct + est_slippage_pct
        
        net_spread_pct = spread_pct - total_cost_pct
        if net_spread_pct <= 0:
            return None
        
        # Score the opportunity
        score = self._calculate_arb_score(
            net_spread_pct,
            min(cheapest["volume"], most_expensive["volume"]),
            spread_pct,
            len(valid_prices),
        )
        
        # Check spread stability
        symbol_key = symbol
        if symbol_key not in self._spread_history:
            self._spread_history[symbol_key] = []
        self._spread_history[symbol_key].append(spread_pct)
        if len(self._spread_history[symbol_key]) > 10:
            self._spread_history[symbol_key] = self._spread_history[symbol_key][-10:]
        
        return {
            "symbol": symbol,
            "direction": "LONG",  # Direction for the buy side
            "strategy": self.name,
            "price": cheapest["price"],
            "volume": min(cheapest["volume"], most_expensive["volume"]),
            "pct_change": 0,
            "score": score,
            "arb_details": {
                "buy_exchange": cheapest["exchange"],
                "buy_price": buy_price,
                "sell_exchange": most_expensive["exchange"],
                "sell_price": sell_price,
                "spread_pct": round(spread_pct, 4),
                "net_spread_pct": round(net_spread_pct, 4),
                "estimated_cost_pct": round(total_cost_pct, 4),
            },
            "exchange": cheapest["exchange"],  # Primary execution exchange
        }
    
    def _calculate_arb_score(
        self,
        net_spread: float,
        volume: float,
        raw_spread: float,
        exchange_count: int,
    ) -> int:
        """Calculate arbitrage opportunity score"""
        config = self._config
        score = 0
        
        # Net spread score (higher = better)
        if net_spread >= 2.0:
            score += config["spread_weight"]
        elif net_spread >= 1.0:
            score += int(config["spread_weight"] * 0.8)
        elif net_spread >= 0.5:
            score += int(config["spread_weight"] * 0.6)
        elif net_spread >= 0.2:
            score += int(config["spread_weight"] * 0.4)
        else:
            score += int(config["spread_weight"] * 0.2)
        
        # Volume score
        if volume >= 5000000:
            score += config["volume_weight"]
        elif volume >= 2000000:
            score += int(config["volume_weight"] * 0.75)
        elif volume >= 500000:
            score += int(config["volume_weight"] * 0.5)
        else:
            score += int(config["volume_weight"] * 0.25)
        
        # Volatility bonus (higher raw spread = more volatile market)
        if raw_spread >= 1.0:
            score += config["volatility_weight"]
        elif raw_spread >= 0.5:
            score += int(config["volatility_weight"] * 0.7)
        else:
            score += int(config["volatility_weight"] * 0.3)
        
        # Cross-exchange availability
        if exchange_count >= 4:
            score += config["cross_exchange_count_weight"]
        elif exchange_count >= 3:
            score += int(config["cross_exchange_count_weight"] * 0.7)
        else:
            score += int(config["cross_exchange_count_weight"] * 0.4)
        
        return min(score, 100)
    
    async def confirm(self, candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Confirm arbitrage opportunity with real-time verification"""
        if not self.datafeed:
            return None
        
        config = self._config
        symbol = candidate["symbol"]
        arb = candidate.get("arb_details", {})
        
        if not arb:
            return None
        
        buy_ex = arb["buy_exchange"]
        sell_ex = arb["sell_exchange"]
        
        # Re-fetch real-time prices to confirm spread still exists
        buy_ticker = await self.datafeed.get_ticker(symbol, buy_ex)
        sell_ticker = await self.datafeed.get_ticker(symbol, sell_ex)
        
        if not buy_ticker or not sell_ticker:
            return None
        
        current_buy = buy_ticker.get("ask", 0)
        current_sell = sell_ticker.get("bid", 0)
        
        if not current_buy or not current_sell or current_buy <= 0:
            return None
        
        current_spread = (current_sell - current_buy) / current_buy * 100
        
        # Recalculate with live data
        exchange_fee_pct = 0.04 * 2
        est_slippage_pct = config["max_slippage_pct"] * 2
        net_spread = current_spread - exchange_fee_pct - est_slippage_pct
        
        if net_spread < config["min_spread_pct"]:
            return None
        
        # Check spread stability (reject if spread collapsed)
        history = self._spread_history.get(symbol, [])
        if len(history) >= 3:
            avg_spread = sum(history[-3:]) / 3
            if current_spread < avg_spread * 0.5:
                logger.info(f"Arb spread collapsed for {symbol}: {current_spread:.3f}% vs avg {avg_spread:.3f}%")
                return None
        
        return {
            "symbol": symbol,
            "direction": "LONG",
            "strategy": self.name,
            "score": candidate.get("score", 0),
            "price": current_buy,
            "exchange": buy_ex,
            "arb_details": {
                "buy_exchange": buy_ex,
                "buy_price": current_buy,
                "sell_exchange": sell_ex,
                "sell_price": current_sell,
                "spread_pct": round(current_spread, 4),
                "net_spread_pct": round(net_spread, 4),
                "stake_pct": config["stake_pct"],
                "leverage": config["leverage"],
            },
        }
    
    def get_multiplier(self, regime: str = "ranging") -> float:
        """Arb works in all regimes but reduced in crashes"""
        multipliers = {
            "trending_up": 1.0,
            "trending_down": 1.0,
            "ranging": 1.0,
            "high_vol": 1.3,     # Higher vol = more arb opportunities
            "crash": 0.5,        # Liquidity risk in crashes
            "recovery": 1.2,
        }
        return multipliers.get(regime, 1.0)
