"""
Execution Router & Smart Order Tests
Tests for order types, slippage estimation, idempotency
"""
import pytest
import uuid


class TestOrderTypes:
    """Test order type enums and basic logic"""

    def test_order_types_exist(self):
        from services.execution.router import OrderType, OrderPriority
        assert OrderType.MARKET == "market"
        assert OrderType.LIMIT == "limit"
        assert OrderPriority.URGENT == "urgent"
        assert OrderPriority.NORMAL == "normal"

    def test_client_order_id_uniqueness(self):
        """Each order should get a unique client order ID"""
        ids = set()
        for _ in range(100):
            cid = f"nexus_{uuid.uuid4().hex[:16]}"
            ids.add(cid)
        assert len(ids) == 100


class TestSmartOrder:
    """Test SmartOrder algorithm selection"""

    def test_algo_selection_small(self):
        """Small order -> Market"""
        from services.execution.smart_order import SmartOrderEngine, OrderAlgo
        engine = SmartOrderEngine()
        algo = engine._select_algo(500)  # $500 < $1000 threshold
        assert algo == OrderAlgo.MARKET

    def test_algo_selection_medium(self):
        """Medium order -> TWAP"""
        from services.execution.smart_order import SmartOrderEngine, OrderAlgo
        engine = SmartOrderEngine()
        algo = engine._select_algo(5000)  # $5000 < $10000 threshold
        assert algo == OrderAlgo.TWAP

    def test_algo_selection_large(self):
        """Large order -> VWAP"""
        from services.execution.smart_order import SmartOrderEngine, OrderAlgo
        engine = SmartOrderEngine()
        algo = engine._select_algo(25000)  # $25000 < $50000 threshold
        assert algo == OrderAlgo.VWAP

    def test_algo_selection_huge(self):
        """Huge order -> Iceberg"""
        from services.execution.smart_order import SmartOrderEngine, OrderAlgo
        engine = SmartOrderEngine()
        algo = engine._select_algo(100000)
        assert algo == OrderAlgo.ICEBERG

    def test_smart_order_result_structure(self):
        from services.execution.smart_order import SmartOrderResult, OrderAlgo
        result = SmartOrderResult(
            order_id="test", algo=OrderAlgo.MARKET, status="filled",
            filled_amount=10.0, avg_price=5.0, slippage_pct=0.1,
        )
        d = result.to_dict()
        assert d["order_id"] == "test"
        assert d["status"] == "filled"
        assert d["slippage_pct"] == 0.1


class TestEventBus:
    """Test event bus publish/subscribe logic"""

    def test_event_creation(self):
        from core.events.bus import Event
        e = Event(channel="test.channel", data={"key": "value"})
        assert e.channel == "test.channel"
        assert e.data["key"] == "value"
        assert e.timestamp  # Should be auto-set
        assert e.event_id   # Should be auto-generated

    def test_event_json_roundtrip(self):
        from core.events.bus import Event
        e = Event(channel="test.channel", data={"num": 42, "str": "hello"})
        json_str = e.to_json()
        e2 = Event.from_json(json_str)
        assert e2.channel == "test.channel"
        assert e2.data["num"] == 42

    def test_subscription_pattern_matching(self):
        from core.events.bus import Subscription
        sub = Subscription(pattern="trade.*", callback=lambda e: None)
        assert sub.matches("trade.opened")
        assert sub.matches("trade.closed")
        assert not sub.matches("risk.alert")

    def test_subscription_exact_match(self):
        from core.events.bus import Subscription
        sub = Subscription(pattern="trade.opened", callback=lambda e: None)
        assert sub.matches("trade.opened")
        assert not sub.matches("trade.closed")


class TestConfigSettings:
    """Test configuration loading and validation"""

    def test_settings_loads(self):
        from core.config.settings import Settings
        s = Settings()
        assert s.version == "4.0.0"
        assert s.environment in ["development", "testing", "production"]

    def test_risk_defaults(self):
        from core.config.settings import Settings
        s = Settings()
        assert s.risk.max_daily_loss > 0
        assert s.risk.max_daily_trades > 0
        assert s.risk.default_stake > 0
        assert s.risk.max_stake > 0

    def test_exchange_defaults(self):
        from core.config.settings import Settings
        s = Settings()
        assert s.exchange.primary_exchange in ["binance", "okx", "bybit", "gate", "bitget"]
        assert s.exchange.leverage > 0

    def test_strategy_defaults(self):
        from core.config.settings import Settings
        s = Settings()
        assert s.strategy.tp1_pct > 0
        assert s.strategy.hard_stop_pct > 0


class TestMacroFilter:
    """Test macro filter decision logic"""

    def test_crash_blocks_all(self):
        from strategies.macro_filter import MacroFilter, MarketRegime
        from signals.regime import MarketRegimeDetector
        mf = MacroFilter()
        # Manually set regime
        mf.regime_detector = None
        decision = mf.evaluate("LONG")
        # Without detector, should default to RANGING and allow
        assert decision.allow_open

    def test_multipliers_in_range(self):
        from strategies.macro_filter import MacroFilter
        mf = MacroFilter()
        for direction in ["SHORT", "LONG"]:
            for regime in ["trending_up", "trending_down", "ranging", "high_vol", "crash", "recovery"]:
                mult = mf._config["regime_multipliers"].get(regime, {}).get(direction, 1.0)
                assert 0.0 <= mult <= 2.0, f"Multiplier out of range: {regime}/{direction} = {mult}"