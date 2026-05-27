"""
异步数据馈送服务
使用 aiohttp 和 websockets 进行纯异步数据获取
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set

import aiohttp
import ccxt.async_support as ccxt

from core.config import get_settings
from core.events import get_event_bus, EventType

logger = logging.getLogger("nexus.datafeed")


class DataFeedService:
    """
    异步数据馈送服务
    
    特性:
    - 纯异步数据获取
    - 多交易所支持
    - WebSocket实时行情
    - 本地缓存
    """
    
    def __init__(self):
        self._settings = get_settings()
        self._exchanges: Dict[str, ccxt.Exchange] = {}
        self._running = False
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl: Dict[str, float] = {}
        self._ws_connections: Dict[str, Any] = {}
        self._subscriptions: Set[str] = set()
        
        # 回调
        self._price_callbacks: List[Callable] = []
        self._ticker_callbacks: List[Callable] = []
    
    async def start(self) -> None:
        """启动数据馈送服务"""
        if self._running:
            return
        
        self._running = True
        await self._init_exchanges()
        logger.info("DataFeedService started")
    
    async def stop(self) -> None:
        """停止数据馈送服务"""
        self._running = False
        
        # 关闭交易所连接
        for name, exchange in self._exchanges.items():
            try:
                await exchange.close()
            except Exception as e:
                logger.warning(f"Error closing {name}: {e}")
        
        self._exchanges.clear()
        logger.info("DataFeedService stopped")
    
    async def _init_exchanges(self) -> None:
        """初始化交易所连接"""
        config = self._settings.exchange
        
        # Binance
        if config.binance_api_key:
            try:
                self._exchanges["binance"] = ccxt.binance({
                    "apiKey": config.binance_api_key,
                    "secret": config.binance_api_secret,
                    "enableRateLimit": True,
                    "options": {"defaultType": "future"},
                })
                logger.info("Binance exchange initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Binance: {e}")
        
        # OKX
        if config.okx_api_key:
            try:
                self._exchanges["okx"] = ccxt.okx({
                    "apiKey": config.okx_api_key,
                    "secret": config.okx_api_secret,
                    "password": config.okx_passphrase,
                    "enableRateLimit": True,
                })
                logger.info("OKX exchange initialized")
            except Exception as e:
                logger.error(f"Failed to initialize OKX: {e}")
        
        # Bybit
        if config.bybit_api_key:
            try:
                self._exchanges["bybit"] = ccxt.bybit({
                    "apiKey": config.bybit_api_key,
                    "secret": config.bybit_api_secret,
                    "enableRateLimit": True,
                    "options": {"defaultType": "linear"},
                })
                logger.info("Bybit exchange initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Bybit: {e}")
        
        # Gate.io
        if config.gate_api_key:
            try:
                self._exchanges["gate"] = ccxt.gate({
                    "apiKey": config.gate_api_key,
                    "secret": config.gate_api_secret,
                    "enableRateLimit": True,
                    "options": {"defaultType": "future"},
                })
                logger.info("Gate.io exchange initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Gate.io: {e}")
        
        # Bitget
        if config.bitget_api_key:
            try:
                self._exchanges["bitget"] = ccxt.bitget({
                    "apiKey": config.bitget_api_key,
                    "secret": config.bitget_api_secret,
                    "password": config.bitget_passphrase,
                    "enableRateLimit": True,
                    "options": {"defaultType": "future"},
                })
                logger.info("Bitget exchange initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Bitget: {e}")
    
    async def get_ticker(
        self,
        symbol: str,
        exchange: str = "binance",
    ) -> Optional[Dict[str, Any]]:
        """获取实时行情"""
        cache_key = f"{exchange}:{symbol}:ticker"
        
        # 检查缓存
        if cache_key in self._cache:
            if time.time() - self._cache_ttl.get(cache_key, 0) < 5:
                return self._cache[cache_key]
        
        if exchange not in self._exchanges:
            logger.warning(f"Exchange {exchange} not available")
            return None
        
        try:
            ticker = await self._exchanges[exchange].fetch_ticker(symbol)
            
            # 更新缓存
            self._cache[cache_key] = ticker
            self._cache_ttl[cache_key] = time.time()
            
            return ticker
        except Exception as e:
            logger.error(f"Failed to fetch ticker {symbol}: {e}")
            return None
    
    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
        exchange: str = "binance",
    ) -> Optional[List[List]]:
        """获取K线数据"""
        cache_key = f"{exchange}:{symbol}:{timeframe}:ohlcv"
        
        # 检查缓存（K线数据缓存更久）
        if cache_key in self._cache:
            if time.time() - self._cache_ttl.get(cache_key, 0) < 60:
                return self._cache[cache_key]
        
        if exchange not in self._exchanges:
            logger.warning(f"Exchange {exchange} not available")
            return None
        
        try:
            ohlcv = await self._exchanges[exchange].fetch_ohlcv(
                symbol, timeframe, limit=limit
            )
            
            # 更新缓存
            self._cache[cache_key] = ohlcv
            self._cache_ttl[cache_key] = time.time()
            
            return ohlcv
        except Exception as e:
            logger.error(f"Failed to fetch OHLCV {symbol}: {e}")
            return None
    
    async def get_orderbook(
        self,
        symbol: str,
        limit: int = 20,
        exchange: str = "binance",
    ) -> Optional[Dict[str, Any]]:
        """获取订单簿"""
        if exchange not in self._exchanges:
            logger.warning(f"Exchange {exchange} not available")
            return None
        
        try:
            orderbook = await self._exchanges[exchange].fetch_order_book(
                symbol, limit=limit
            )
            return orderbook
        except Exception as e:
            logger.error(f"Failed to fetch orderbook {symbol}: {e}")
            return None
    
    async def get_funding_rate(
        self,
        symbol: str,
        exchange: str = "binance",
    ) -> Optional[Dict[str, Any]]:
        """获取资金费率"""
        if exchange not in self._exchanges:
            return None
        
        try:
            funding = await self._exchanges[exchange].fetch_funding_rate(symbol)
            return funding
        except Exception as e:
            logger.error(f"Failed to fetch funding rate {symbol}: {e}")
            return None
    
    async def get_open_interest(
        self,
        symbol: str,
        exchange: str = "binance",
    ) -> Optional[Dict[str, Any]]:
        """获取持仓量"""
        if exchange not in self._exchanges:
            return None
        
        try:
            oi = await self._exchanges[exchange].fetch_open_interest(symbol)
            return oi
        except Exception as e:
            logger.error(f"Failed to fetch open interest {symbol}: {e}")
            return None
    
    async def get_all_tickers(
        self,
        exchange: str = "binance",
    ) -> Dict[str, Any]:
        """获取所有行情"""
        if exchange not in self._exchanges:
            return {}
        
        try:
            tickers = await self._exchanges[exchange].fetch_tickers()
            return tickers
        except Exception as e:
            logger.error(f"Failed to fetch all tickers: {e}")
            return {}
    
    async def scan_potential_symbols(
        self,
        min_volume: float = 500000,
        min_pct_change: float = 5.0,
        max_price: float = 100.0,
        exchange: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        扫描潜在标的
        
        Args:
            min_volume: 最小24h成交量(USDT)
            min_pct_change: 最小24h涨幅(%)
            max_price: 最大价格
            exchange: 指定交易所，None=扫描所有已连接的交易所
        
        Returns:
            候选列表，每个候选包含 symbol, price, volume, pct_change, exchange
        """
        candidates = []
        
        # 确定要扫描的交易所列表
        if exchange:
            exchanges_to_scan = [exchange] if exchange in self._exchanges else []
        else:
            exchanges_to_scan = list(self._exchanges.keys())
        
        # 并发扫描所有交易所
        scan_tasks = []
        for ex_name in exchanges_to_scan:
            scan_tasks.append(self._scan_single_exchange(
                ex_name, min_volume, min_pct_change, max_price
            ))
        
        if scan_tasks:
            results = await asyncio.gather(*scan_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, list):
                    candidates.extend(result)
        
        # 按涨幅排序
        candidates.sort(key=lambda x: x["pct_change"], reverse=True)
        
        # 去重：同一 symbol 取流动性最好的交易所
        candidates = self._deduplicate_candidates(candidates)
        
        return candidates
    
    async def _scan_single_exchange(
        self,
        exchange: str,
        min_volume: float,
        min_pct_change: float,
        max_price: float,
    ) -> List[Dict[str, Any]]:
        """扫描单个交易所"""
        tickers = await self.get_all_tickers(exchange)
        
        candidates = []
        for symbol, ticker in tickers.items():
            try:
                # 过滤条件
                if not symbol.endswith("/USDT"):
                    continue
                
                price = ticker.get("last", 0)
                volume = ticker.get("quoteVolume", 0)
                pct_change = ticker.get("percentage", 0)
                
                if not price or not volume:
                    continue
                
                if price > max_price:
                    continue
                
                if volume < min_volume:
                    continue
                
                if pct_change < min_pct_change:
                    continue
                
                candidates.append({
                    "symbol": symbol,
                    "price": price,
                    "volume": volume,
                    "pct_change": pct_change,
                    "exchange": exchange,
                    "bid": ticker.get("bid", 0),
                    "ask": ticker.get("ask", 0),
                    "spread_pct": self._calculate_spread(ticker),
                })
            except Exception:
                continue
        
        return candidates
    
    def _calculate_spread(self, ticker: Dict) -> float:
        """计算买卖价差百分比"""
        bid = ticker.get("bid", 0)
        ask = ticker.get("ask", 0)
        if bid and ask and bid > 0:
            return round((ask - bid) / bid * 100, 4)
        return 0.0
    
    def _deduplicate_candidates(self, candidates: List[Dict]) -> List[Dict]:
        """
        去重候选：同一 symbol 取流动性最好(成交量最大)的交易所
        """
        seen = {}
        for candidate in candidates:
            symbol = candidate["symbol"]
            if symbol not in seen:
                seen[symbol] = candidate
            else:
                # 保留成交量更大的
                if candidate["volume"] > seen[symbol]["volume"]:
                    seen[symbol] = candidate
        
        return list(seen.values())
    
    async def get_best_exchange_for_symbol(
        self,
        symbol: str,
        metric: str = "volume",
    ) -> Optional[str]:
        """
        获取指定 symbol 的最佳交易所
        
        Args:
            symbol: 交易对
            metric: 评估指标 (volume/price/spread)
        
        Returns:
            最佳交易所名称
        """
        best_exchange = None
        best_value = 0
        
        for ex_name in self._exchanges:
            try:
                ticker = await self.get_ticker(symbol, ex_name)
                if not ticker:
                    continue
                
                if metric == "volume":
                    value = ticker.get("quoteVolume", 0)
                elif metric == "price":
                    value = ticker.get("last", 0)
                elif metric == "spread":
                    # spread 越小越好
                    bid = ticker.get("bid", 0)
                    ask = ticker.get("ask", 0)
                    value = -(ask - bid) if bid and ask else 0
                else:
                    value = ticker.get("quoteVolume", 0)
                
                if value > best_value:
                    best_value = value
                    best_exchange = ex_name
            except Exception:
                continue
        
        return best_exchange or self.settings.exchange.primary_exchange
    
    async def get_multi_exchange_price(
        self,
        symbol: str,
    ) -> Dict[str, Dict[str, float]]:
        """
        获取多交易所价格对比
        
        Returns:
            {exchange: {last, bid, ask, volume}}
        """
        result = {}
        
        for ex_name in self._exchanges:
            try:
                ticker = await self.get_ticker(symbol, ex_name)
                if ticker:
                    result[ex_name] = {
                        "last": ticker.get("last", 0),
                        "bid": ticker.get("bid", 0),
                        "ask": ticker.get("ask", 0),
                        "volume": ticker.get("quoteVolume", 0),
                    }
            except Exception:
                continue
        
        return result
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        status = {
            "running": self._running,
            "exchanges": {},
        }
        
        for name, exchange in self._exchanges.items():
            try:
                await exchange.fetch_time()
                status["exchanges"][name] = "connected"
            except Exception as e:
                status["exchanges"][name] = f"error: {e}"
        
        return status
    
    def on_price_update(self, callback: Callable) -> None:
        """注册价格更新回调"""
        self._price_callbacks.append(callback)
    
    def on_ticker_update(self, callback: Callable) -> None:
        """注册行情更新回调"""
        self._ticker_callbacks.append(callback)
