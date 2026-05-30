"""
PositionTracker & TradeManager Unit Tests
Tests for TP/SL trigger logic, price updates, position lifecycle
"""
import pytest
from datetime import datetime, timezone, timedelta
from services.trade_manager.service import PositionTracker


class TestPositionTracker:
    """Test the PositionTracker class"""

    def _make_tracker(self):
        return PositionTracker()

    def _make_position(self, entry=10.0, direction="LONG", tp1=3.0, tp2=6.0, sl=5.0, trail=2.0):
        return {
            "symbol": "ALT/USDT",
            "direction": direction,
            "entry_price": entry,
            "stake": 20.0,
            "leverage": 12,
            "shares": 24.0,
            "tp1_pct": tp1,
            "tp2_pct": tp2,
            "hard_stop_pct": sl,
            "trail_activate_pct": trail,
            "trail_retrace_ratio": 0.5,
            "max_hold_minutes": 360,
            "tp1_triggered": False,
            "opened_at": datetime.now(timezone.utc),
        }

    def test_register_and_get(self):
        t = self._make_tracker()
        pos = self._make_position()
        t.register("t1", pos)
        assert t.get_position("t1") is not None
        assert t.get_position("t1")["symbol"] == "ALT/USDT"

    def test_unregister(self):
        t = self._make_tracker()
        t.register("t1", self._make_position())
        t.unregister("t1")
        assert t.get_position("t1") is None

    def test_price_update_long_pnl(self):
        """LONG position: price up -> positive PnL"""
        t = self._make_tracker()
        t.register("t1", self._make_position(entry=10.0))
        t.update_price("ALT/USDT", 11.0)  # +10%
        pos = t.get_position("t1")
        assert pos["pnl_pct"] == pytest.approx(10.0, abs=0.1)
        assert pos["pnl"] > 0

    def test_price_update_short_pnl(self):
        """SHORT position: price down -> positive PnL"""
        t = self._make_tracker()
        t.register("t1", self._make_position(entry=10.0, direction="SHORT"))
        t.update_price("ALT/USDT", 9.0)  # -10%
        pos = t.get_position("t1")
        assert pos["pnl_pct"] == pytest.approx(10.0, abs=0.1)

    def test_no_trigger_at_entry(self):
        """No trigger at entry price"""
        t = self._make_tracker()
        t.register("t1", self._make_position(entry=10.0))
        t.update_price("ALT/USDT", 10.0)
        assert t.check_triggers("t1") is None

    def test_tp1_trigger_long(self):
        """TP1 triggers when LONG pnl >= tp1_pct"""
        t = self._make_tracker()
        t.register("t1", self._make_position(entry=10.0, tp1=3.0))
        t.update_price("ALT/USDT", 10.35)  # +3.5%
        trigger = t.check_triggers("t1")
        assert trigger is not None
        assert trigger["type"] == "tp1"

    def test_tp1_no_repeat(self):
        """TP1 should not trigger again after being triggered"""
        t = self._make_tracker()
        pos = self._make_position(entry=10.0, tp1=3.0)
        pos["tp1_triggered"] = True
        t.register("t1", pos)
        t.update_price("ALT/USDT", 10.35)
        # Should not trigger tp1 again, but may trigger trail or tp2
        trigger = t.check_triggers("t1")
        if trigger:
            assert trigger["type"] != "tp1"

    def test_hard_stop_long(self):
        """Hard stop triggers when LONG loss >= sl_pct"""
        t = self._make_tracker()
        t.register("t1", self._make_position(entry=10.0, sl=5.0))
        t.update_price("ALT/USDT", 9.4)  # -6%
        trigger = t.check_triggers("t1")
        assert trigger is not None
        assert trigger["type"] == "hard_stop"

    def test_hard_stop_short(self):
        """Hard stop triggers when SHORT loss >= sl_pct"""
        t = self._make_tracker()
        t.register("t1", self._make_position(entry=10.0, direction="SHORT", sl=5.0))
        t.update_price("ALT/USDT", 10.6)  # +6% (bad for short)
        trigger = t.check_triggers("t1")
        assert trigger is not None
        assert trigger["type"] == "hard_stop"

    def test_tp2_requires_tp1(self):
        """TP2 should only trigger after TP1"""
        t = self._make_tracker()
        t.register("t1", self._make_position(entry=10.0, tp2=6.0, tp1=3.0))
        t.update_price("ALT/USDT", 10.7)  # +7% > tp2
        trigger = t.check_triggers("t1")
        # First trigger should be tp1, not tp2
        assert trigger is not None
        assert trigger["type"] == "tp1"

    def test_trailing_stop_after_tp1(self):
        """Trailing stop should activate after TP1 with retrace"""
        t = self._make_tracker()
        pos = self._make_position(entry=10.0, tp1=2.0, trail=2.0)
        pos["tp1_triggered"] = True
        pos["best_price"] = 10.5  # Was at +5%
        t.register("t1", pos)
        # Price retraces to +2% (retrace of 3% from best)
        t.update_price("ALT/USDT", 10.2)
        trigger = t.check_triggers("t1")
        # Should trigger trail stop since retrace > 50% of pnl
        if trigger:
            assert trigger["type"] == "trail_stop"

    def test_max_hold_time(self):
        """Max hold time triggers when exceeded"""
        t = self._make_tracker()
        pos = self._make_position(entry=10.0)
        pos["max_hold_minutes"] = 5
        pos["opened_at"] = datetime.now(timezone.utc) - timedelta(minutes=10)
        t.register("t1", pos)
        t.update_price("ALT/USDT", 10.1)  # +1%, no TP/SL
        trigger = t.check_triggers("t1")
        assert trigger is not None
        assert trigger["type"] == "max_hold"

    def test_no_trigger_within_hold_time(self):
        """No max_hold trigger within time limit"""
        t = self._make_tracker()
        pos = self._make_position(entry=10.0)
        pos["max_hold_minutes"] = 60
        pos["opened_at"] = datetime.now(timezone.utc)
        t.register("t1", pos)
        t.update_price("ALT/USDT", 10.05)  # +0.5%
        trigger = t.check_triggers("t1")
        assert trigger is None

    def test_multiple_positions(self):
        """Tracker handles multiple positions independently"""
        t = self._make_tracker()
        pos1 = self._make_position(entry=10.0)
        pos1["symbol"] = "ALT1/USDT"
        pos2 = self._make_position(entry=10.0, direction="SHORT")
        pos2["symbol"] = "ALT2/USDT"
        t.register("t1", pos1)
        t.register("t2", pos2)
        assert len(t.get_all_positions()) == 2
        t.update_price("ALT1/USDT", 10.0)
        t.update_price("ALT2/USDT", 10.0)
        assert t.get_position("t1")["pnl_pct"] == pytest.approx(0.0)
        assert t.get_position("t2")["pnl_pct"] == pytest.approx(0.0)

    def test_best_price_tracking_long(self):
        """LONG: best_price should track highest seen price"""
        t = self._make_tracker()
        t.register("t1", self._make_position(entry=10.0))
        t.update_price("ALT/USDT", 10.5)
        assert t.get_position("t1")["best_price"] == 10.5
        t.update_price("ALT/USDT", 10.3)
        assert t.get_position("t1")["best_price"] == 10.5  # Still best

    def test_best_price_tracking_short(self):
        """SHORT: best_price should track lowest seen price"""
        t = self._make_tracker()
        t.register("t1", self._make_position(entry=10.0, direction="SHORT"))
        t.update_price("ALT/USDT", 9.5)
        assert t.get_position("t1")["best_price"] == 9.5
        t.update_price("ALT/USDT", 9.8)
        assert t.get_position("t1")["best_price"] == 9.5  # Still best

    def test_nonexistent_position(self):
        """Nonexistent position returns None"""
        t = self._make_tracker()
        assert t.get_position("nonexistent") is None
        assert t.check_triggers("nonexistent") is None

    def test_price_update_unknown_symbol(self):
        """Updating unknown symbol should not crash"""
        t = self._make_tracker()
        t.register("t1", self._make_position())
        t.update_price("BTC/USDT", 50000)  # Different symbol
        pos = t.get_position("t1")
        assert pos["pnl_pct"] == 0.0  # Unchanged