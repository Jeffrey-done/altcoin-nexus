# Altcoin Nexus - L4级自治量化交易系统

纯异步、事件驱动、自适应架构的量化交易系统。

## 支持的交易所

| 交易所 | 现货 | 合约 | 状态 |
|--------|------|------|------|
| **Binance** | ✅ | ✅ USDM/COINM | 主要支持 |
| **OKX** | ✅ | ✅ | 支持 |
| **Bybit** | ✅ | ✅ 线性合约 | 支持 |
| **Gate.io** | ✅ | ✅ | 支持 |
| **Bitget** | ✅ | ✅ | 支持 |

## 特性

- **纯异步架构**: 基于 asyncio，无阻塞 I/O
- **事件驱动**: Redis Pub/Sub 实现模块解耦
- **单一真相源**: PostgreSQL 数据库，行级锁保证一致性
- **自适应策略**: 市场状态感知，参数自动调整
- **闭环优化**: WFA 自动参数优化
- **系统自愈**: 熔断器、自动对账、安全模式

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Redis Pub/Sub 事件总线                    │
└─────────┬───────────────────────────────────────┬───────────┘
          │                                       │
          ▼                                       ▼
┌─────────────────────┐                 ┌─────────────────────┐
│   StrategyEngine    │                 │   RealtimeMonitor   │
│   (纯异步策略引擎)   │                 │   (纯异步监控)       │
└─────────┬───────────┘                 └─────────┬───────────┘
          │                                       │
          ▼                                       ▼
┌─────────────────────────────────────────────────────────────┐
│              UnifiedExecutionRouter & RiskControl            │
│            (统一执行路由 & 风控，基于数据库行级锁)              │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    PostgreSQL 数据库                          │
│                    (唯一真相源)                               │
└─────────────────────────────────────────────────────────────┘
```

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <repo-url>
cd altcoin-nexus

# 复制配置文件
cp .env.example .env

# 编辑配置
nano .env
```

### 2. Docker 部署（推荐）

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f nexus-core
```

### 3. 本地开发

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 启动 PostgreSQL 和 Redis
docker-compose up -d postgres redis

# 运行数据库迁移
alembic upgrade head

# 启动核心服务
python main.py

# 启动 API 服务（另一个终端）
uvicorn api:app --reload --port 8000
```

### 4. 启动前端面板

```bash
# 方式1: PowerShell (Windows)
.\start-frontend.ps1

# 方式2: 批处理 (Windows)
start-frontend.bat

# 方式3: 手动启动
cd frontend
npm install
npm run dev
```

访问 http://localhost:3000 打开管理面板

## 项目结构

```
altcoin-nexus/
├── core/                    # 核心模块
│   ├── config/             # 配置管理
│   ├── db/                 # 数据库层
│   └── events/             # 事件总线
├── services/               # 服务层
│   ├── datafeed/           # 数据馈送
│   ├── strategy/           # 策略引擎
│   ├── execution/          # 执行路由
│   ├── risk/               # 风控服务
│   ├── monitor/            # 监控告警
│   ├── admin/              # 管理面板
│   └── optimization/       # 优化服务
├── strategies/             # 策略实现
├── signals/                # 信号处理
├── ml/                     # 机器学习
├── backtesting/            # 回测引擎
├── config/                 # YAML 配置文件
├── tests/                  # 测试
├── main.py                 # 主启动脚本
├── api.py                  # FastAPI 入口
└── docker-compose.yml      # Docker 编排
```

## 配置

配置优先级（高→低）：
1. 环境变量
2. `.env` 文件
3. `config/*.yaml` 文件
4. 代码默认值

### 主要配置项

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `DATABASE_URL` | 数据库连接 | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis 连接 | `redis://localhost:6379/0` |
| `EXCHANGE_LEVERAGE` | 杠杆倍数 | `10` |
| `RISK_MAX_DAILY_LOSS` | 日最大亏损 | `100` |
| `STRATEGY_DAILY_RSI_MIN` | RSI 阈值 | `70` |

## API 文档

启动 API 服务后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 监控

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

## 开发

### 运行测试

```bash
pytest tests/
```

### 代码检查

```bash
ruff check .
mypy .
```

## License

MIT
