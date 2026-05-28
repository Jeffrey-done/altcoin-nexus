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
from cachetools import TTLCache

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
    - 本地缓存（带TTL和容量限制）
    """
    
    def __init__(self):
        self._settings = get_settings()
        self._exchanges: Dict[str, ccxt.Exchange] = {}
        self._running = False
        # 使用 TTLCache 限制缓存大小和过期时间
        self._cache = TTLCache(maxsize=1000, ttl=60)  # 最多1000条，60秒过期
        self._inflight: Dict[str, asyncio.Task] = {}  # 防止重复请求
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
        """初始化交易所连接 - 始终初始化用于公开API，有密钥时额外启用私有API"""
        config = self._settings.exchange
        
        # 始终初始化主交易所（公开API不需要密钥）
        exchange_configs = {
            "binance": {
                "cls": ccxt.binance,
                "key": config.binance_api_key,
                "secret": config.binance_api_secret,
                "extra": {"options": {"defaultType": "future"}},
            },
            "okx": {
                "cls": ccxt.okx,
                "key": config.okx_api_key,
                "secret": config.okx_api_secret,
                "passphrase": config.okx_passphrase,
                "extra": {},
            },
            "bybit": {
                "cls": ccxt.bybit,
                "key": config.bybit_api_key,
                "secret": config.bybit_api_secret,
                "extra": {"options": {"defaultType": "linear"}},
            },
            "gate": {
                "cls": ccxt.gate,
                "key": config.gate_api_key,
                "secret": config.gate_api_secret,
                "extra": {"options": {"defaultType": "future"}},
            },
            "bitget": {
                "cls": ccxt.bitget,
                "key": config.bitget_api_key,
                "secret": config.bitget_api_secret,
                "passphrase": config.bitget_passphrase,
                "extra": {"options": {"defaultType": "future"}},
            },
        }
        
        primary = config.primary_exchange
        proxy = config.proxy  # 可选代理，本地开发用，服务器留空直连
        
        for name, ex_cfg in exchange_configs.items():
            # 主交易所始终初始化，其他交易所仅在有密钥时初始化
            if name != primary and not ex_cfg["key"]:
                continue
            
            try:
                params = {
                    "enableRateLimit": True,
                    **ex_cfg["extra"],
                }
                # 有密钥时添加认证信息（用于下单、查询持仓等私有API）
                if ex_cfg["key"]:
                    params["apiKey"] = ex_cfg["key"]
                    params["secret"] = ex_cfg["secret"]
                    if ex_cfg.get("passphrase"):
                        params["password"] = ex_cfg["passphrase"]
                    auth_status = "authenticated"
                else:
                    auth_status = "public-only (no API key)"
                
                # 代理支持（本地开发时通过代理访问交易所，服务器留空直连）
                if proxy:
                    params["httpsProxy"] = proxy
                    logger.info(f"Using proxy for {name}: {proxy}")
                
                self._exchanges[name] = ex_cfg["cls"](params)
                logger.info(f"{name.capitalize()} exchange initialized ({auth_status})")
            except Exception as e:
                logger.error(f"Failed to initialize {name}: {e}")
        
        if not self._exchanges:
            logger.warning("No exchanges initialized - scanner will not work")
        else:
            logger.info(f"Initialized {len(self._exchanges)} exchange(s): {list(self._exchanges.keys())}")
    
    async def get_ticker(
        self,
        symbol: str,
        exchange: str = "binance",
    ) -> Optional[Dict[str, Any]]:
        """获取实时行情（带缓存和并发保护）"""
        cache_key = f"{exchange}:{symbol}:ticker"
        
        # 检查缓存
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 如果已有相同请求在飞行中，等待其结果
        if cache_key in self._inflight:
            try:
                return await self._inflight[cache_key]
            except Exception:
                return None
        
        if exchange not in self._exchanges:
            logger.warning(f"Exchange {exchange} not available")
            return None
        
        # 创建 inflight 请求
        async def _fetch():
            try:
                ticker = await self._exchanges[exchange].fetch_ticker(symbol)
                self._cache[cache_key] = ticker  # TTLCache 自动管理过期
                return ticker
            except Exception as e:
                logger.error(f"Failed to fetch ticker {symbol}: {e}")
                return None
        
        task = asyncio.create_task(_fetch())
        self._inflight[cache_key] = task
        
        try:
            return await task
        finally:
            self._inflight.pop(cache_key, None)
    
    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
        exchange: str = "binance",
    ) -> Optional[List[List]]:
        """获取K线数据（带缓存和并发保护）"""
        cache_key = f"{exchange}:{symbol}:{timeframe}:ohlcv"
        
        # TTLCache 自动处理过期，直接检查即可
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        if exchange not in self._exchanges:
            logger.warning(f"Exchange {exchange} not available")
            return None
        
        try:
            ohlcv = await self._exchanges[exchange].fetch_ohlcv(
                symbol, timeframe, limit=limit
            )
            
            # 写入 TTLCache（自动管理过期）
            self._cache[cache_key] = ohlcv
            
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
        
        return best_exchange or self._settings.exchange.primary_exchange
    
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
