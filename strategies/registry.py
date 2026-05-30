"""
Strategy registry
"""

import logging
from typing import Any, Dict, List, Optional

from .base import BaseStrategy
from .short_overbought import ShortOverboughtStrategy
from .long_oversold import LongOversoldStrategy
from .prepump_sniffer import PrePumpSnifferStrategy
from .arb_cross_exchange import CrossExchangeArbStrategy
from .momentum_scalp import MomentumScalpStrategy

logger = logging.getLogger("nexus.strategy.registry")


class StrategyRegistry:
    """
    Strategy registry
    
    Manages registration and lookup of all strategies.
    """
    
    def __init__(self, datafeed=None):
        self.datafeed = datafeed
        self._strategies: Dict[str, BaseStrategy] = {}
        self._register_defaults()
    
    def _register_defaults(self) -> None:
        self.register(ShortOverboughtStrategy(self.datafeed))
        self.register(LongOversoldStrategy(self.datafeed))
        self.register(PrePumpSnifferStrategy(self.datafeed))
        self.register(CrossExchangeArbStrategy(self.datafeed))
        self.register(MomentumScalpStrategy(self.datafeed))
    
    def register(self, strategy: BaseStrategy) -> None:
        self._strategies[strategy.name] = strategy
        logger.info(f"Strategy registered: {strategy.name}")
    
    def get(self, name: str) -> Optional[BaseStrategy]:
        return self._strategies.get(name)
    
    def get_all(self) -> Dict[str, BaseStrategy]:
        return self._strategies.copy()
    
    def get_enabled(self) -> List[BaseStrategy]:
        return [s for s in self._strategies.values() if s.is_enabled]
    
    def get_by_direction(self, direction: str) -> List[BaseStrategy]:
        return [s for s in self._strategies.values()
                if s.direction in (direction, "BOTH") and s.is_enabled]
    
    @property
    def strategy_names(self) -> List[str]:
        return list(self._strategies.keys())
