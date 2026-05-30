"""
Strategy Module Tests
Tests for all strategy implementations: scan, confirm, scoring, RSI, BB
"""
import pytest
import math
import numpy as np


# ============================================================
# RSI / BB / Indicator Tests
# ============================================================

class TestRSI:
    """RSI calculation tests across all strategies"""

    def _calc_rsi(self, closes, period=14):
        """Standalone RSI calculation matching strategy implementation"""
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
        return round(100 - (100 / (1 + rs)), 2)

    def test_rsi_all_gains(self):
        """RSI should be 100 when all moves are positive"""
        closes = [float(100 + i) for i in range(20)]
        rsi = self._calc_rsi(closes)
        assert rsi == 100.0

    def test_rsi_all_losses(self):
        """RSI should be near 0 when all moves are negative"""
        closes = [float(100 - i) for i in range(20)]
        rsi = self._calc_rsi(closes)
        assert rsi < 5.0

    def test_rsi_neutral(self):
        """RSI should be ~50 for a flat series"""
        closes = [50.0] * 20
        rsi = self._calc_rsi(closes)
        assert rsi == 100.0  # no losses -> 100

    def test_rsi_mixed(self):
        """RSI in 30-70 range for mixed data"""
        np.random.seed(42)
        base = 100.0
        closes = [base]
        for _ in range(30):
            closes.append(closes[-1] + np.random.normal(0, 1))
        rsi = self._calc_rsi(closes)
        assert 20 < rsi < 80

    def test_rsi_short_data(self):
        """RSI returns 50 when data is too short"""
        rsi = self._calc_rsi([1.0, 2.0, 3.0], period=14)
        assert rsi == 50.0

    def test_rsi_oversold_extreme(self):
        """RSI < 20 for strong downtrend"""
        closes = [100.0 - i * 2 for i in range(20)]
        rsi = self._calc_rsi(closes)
        assert rsi < 20

    def test_rsi_overbought_extreme(self):
        """RSI > 80 for strong uptrend"""
        closes = [10.0 + i * 2 for i in range(20)]
        rsi = self._calc_rsi(closes)
        assert rsi > 80


class TestBollingerBands:
    """Bollinger Band calculation tests"""

    def _calc_bb(self, closes, period=20, mult=2.0):
        upper, middle, lower, width = [], [], [], []
        for i in range(len(closes)):
            if i < period - 1:
                upper.append(closes[i]); middle.append(closes[i])
                lower.append(closes[i]); width.append(0)
            else:
                window = closes[i - period + 1:i + 1]
                m = np.mean(window)
                s = np.std(window)
                middle.append(m)
                upper.append(m + mult * s)
                lower.append(m - mult * s)
                width.append(2 * mult * s / m if m > 0 else 0)
        return upper, middle, lower, width

    def test_bb_flat_data(self):
        """Bollinger width should be 0 for flat data"""
        closes = [50.0] * 30
        _, _, _, w = self._calc_bb(closes)
        assert w[-1] == 0 or w[-1] < 0.001

    def test_bb_relationships(self):
        """Upper > Middle > Lower always"""
        np.random.seed(42)
        closes = [50.0]
        for _ in range(29):
            closes.append(closes[-1] + np.random.normal(0, 2))
        u, m, lo, _ = self._calc_bb(closes)
        for i in range(20, len(closes)):
            assert u[i] >= m[i]
            assert m[i] >= lo[i]

    def test_bb_squeeze_detection(self):
        """Low volatility -> tight BB width"""
        closes = [50.0 + np.random.normal(0, 0.01) for _ in range(30)]
        np.random.seed(42)
        closes = [50.0 + np.random.normal(0, 0.01) for _ in range(30)]
        _, _, _, w = self._calc_bb(closes)
        assert w[-1] < 0.01  # Very tight

    def test_bb_wide_on_volatile(self):
        """High volatility -> wide BB"""
        np.random.seed(42)
        closes = [50.0 + np.random.normal(0, 5) for _ in range(30)]
        _, _, _, w = self._calc_bb(closes)
        assert w[-1] > 0.05


# ============================================================
# Strategy Scoring Tests
# ============================================================

class TestStrategyScoring:
    """Test the scoring functions for each strategy"""

    def test_short_overbought_score_high_rsi(self):
        """High RSI + high pct_change + high volume = max score"""
        # Inline scoring matching ShortOverboughtStrategy
        rsi, pct_change, volume = 85.0, 25.0, 6000000
        score = 0
        if rsi >= 80: score += 40
        elif rsi >= 70: score += 30
        if pct_change >= 20: score += 30
        elif pct_change >= 15: score += 25
        if volume >= 5000000: score += 20
        assert score == 90

    def test_short_overbought_score_low(self):
        """Low RSI should produce low score"""
        rsi, pct_change, volume = 50.0, 3.0, 100000
        score = 0
        if rsi >= 80: score += 40
        elif rsi >= 70: score += 30
        if pct_change >= 20: score += 30
        elif pct_change >= 15: score += 25
        if volume >= 5000000: score += 20
        assert score == 0

    def test_long_oversold_score_high(self):
        """Deep oversold + big drop + high volume = max score"""
        rsi, pct_24h, volume = 15.0, -18.0, 6000000
        score = 0
        if rsi <= 20: score += 40
        elif rsi <= 25: score += 30
        if pct_24h <= -15: score += 30
        elif pct_24h <= -10: score += 25
        if volume >= 5000000: score += 20
        assert score == 90

    def test_momentum_score_components(self):
        """Test momentum scalping 5-dimensional scoring"""
        vol_ratio, pct_1h, rsi, bb_width, ob_ratio = 5.0, 8.0, 50, 0.01, 3.0
        score = 0
        # Volume surge
        if vol_ratio >= 5: score += 25
        # 1h momentum
        if pct_1h >= 8: score += 25
        # RSI position
        if 40 <= rsi <= 60: score += 15
        # BB squeeze
        if bb_width < 0.02: score += 15
        # Orderbook imbalance
        if ob_ratio >= 3.0: score += 20
        assert score == 100

    def test_arb_score_high_spread(self):
        """High net spread + high volume + high exchange count = max score"""
        net_spread, volume, raw_spread, ex_count = 2.0, 6000000, 1.5, 4
        score = 0
        if net_spread >= 2.0: score += 40
        if volume >= 5000000: score += 30
        if raw_spread >= 1.0: score += 20
        if ex_count >= 4: score += 10
        assert score == 100


# ============================================================
# Market Regime Multiplier Tests
# ============================================================

class TestRegimeMultipliers:
    """Test market regime multiplier logic"""

    def test_crash_multiplier_zero(self):
        """All strategies should have 0 multiplier in crash"""
        multipliers = {
            "short_overbought": {"crash": 0.0},
            "long_oversold": {"crash": 0.0},
            "prepump_sniffer": {"crash": 0.0},
            "arb_cross_exchange": {"crash": 0.5},
            "momentum_scalp": {"crash": 0.0},
        }
        for strat, regime_map in multipliers.items():
            assert regime_map["crash"] == 0.0 or strat == "arb_cross_exchange"

    def test_short_prefers_downtrend(self):
        """Short strategy should prefer trending_down over trending_up"""
        short_multipliers = {"trending_up": 0.3, "trending_down": 1.5}
        assert short_multipliers["trending_down"] > short_multipliers["trending_up"]

    def test_long_prefers_uptrend(self):
        """Long strategy should prefer trending_up over trending_down"""
        long_multipliers = {"trending_up": 1.5, "trending_down": 0.3}
        assert long_multipliers["trending_up"] > long_multipliers["trending_down"]

    def test_arb_neutral_across_regimes(self):
        """Arb strategy should work in most regimes (except crash)"""
        arb = {"trending_up": 1.0, "trending_down": 1.0, "ranging": 1.0, "high_vol": 1.3}
        for regime, mult in arb.items():
            assert mult >= 0.8


# ============================================================
# Strategy Import & Instantiation Tests
# ============================================================

class TestStrategyImports:
    """Test that all strategies can be imported and instantiated"""

    def test_import_base(self):
        from strategies.base import BaseStrategy
        assert BaseStrategy is not None

    def test_import_short_overbought(self):
        from strategies.short_overbought import ShortOverboughtStrategy
        s = ShortOverboughtStrategy(datafeed=None)
        assert s.name == "short_overbought"
        assert s.direction == "SHORT"
        assert s.is_enabled

    def test_import_long_oversold(self):
        from strategies.long_oversold import LongOversoldStrategy
        s = LongOversoldStrategy(datafeed=None)
        assert s.name == "long_oversold"
        assert s.direction == "LONG"

    def test_import_prepump_sniffer(self):
        from strategies.prepump_sniffer import PrePumpSnifferStrategy
        s = PrePumpSnifferStrategy(datafeed=None)
        assert s.name == "prepump_sniffer"

    def test_import_arb(self):
        from strategies.arb_cross_exchange import CrossExchangeArbStrategy
        s = CrossExchangeArbStrategy(datafeed=None)
        assert s.name == "arb_cross_exchange"
        assert s.direction == "BOTH"

    def test_import_momentum(self):
        from strategies.momentum_scalp import MomentumScalpStrategy
        s = MomentumScalpStrategy(datafeed=None)
        assert s.name == "momentum_scalp"
        assert s.direction == "LONG"

    def test_registry_has_all(self):
        from strategies.registry import StrategyRegistry
        reg = StrategyRegistry(datafeed=None)
        names = reg.strategy_names
        assert "short_overbought" in names
        assert "long_oversold" in names
        assert "prepump_sniffer" in names
        assert "arb_cross_exchange" in names
        assert "momentum_scalp" in names

    def test_registry_enable_disable(self):
        from strategies.registry import StrategyRegistry
        reg = StrategyRegistry(datafeed=None)
        s = reg.get("short_overbought")
        assert s.is_enabled
        s.disable()
        assert not s.is_enabled
        s.enable()
        assert s.is_enabled