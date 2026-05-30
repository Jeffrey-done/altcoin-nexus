"""
Backtesting Engine Tests
Validates backtest logic: data generation, trade simulation, equity curves
"""
import pytest
import math
import numpy as np


class TestSyntheticDataGeneration:
    """Test synthetic OHLCV data generation"""

    def _gen_simple(self, n=300, base=5.0, vol=0.08, seed=42):
        """Simple OHLCV generator matching backtest internals"""
        np.random.seed(seed)
        prices = [base]
        for _ in range(n - 1):
            ret = np.random.normal(0.0001, vol / math.sqrt(288))
            prices.append(max(prices[-1] * (1 + ret), base * 0.01))
        out = []
        for i in range(1, len(prices)):
            r = abs(prices[i] / prices[i - 1] - 1)
            h = max(prices[i], prices[i - 1]) * (1 + abs(np.random.normal(0, r * 0.3 + 0.001)))
            lo = min(prices[i], prices[i - 1]) * (1 - abs(np.random.normal(0, r * 0.3 + 0.001)))
            h = max(h, prices[i], prices[i - 1])
            lo = min(lo, prices[i], prices[i - 1])
            out.append({"open": prices[i - 1], "high": h, "low": lo,
                         "close": prices[i], "volume": 1e5 + abs(np.random.normal(0, 5e4))})
        return out

    def test_candle_count(self):
        data = self._gen_simple(300)
        assert len(data) == 299

    def test_ohlcv_keys(self):
        data = self._gen_simple(50)
        for c in data:
            assert all(k in c for k in ("open", "high", "low", "close", "volume"))

    def test_high_low_consistency(self):
        data = self._gen_simple(100)
        for c in data:
            assert c["high"] >= c["open"]
            assert c["high"] >= c["close"]
            assert c["low"] <= c["open"]
            assert c["low"] <= c["close"]

    def test_all_positive(self):
        data = self._gen_simple(100)
        for c in data:
            assert c["open"] > 0 and c["high"] > 0 and c["low"] > 0 and c["close"] > 0
            assert c["volume"] > 0

    def test_mean_reversion(self):
        np.random.seed(42)
        prices = [5.0]
        for _ in range(5000):
            ret = np.random.normal(0, 0.005)
            ret -= 0.02 * (prices[-1] - 5.0) / 5.0
            prices.append(max(prices[-1] * (1 + ret), 0.05))
        assert 3.0 < np.mean(prices) < 7.0

    def test_different_seeds_differ(self):
        d1 = self._gen_simple(50, seed=1)
        d2 = self._gen_simple(50, seed=2)
        assert d1[0]["close"] != d2[0]["close"]


class TestTradeSimulation:
    """Test trade PnL calculation"""

    def _pnl(self, pnl_pct, leverage=10, stake=20.0, fee=0.04, slip=0.05):
        net = (pnl_pct * leverage / 100) - (fee + slip) * 2 / 100
        return stake * net

    def test_winning_trade_positive(self):
        assert self._pnl(1.5, leverage=12) > 0

    def test_losing_trade_negative(self):
        assert self._pnl(-3.0, leverage=12) < 0

    def test_fee_impact(self):
        low = self._pnl(1.0, fee=0.02, slip=0.02)
        high = self._pnl(1.0, fee=0.10, slip=0.10)
        assert low > high

    def test_leverage_amplification(self):
        assert self._pnl(2.0, leverage=10) > self._pnl(2.0, leverage=5)

    def test_position_size_impact(self):
        assert self._pnl(1.0, stake=30) > self._pnl(1.0, stake=10)

    def test_high_win_rate_positive_with_correct_tp_sl(self):
        """
        83% win at 1.2% TP, 17% loss at 4.5% SL, 12x leverage.
        Expected per trade: 0.83 * 1.2 * 12 / 100 - 0.17 * 4.5 * 12 / 100 - fees
        = 0.1195 - 0.0918 - 0.0018 = +0.0259 per dollar staked (positive)
        """
        stake = 20.0
        total = 0.0
        wins, losses = 83, 17
        for _ in range(wins):
            total += self._pnl(1.2, leverage=12, stake=stake)
        for _ in range(losses):
            total += self._pnl(-4.5, leverage=12, stake=stake)
        assert total > 0, f"Expected profit but got {total}"


class TestEquityCurve:
    """Test equity curve and drawdown"""

    def _run(self, pnl_pcts, leverage=10, pos=0.25, cap=100.0, fee=0.04, slip=0.05):
        capital = cap; pk = cap; md = 0.0
        for p in pnl_pcts:
            sk = capital * pos
            net = p - (fee + slip) * 2
            capital += sk * (net * leverage / 100)
            capital = max(capital, 0)
            if capital > pk: pk = capital
            dd = (pk - capital) / pk * 100 if pk > 0 else 0
            md = max(md, dd)
        return capital, md

    def test_all_wins_grow(self):
        final, _ = self._run([1.5] * 20)
        assert final > 100.0

    def test_all_losses_shrink(self):
        final, _ = self._run([-3.0] * 20)
        assert final < 100.0

    def test_capital_never_negative(self):
        final, _ = self._run([-10.0] * 100)
        assert final >= 0

    def test_drawdown_tracked(self):
        _, dd = self._run([5.0, 5.0, -15.0, -10.0, 3.0])
        assert dd > 0

    def test_positive_with_realistic_params(self):
        """83% win 1.2%, 17% loss 4.5%, lev 10 -> positive with conservative sizing"""
        trades = [1.2] * 83 + [-4.5] * 17
        all_trades = trades * 5
        # Conservative: 15% position, 10x leverage, 100 trades is enough to show edge
        final, _ = self._run(all_trades, leverage=10, pos=0.15)
        assert final > 100.0

    def test_positive_with_very_conservative_sizing(self):
        """High win rate is profitable with small position sizes"""
        trades = [1.2] * 85 + [-4.5] * 15
        all_trades = trades * 3
        final, _ = self._run(all_trades, leverage=12, pos=0.10)
        assert final > 100.0


class TestBacktestIntegration:
    """Integration test using actual run_90day_bt module"""

    def test_module_imports(self):
        """Module should be importable"""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from backtesting.run_90day_bt import sim_trade, run_sim
        assert callable(sim_trade)
        assert callable(run_sim)

    def test_sim_trade_returns_tuple(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from backtesting.run_90day_bt import sim_trade
        result = sim_trade({"win_rate": 0.8, "avg_win_pct": 1.2, "avg_loss_pct": 4.0, "leverage": 12}, 100.0)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_run_sim_returns_dict(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from backtesting.run_90day_bt import run_sim
        result = run_sim(50)
        assert "final" in result
        assert "wr" in result
        assert "ret" in result
        assert "dd" in result

    def test_high_wr_strategy_profile(self):
        """A strategy with 85% WR and good TP/SL should be profitable"""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from backtesting.run_90day_bt import sim_trade
        np.random.seed(42)
        total_pnl = 0.0
        for _ in range(1000):
            pnl, _ = sim_trade({"win_rate": 0.85, "avg_win_pct": 1.2, "avg_loss_pct": 4.0, "leverage": 12}, 20.0)
            total_pnl += pnl
        assert total_pnl > 0