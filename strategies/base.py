"""
策略基类
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger("nexus.strategy")


class BaseStrategy(ABC):
    """
    策略基类
    
    所有策略必须继承此类并实现抽象方法
    """
    
    name: str = "base"
    direction: str = "SHORT"  # SHORT / LONG / BOTH
    description: str = ""
    
    def __init__(self, datafeed=None, config: Optional[Dict] = None):
        self.datafeed = datafeed
        self.config = config or {}
        self._enabled = True
    
    @abstractmethod
    async def scan(self) -> List[Dict[str, Any]]:
        """
        扫描潜在标的
        
        Returns:
            候选列表 [{symbol, price, volume, score, ...}]
        """
        raise NotImplementedError
    
    @abstractmethod
    async def confirm(self, candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        确认候选
        
        Args:
            candidate: 候选数据
        
        Returns:
            信号详情或 None (拒绝)
        """
        raise NotImplementedError
    
    async def should_close(self, trade: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        检查是否应该平仓
        
        Args:
            trade: 持仓数据
        
        Returns:
            平仓原因或 None
        """
        return None
    
    def get_multiplier(self, regime: str = "ranging") -> float:
        """
        获取市场状态对应的仓位乘数
        
        Args:
            regime: 市场状态
        
        Returns:
            仓位乘数 (0-2)
        """
        return 1.0
    
    @property
    def is_enabled(self) -> bool:
        return self._enabled
    
    def enable(self) -> None:
        self._enabled = True
    
    def disable(self) -> None:
        self._enabled = False
