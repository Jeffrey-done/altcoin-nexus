# Altcoin-Nexus 系统一体化健康诊断报告

**审计时间**: 2026-05-27  
**审计范围**: 全系统架构、事件流、生命周期、真相源、配置管理、异常传播  
**审计方法**: 深度代码静态分析 + 架构一致性检查

---

## 一、综合评分

| 维度 | 满分 | 得分 | 等级 | 说明 |
|------|------|------|------|------|
| 事件流闭环 | 100 | 45 | **D** | 14个孤儿事件，5个严重断链 |
| 生命周期管理 | 100 | 69 | **C+** | 4个模块未管理，5处资源泄漏 |
| 真相源一致性 | 100 | 70 | **B** | Repository收口优秀，但3处内存状态无持久化 |
| 配置热加载 | 100 | 33 | **F** | 热加载完全失效，0%覆盖率 |
| 异常传播与自愈 | 100 | 43 | **D** | 风控异常=信号穿透，关键熔断缺失 |
| **总分** | **500** | **260** | **52%** | **碎片化风险：中高** |

### 总体诊断结论

> **系统目前处于"半一体化"状态：架构骨架优秀，但模块间连接存在多处断裂。**
>
> - ✅ 优点：Repository 收口完美、事件总线设计正确、服务生命周期基本完整
> - ❌ 缺陷：事件无人消费、配置热加载失效、风控异常穿透、关键状态无持久化
>
> **如果不修复 P0 级问题，系统在极端行情下可能出现：风控失效、配置不生效、状态丢失。**

---

## 二、P0 级风险清单（必须立即修复）

### 风险 1：风控检查异常 = 信号穿透

**位置**: `services/risk/service.py:137`  
**问题**: `_on_signal_triggered` 中 `check_can_open()` 无 try/except，异常导致 `risk_blocked` 标记不设置  
**后果**: 风控服务异常时，所有信号无条件通过  
**修复**:
```python
try:
    can_open, reason = await self.check_can_open(...)
except Exception as e:
    logger.critical(f"Risk check FAILED: {e} - BLOCKING signal")
    can_open, reason = False, f"Risk check exception: {e}"
```

### 风险 2：TRADE_OPENED 事件从未发布

**位置**: `services/execution/router.py`  
**问题**: `execute_open()` 成交后不发布 `TRADE_OPENED`  
**后果**: Admin 面板 WebSocket 永远收不到新开仓通知  
**修复**: 在 `execute_open()` 成功后添加 `await bus.publish(EventType.TRADE_OPENED, {...})`

### 风险 3：EXECUTION_ORDER_SENT 事件从未发布

**位置**: `services/execution/router.py`  
**问题**: validator 订阅了 `ORDER_SENT`，但 execution 从不发布  
**后果**: 事件闭环验证链中间断裂  
**修复**: 在下单前添加 `await bus.publish(EventType.EXECUTION_ORDER_SENT, {...})`

### 风险 4：MARKET_REGIME_CHANGED 无人消费

**位置**: `signals/regime.py:257` 发布，无订阅者  
**问题**: 市场状态变化无法驱动策略动态切换  
**后果**: `MacroFilter` 的仓位乘数映射形同虚设  
**修复**: `StrategyEngine` 订阅此事件，动态调整策略参数

### 风险 5：OPTIMIZATION_PARAMS_UPDATED 无人消费

**位置**: `services/optimization/service.py:167` 发布，无订阅者  
**问题**: WFA 优化产出新参数后无法热加载  
**后果**: 闭环优化断裂，参数更新需手动重启  
**修复**: `StrategyEngine` 订阅此事件，更新运行时参数

### 风险 6：恐慌平仓绕过事件总线

**位置**: `services/admin/app.py:220-234`  
**问题**: 直接调用 `TradeRepository.close_trade()` 而非 `ExecutionRouter`  
**后果**: 不在交易所实际平仓、不发布 `TRADE_CLOSED`、风控状态不更新  
**修复**: 改为调用 `ExecutionRouter.execute_close()`

### 风险 7：配置热加载完全失效

**位置**: 所有使用 `get_settings()` 的模块  
**问题**: 模块缓存旧 Settings 引用，`CONFIG_RELOADED` 无人订阅  
**后果**: 修改 YAML 配置后需重启才生效  
**修复**: 所有服务订阅 `CONFIG_RELOADED` 并刷新 `self.settings`

### 风险 8：黑名单/暂停状态无持久化

**位置**: `services/admin/app.py:200` (`_blacklist`)、`services/risk/service.py:40` (`_paused_until`)  
**问题**: 进程重启后黑名单和暂停状态丢失  
**后果**: 风控暂停后崩溃重启 = 立即恢复交易  
**修复**: 存入 DB `system_states` 表

---

## 三、P1 级风险清单（本周修复）

| # | 风险 | 位置 | 说明 |
|---|------|------|------|
| 9 | EventChainValidator task 引用丢失 | `validator.py:129` | `create_task()` 未保存引用，无法取消 |
| 10 | ConfigManager 未纳入生命周期 | `core/config/manager.py` | `stop()` 永远不被调用 |
| 11 | SelfHealingService 未集成 | `services/monitor/healing.py` | 功能完整但从未启动 |
| 12 | MarketRegimeDetector 未集成 | `signals/regime.py` | 市场状态检测从未运行 |
| 13 | `_get_exchange_positions` 空实现 | `healing.py:179` | 对账功能形同虚设 |
| 14 | RISK_PAUSED/RISK_RESUMED 无人订阅 | `risk/service.py` | 手动暂停指令石沉大海 |
| 15 | SYSTEM_HEALTH 无人订阅 | `monitor/service.py` | 健康数据无人消费 |
| 16 | 风控缓存与 DB 非原子同步 | `risk/service.py:306` | 60秒刷新间隔存在一致性窗口 |
| 17 | YAML 覆盖逻辑失效 | `settings.py:248` | 嵌套结构与扁平解析不匹配 |
| 18 | 裸 except 吞掉关键异常 | 5处 | OI/资金费率缺失静默回退为0 |

---

## 四、P2 级风险清单（本月修复）

| # | 风险 | 位置 | 说明 |
|---|------|------|------|
| 19 | 事件类型定义冗余 37% | `types.py` | 27个枚举中10个未使用 |
| 20 | 字符串/枚举事件混用 | `main.py:90` | `"system.startup"` vs `EventType.SYSTEM_STARTUP` |
| 21 | 事件数据竞态修改 | `risk/service.py:158` | 直接修改 `event.data` 字典 |
| 22 | 熔断器 HALF_OPEN 探测失败卡死 | `healing.py:296` | 应重新设为 OPEN |
| 23 | 策略执行无熔断 | `StrategyEngine` | 连续失败无保护 |
| 24 | EventBus 发布失败无感知 | `bus.py:140` | 所有调用方未检查返回值 |
| 25 | 优化历史无持久化 | `optimization/service.py` | 进程重启丢失 |

---

## 五、架构亮点（做得好的地方）

### ✅ Repository 收口完美
- 所有 46 处 DB 操作均在 `core/db/repositories.py` 内
- 0 处业务模块直接操作数据库
- 这是整个系统最优秀的架构设计

### ✅ 事件总线设计正确
- Redis Pub/Sub 支持跨进程通信
- 通配符订阅支持
- 自动重连机制

### ✅ 核心服务生命周期完整
- 6 个核心服务的 start/stop 配对正确
- 异步任务取消和等待正确
- 逆序关闭策略正确

### ✅ 行级锁使用正确
- `close_trade` 使用 `SELECT FOR UPDATE`
- `trigger_tp1_with_lock` 使用行级锁
- `RiskRepository.update_with_lock` 使用行级锁

---

## 六、重构建议

### 6.1 建立事件注册表（防止孤儿事件）

```python
# core/events/registry.py
class EventRegistry:
    """事件注册表 - 启动时校验发布/订阅完整性"""
    
    def __init__(self):
        self._publishers: Dict[str, List[str]] = {}  # event -> [publishers]
        self._subscribers: Dict[str, List[str]] = {}  # event -> [subscribers]
    
    def validate(self) -> List[str]:
        """校验孤儿事件和死订阅"""
        issues = []
        for event, pubs in self._publishers.items():
            if event not in self._subscribers:
                issues.append(f"Orphan event: {event} (published by {pubs}, no subscribers)")
        for event, subs in self._subscribers.items():
            if event not in self._publishers:
                issues.append(f"Dead subscription: {event} (subscribed by {subs}, no publisher)")
        return issues
```

### 6.2 配置热加载刷新机制

```python
# 所有服务基类添加
class BaseService:
    async def _on_config_reloaded(self, event):
        """配置热加载回调"""
        self.settings = get_settings()
        logger.info(f"{self.__class__.__name__} config refreshed")
```

### 6.3 风控异常默认拒绝

```python
# risk/service.py
async def _on_signal_triggered(self, event):
    try:
        can_open, reason = await self.check_can_open(...)
    except Exception as e:
        logger.critical(f"Risk check FAILED: {e}")
        can_open, reason = False, "Risk check exception"
    
    if not can_open:
        signal_data["risk_blocked"] = True
```

### 6.4 关键状态持久化

```python
# 黑名单持久化
await SystemStateRepository.set("blacklist", json.dumps(list(_blacklist)))

# 暂停状态持久化
await RiskRepository.update(account_id, {"paused_until": paused_until.isoformat()})
```

---

## 七、修复优先级路线图

```
Week 1 (P0):
├── 修复风控异常穿透
├── 补齐 TRADE_OPENED / ORDER_SENT 事件
├── 订阅 MARKET_REGIME_CHANGED / OPTIMIZATION_PARAMS_UPDATED
├── 修复恐慌平仓绕过
└── 配置热加载刷新机制

Week 2 (P1):
├── 集成 SelfHealingService / MarketRegimeDetector
├── 实现 _get_exchange_positions
├── 订阅 RISK_PAUSED/RISK_RESUMED
├── 修复 EventChainValidator task 泄漏
└── 黑名单/暂停状态持久化

Week 3-4 (P2):
├── 事件注册表
├── 策略/数据馈送熔断器
├── EventBus 发布失败处理
├── 清理未使用事件类型
└── 优化历史持久化
```

---

## 八、最终结论

| 指标 | 评分 | 状态 |
|------|------|------|
| 一体化程度 | 52% | ⚠️ 半一体化 |
| 架构骨架 | 85% | ✅ 优秀 |
| 模块连接 | 45% | ❌ 多处断裂 |
| 生产就绪度 | 40% | ❌ 需修复 P0 |

**诊断结论**: 系统架构设计优秀，但模块间"最后一公里"的连接存在多处断裂。修复 P0 级问题后，一体化程度可提升至 75%+，达到生产可用标准。
