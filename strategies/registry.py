"""
策略注册表
"""

import logging
from typing import Any, Dict, List, Optional

from .base import BaseStrategy
from .long_oversold import LongOversoldStrategy
from .prepump_sniffer import PrePumpSnifferStrategy

logger = logging.getLogger("nexus.strategy.registry")


class StrategyRegistry:
    """
    策略注册表
    
    管理所有策略的注册和查询
    """
    
    def __init__(self, datafeed=None):
        self.datafeed = datafeed
        self._strategies: Dict[str, BaseStrategy] = {}
        
        # 注册默认策略
        self._register_defaults()
    
    def _register_defaults(self) -> None:
        """注册默认策略"""
        self.register(LongOversoldStrategy(self.datafeed))
        self.register(PrePumpSnifferStrategy(self.datafeed))
    
    def register(self, strategy: BaseStrategy) -> None:
        """注册策略"""
        self._strategies[strategy.name] = strategy
        logger.info(f"Strategy registered: {strategy.name}")
    
    def get(self, name: str) -> Optional[BaseStrategy]:
        """获取策略"""
        return self._strategies.get(name)
    
    def get_all(self) -> Dict[str, BaseStrategy]:
        """获取所有策略"""
        return self._strategies.copy()
    
    def get_enabled(self) -> List[BaseStrategy]:
        """获取启用的策略"""
        return [s for s in self._strategies.values() if s.is_enabled]
    
    def get_by_direction(self, direction: str) -> List[BaseStrategy]:
        """按方向获取策略"""
        return [s for s in self._strategies.values() 
                if s.direction in (direction, "BOTH") and s.is_enabled]
    
    @property
    def strategy_names(self) -> List[str]:
        return list(self._strategies.keys())
