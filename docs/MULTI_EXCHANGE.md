# 多交易所架构说明

## 设计理念

```
┌─────────────────────────────────────────────────────────────────┐
│                      市场数据聚合层                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐│
│  │ Binance  │ │   OKX    │ │  Bybit   │ │Gate.io   │ │ Bitget   ││
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘│
│       └────────────┼───────────┼────────────┼──────────────┘     │
│                    ▼           ▼            ▼                     │
│              ┌─────────────────────────────────┐                 │
│              │      DataFeedService            │                 │
│              │   (多交易所数据聚合 & 去重)       │                 │
│              └───────────────┬─────────────────┘                 │
└──────────────────────────────┼───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                      策略分析层                                   │
│              ┌─────────────────────────────────┐                 │
│              │      StrategyEngine             │                 │
│              │  1. 多交易所聚合扫描             │                 │
│              │  2. 各交易所独立计算指标          │                 │
│              │  3. 智能选择目标交易所           │                 │
│              └───────────────┬─────────────────┘                 │
└──────────────────────────────┼───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                      执行层                                       │
│              ┌─────────────────────────────────┐                 │
│              │     ExecutionRouter             │                 │
│              │  根据 target_exchange 路由下单   │                 │
│              └───────────────┬─────────────────┘                 │
│                              │                                    │
│       ┌──────────────────────┼──────────────────────┐            │
│       ▼                      ▼                      ▼            │
│  ┌─────────┐           ┌─────────┐           ┌─────────┐        │
│  │ Binance │           │   OKX   │           │  Bybit  │  ...   │
│  └─────────┘           └─────────┘           └─────────┘        │
└──────────────────────────────────────────────────────────────────┘
```

## 数据流

### 1. 扫描阶段（多交易所聚合）

```python
# scan_potential_symbols(exchange=None) 会：
# 1. 并发请求所有已连接交易所的行情
# 2. 按 symbol 去重，保留流动性最好的交易所
# 3. 返回候选列表，每个候选包含 exchange 字段

candidates = await datafeed.scan_potential_symbols(
    min_volume=500000,
    min_pct_change=5.0,
    exchange=None  # 扫描所有交易所
)

# 返回示例：
[
    {"symbol": "PEPE/USDT", "exchange": "binance", "volume": 10000000, ...},
    {"symbol": "DOGE/USDT", "exchange": "okx", "volume": 8000000, ...},
    {"symbol": "WIF/USDT", "exchange": "bybit", "volume": 5000000, ...},
]
```

### 2. 确认阶段（智能路由）

```python
# 策略确认时会：
# 1. 从候选交易所获取详细数据（K线、资金费率）
# 2. 智能选择目标交易所下单

signal = await strategy.confirm(candidate)

# 返回示例：
{
    "symbol": "PEPE/USDT",
    "scan_exchange": "binance",      # 扫描到的交易所
    "target_exchange": "binance",    # 下单目标交易所
    "score": 85,
    ...
}
```

### 3. 执行阶段（按交易所路由）

```python
# 执行器根据 target_exchange 路由到对应交易所
await execution_router.execute_open(
    symbol=signal["symbol"],
    exchange=signal["target_exchange"],  # 使用目标交易所
    ...
)
```

## 交易所选择逻辑

### 场景1：主交易所支持该交易对
```
扫描交易所: Bybit (发现 PEPE/USDT 涨幅 20%)
主交易所: Binance (也有 PEPE/USDT)

决策: 
- 比较两边流动性
- 如果 Binance 流动性 > Bybit 的 50%，用 Binance
- 否则用 Bybit
```

### 场景2：主交易所不支持该交易对
```
扫描交易所: Gate.io (发现某新币涨幅 50%)
主交易所: Binance (没有该交易对)

决策: 直接用 Gate.io 下单
```

### 场景3：价差套利机会
```python
# 获取多交易所价格对比
prices = await datafeed.get_multi_exchange_price("BTC/USDT")
# {
#     "binance": {"last": 65000, "bid": 64999, "ask": 65001},
#     "okx": {"last": 65010, "bid": 65009, "ask": 65011},
#     "bybit": {"last": 64995, "bid": 64994, "ask": 64996},
# }
```

## 配置

### .env 文件
```bash
# 主交易所（优先用于下单）
EXCHANGE_PRIMARY_EXCHANGE=binance

# 各交易所 API（配置了哪个就用哪个扫描）
EXCHANGE_BINANCE_API_KEY=xxx
EXCHANGE_OKX_API_KEY=xxx
EXCHANGE_BYBIT_API_KEY=xxx
EXCHANGE_GATE_API_KEY=xxx
EXCHANGE_BITGET_API_KEY=xxx
```

### 策略配置
```yaml
# config/strategy.yaml
short_overbought:
  # 扫描配置
  scan:
    vol_min: 500000      # 最小成交量
    pct_24h_min: 5       # 最小涨幅
    
  # 交易所优先级（可选）
  exchange_priority:
    - binance
    - okx
    - bybit
```

## 优势

1. **发现更多机会** - 多交易所扫描不漏掉任何交易所的暴涨币
2. **流动性优化** - 自动选择流动性最好的交易所
3. **风险分散** - 可以在不同交易所分散持仓
4. **价格发现** - 多交易所价格对比，发现套利机会
