"""
FastAPI 管理面板
支持 API + 前端静态文件托管
包含身份认证和授权
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.config import get_settings, reload_settings
from core.db import TradeRepository, CandidateRepository, RiskRepository, EventRepository, SystemStateRepository
from core.events import EventType, get_event_bus
from .auth import get_current_user, require_admin, create_session, verify_credentials

logger = logging.getLogger("nexus.admin")

# 前端构建目录
FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend" / "dist"

# CORS 允许的来源（从环境变量读取）
ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")


# Pydantic 模型
class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str


class TradeResponse(BaseModel):
    id: str
    symbol: str
    direction: str
    status: str
    entry_price: float
    stake: float
    pnl: float


class RiskStatusResponse(BaseModel):
    account_id: str
    is_paused: bool
    daily_loss: float
    daily_loss_limit: float
    consecutive_losses: int
    today_trades: int


class ConfigUpdateRequest(BaseModel):
    key: str
    value: Any


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    settings = get_settings()
    
    app = FastAPI(
        title="Altcoin Nexus Admin",
        description="L4级自治量化交易系统管理面板",
        version=settings.version,
    )
    
    # CORS - 限制来源
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    
    # WebSocket 连接管理
    ws_connections: List[WebSocket] = []
    
    # 登录请求模型
    class LoginRequest(BaseModel):
        username: str
        password: str
    
    class LoginResponse(BaseModel):
        token: str
        expires_in: int
    
    @app.on_event("startup")
    async def startup():
        logger.info("Admin panel started")
    
    @app.on_event("shutdown")
    async def shutdown():
        logger.info("Admin panel shutting down")
    
    # 登录端点（无需认证）
    @app.post("/api/auth/login", response_model=LoginResponse)
    async def login(request: LoginRequest):
        """用户登录，获取访问令牌"""
        if not verify_credentials(request.username, request.password):
            raise HTTPException(
                status_code=401,
                detail="Invalid credentials",
            )
        
        token = create_session(request.username)
        return LoginResponse(token=token, expires_in=86400)  # 24小时
    
    # 登出端点
    @app.post("/api/auth/logout")
    async def logout(user: str = Depends(get_current_user)):
        """用户登出"""
        # 实际实现需要从请求中获取 token 并撤销
        return {"status": "ok"}
    
    # 健康检查（无需认证）
    @app.get("/health", response_model=HealthResponse)
    async def health():
        return HealthResponse(
            status="ok",
            version=settings.version,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    
    # 交易相关
    @app.get("/api/trades", response_model=List[TradeResponse])
    async def get_trades(
        status: Optional[str] = None,
        account_id: Optional[str] = None,
    ):
        trades = await TradeRepository.get_open(account_id=account_id)
        return [TradeResponse(**t) for t in trades]
    
    @app.get("/api/trades/{trade_id}")
    async def get_trade(trade_id: str):
        trade = await TradeRepository.get_by_id(trade_id)
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")
        return trade
    
    # 候选池
    @app.get("/api/candidates")
    async def get_candidates(
        strategy: Optional[str] = None,
        direction: Optional[str] = None,
    ):
        candidates = await CandidateRepository.get_active(
            strategy=strategy,
            direction=direction,
        )
        return candidates
    
    # 风控状态
    @app.get("/api/risk/{account_id}", response_model=RiskStatusResponse)
    async def get_risk_status(account_id: str):
        from services.risk import RiskControlService
        # 这里需要获取风控服务实例
        # 简化实现
        risk_state = await RiskRepository.get_or_create(account_id)
        return RiskStatusResponse(
            account_id=account_id,
            is_paused=False,
            daily_loss=risk_state.get("daily_loss", 0),
            daily_loss_limit=settings.risk.max_daily_loss,
            consecutive_losses=risk_state.get("consecutive_losses", 0),
            today_trades=risk_state.get("daily_trades_opened", 0),
        )
    
    # 执行事件
    @app.get("/api/events")
    async def get_events(
        event_type: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
    ):
        events = await EventRepository.get_recent(
            event_type=event_type,
            symbol=symbol,
            limit=limit,
        )
        return events
    
    # 系统状态
    @app.get("/api/system/status")
    async def get_system_status():
        return {
            "version": settings.version,
            "environment": settings.environment,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    # 配置管理
    @app.get("/api/config")
    async def get_config():
        return {
            "exchange": {
                "primary_exchange": settings.exchange.primary_exchange,
                "leverage": settings.exchange.leverage,
                "max_open_trades": settings.exchange.max_open_trades,
            },
            "risk": {
                "max_daily_loss": settings.risk.max_daily_loss,
                "max_daily_trades": settings.risk.max_daily_trades,
                "consecutive_loss_pause": settings.risk.consecutive_loss_pause,
            },
            "strategy": {
                "vol_min": settings.strategy.vol_min,
                "daily_rsi_min": settings.strategy.daily_rsi_min,
                "hard_stop_pct": settings.strategy.hard_stop_pct,
            },
        }
    
    @app.post("/api/config")
    async def update_config(
        request: ConfigUpdateRequest,
        user: str = Depends(require_admin),  # 需要管理员权限
    ):
        # 发布配置变更事件
        bus = await get_event_bus()
        await bus.publish(EventType.CONFIG_CHANGED, {
            "key": request.key,
            "value": request.value,
            "changed_by": user,
        })
        return {"status": "ok"}
    
    # ==================== 一体化指令 API ====================
    
    # 黑名单存储（持久化到数据库）
    _blacklist: set = set()
    
    # 启动时加载黑名单
    @app.on_event("startup")
    async def load_blacklist():
        nonlocal _blacklist
        try:
            stored = await SystemStateRepository.get("blacklist")
            if stored:
                import json
                _blacklist = set(json.loads(stored))
                logger.info(f"Loaded blacklist from DB: {_blacklist}")
        except Exception as e:
            logger.warning(f"Failed to load blacklist: {e}")
    
    @app.post("/api/execution/panic-sell-all")
    async def panic_sell_all(
        user: str = Depends(require_admin),  # 需要管理员权限
    ):
        """
        紧急全平仓
        
        立即触发所有持仓的市价平仓单，并进入休眠模式
        通过事件总线通知所有服务，而非直接操作数据库
        """
        logger.warning(f"PANIC SELL ALL triggered by {user}!")
        
        bus = await get_event_bus()
        
        # 发布系统恐慌事件 - 通过事件总线通知所有服务
        await bus.publish(EventType.SYSTEM_PANIC, {
            "reason": "Manual panic sell triggered",
            "action": "close_all",
            "triggered_by": "admin",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        # 获取所有持仓用于返回结果
        open_trades = await TradeRepository.get_open()
        
        # 注意：实际平仓由 ExecutionRouter 通过订阅 SYSTEM_PANIC 事件来执行
        # 这里只负责发布事件和返回当前持仓信息
        
        return {
            "status": "ok",
            "open_trades": len(open_trades),
            "trades": [
                {
                    "symbol": t.get("symbol"),
                    "direction": t.get("direction"),
                    "stake": t.get("stake"),
                }
                for t in open_trades
            ],
            "message": "PANIC event published. ExecutionRouter will close all positions.",
        }
    
    @app.post("/api/strategy/blacklist")
    async def add_to_blacklist(
        request: Dict[str, str],
        user: str = Depends(require_admin),  # 需要管理员权限
    ):
        """
        添加币种到黑名单
        
        {
            "symbol": "PEPE/USDT",
            "reason": "高风险"
        }
        """
        symbol = request.get("symbol", "")
        reason = request.get("reason", "")
        
        if not symbol:
            raise HTTPException(status_code=400, detail="symbol is required")
        
        _blacklist.add(symbol)
        
        # 持久化到数据库
        import json
        await SystemStateRepository.set("blacklist", json.dumps(list(_blacklist)))
        
        # 发布事件
        bus = await get_event_bus()
        await bus.publish("strategy.blacklist_added", {
            "symbol": symbol,
            "reason": reason,
            "added_by": user,
        })
        
        logger.info(f"Blacklist added by {user}: {symbol} - {reason}")
        
        return {
            "status": "ok",
            "symbol": symbol,
            "blacklist": list(_blacklist),
        }
    
    @app.delete("/api/strategy/blacklist/{symbol}")
    async def remove_from_blacklist(
        symbol: str,
        user: str = Depends(require_admin),  # 需要管理员权限
    ):
        """从黑名单移除"""
        _blacklist.discard(symbol)
        
        # 持久化到数据库
        import json
        await SystemStateRepository.set("blacklist", json.dumps(list(_blacklist)))
        
        logger.info(f"Blacklist removed by {user}: {symbol}")
        
        return {
            "status": "ok",
            "symbol": symbol,
            "blacklist": list(_blacklist),
        }
    
    @app.get("/api/strategy/blacklist")
    async def get_blacklist(user: str = Depends(get_current_user)):  # 需要登录
        """获取黑名单"""
        return {
            "blacklist": list(_blacklist),
            "count": len(_blacklist),
        }
    
    @app.post("/api/risk/toggle-pause")
    async def toggle_risk_pause(
        request: Dict[str, Any],
        user: str = Depends(require_admin),  # 需要管理员权限
    ):
        """
        强制熔断/恢复
        
        {
            "paused": true,
            "reason": "手动暂停",
            "duration_minutes": 60
        }
        """
        paused = request.get("paused", True)
        reason = request.get("reason", "Manual toggle")
        duration = request.get("duration_minutes", 60)
        
        bus = await get_event_bus()
        
        if paused:
            await bus.publish(EventType.RISK_PAUSED, {
                "reason": reason,
                "duration_minutes": duration,
                "paused_by": user,
            })
            logger.warning(f"Risk PAUSED by {user}: {reason} for {duration} minutes")
        else:
            await bus.publish(EventType.RISK_RESUMED, {
                "reason": reason,
                "resumed_by": user,
            })
            logger.info(f"Risk RESUMED by {user}: {reason}")
        
        return {
            "status": "ok",
            "paused": paused,
            "reason": reason,
            "duration_minutes": duration if paused else None,
        }
    
    @app.post("/api/optimization/run-now")
    async def run_optimization_now(
        user: str = Depends(require_admin),  # 需要管理员权限
    ):
        """
        立即触发参数优化
        
        启动 WFA 优化任务
        """
        logger.info(f"Manual optimization triggered by {user}")
        
        bus = await get_event_bus()
        await bus.publish(EventType.OPTIMIZATION_COMPLETED, {
            "trigger": "manual",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        return {
            "status": "ok",
            "message": "Optimization task queued",
        }
    
    @app.post("/api/config/regime")
    async def force_regime(
        request: Dict[str, str],
        user: str = Depends(require_admin),  # 需要管理员权限
    ):
        """
        强制设置市场状态
        
        {
            "regime": "crash",
            "reason": "手动进入防守模式"
        }
        """
        regime = request.get("regime", "")
        reason = request.get("reason", "")
        
        valid_regimes = ["trending_up", "trending_down", "ranging", "high_vol", "crash", "recovery"]
        if regime not in valid_regimes:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid regime. Must be one of: {valid_regimes}"
            )
        
        bus = await get_event_bus()
        await bus.publish(EventType.MARKET_REGIME_CHANGED, {
            "old_regime": "manual",
            "new_regime": regime,
            "confidence": 1.0,
            "reason": reason,
            "forced_by": user,
        })
        
        logger.warning(f"Regime FORCED to {regime} by {user}: {reason}")
        
        return {
            "status": "ok",
            "regime": regime,
            "reason": reason,
        }
    
    @app.get("/api/system/pulse")
    async def system_pulse(user: str = Depends(get_current_user)):  # 需要登录
        """
        系统脉搏 - 返回所有服务状态
        """
        from services.risk import RiskControlService
        from services.strategy import StrategyEngine
        from services.execution import ExecutionRouter
        from services.monitor import MonitoringService
        from services.optimization import OptimizationService
        
        # 这里需要获取各服务实例
        # 简化实现，返回基本信息
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "services": {
                "api": {"status": "running"},
                "database": {"status": "connected"},
                "redis": {"status": "connected"},
                "event_bus": {"status": "running"},
            },
            "blacklist": list(_blacklist),
            "uptime": "N/A",
        }
    
    @app.get("/api/system/validation")
    async def system_validation():
        """
        事件闭环验证
        
        返回信号→风控→下单的延迟统计
        """
        from services.monitor.validator import get_validator
        
        validator = await get_validator()
        result = validator.validate()
        
        return {
            "timestamp": result.timestamp,
            "is_healthy": result.is_healthy,
            "health_score": result.health_score,
            "chains": {
                "total": result.total_chains,
                "completed": result.completed_chains,
                "timeout": result.timeout_chains,
                "failed": result.failed_chains,
            },
            "latency": {
                "avg_risk_ms": result.avg_risk_latency_ms,
                "avg_execution_ms": result.avg_execution_latency_ms,
                "avg_total_ms": result.avg_total_latency_ms,
                "p95_ms": result.p95_total_latency_ms,
                "p99_ms": result.p99_total_latency_ms,
            },
        }
    
    @app.get("/api/config/manager")
    async def config_manager_status():
        """
        配置管理器状态
        """
        from core.config.manager import get_config_manager
        
        manager = await get_config_manager()
        return manager.get_status()
    
    # WebSocket 实时推送
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        ws_connections.append(websocket)
        
        try:
            while True:
                # 保持连接
                data = await websocket.receive_text()
                # 处理客户端消息
                logger.debug(f"WebSocket message: {data}")
        except WebSocketDisconnect:
            ws_connections.remove(websocket)
    
    # 广播消息到所有 WebSocket 连接
    async def broadcast(message: Dict[str, Any]):
        for ws in ws_connections.copy():
            try:
                await ws.send_json(message)
            except Exception:
                ws_connections.remove(ws)
    
    # 注册事件监听
    @app.on_event("startup")
    async def register_event_listeners():
        bus = await get_event_bus()
        
        async def on_trade_opened(event):
            await broadcast({"type": "trade.opened", "data": event.data})
        
        async def on_trade_closed(event):
            await broadcast({"type": "trade.closed", "data": event.data})
        
        async def on_risk_alert(event):
            await broadcast({"type": "risk.alert", "data": event.data})
        
        await bus.subscribe(EventType.TRADE_OPENED, on_trade_opened)
        await bus.subscribe(EventType.TRADE_CLOSED, on_trade_closed)
        await bus.subscribe(EventType.RISK_ALERT, on_risk_alert)
    
    # 前端静态文件托管
    if FRONTEND_DIR.exists():
        # 挂载静态资源
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")
        
        # SPA 路由 - 所有非 API 路由都返回 index.html
        @app.get("/{path:path}", response_class=HTMLResponse)
        async def serve_spa(request: Request, path: str):
            # 如果是 API 路由，跳过
            if path.startswith("api/") or path.startswith("ws"):
                raise HTTPException(status_code=404, detail="Not found")
            
            # 尝试返回静态文件
            file_path = FRONTEND_DIR / path
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)
            
            # 返回 index.html (SPA 路由)
            return FileResponse(FRONTEND_DIR / "index.html")
        
        logger.info(f"Frontend served from: {FRONTEND_DIR}")
    else:
        @app.get("/", response_class=HTMLResponse)
        async def no_frontend():
            return """
            <html>
                <head><title>Altcoin Nexus</title></head>
                <body style="background:#111827;color:#fff;font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh">
                    <div style="text-align:center">
                        <h1>🚀 Altcoin Nexus API</h1>
                        <p>前端未构建，请先构建前端：</p>
                        <code style="background:#1f2937;padding:10px 20px;border-radius:5px">
                            cd frontend && npm install && npm run build
                        </code>
                        <p style="margin-top:20px">
                            <a href="/docs" style="color:#0ea5e9">查看 API 文档 →</a>
                        </p>
                    </div>
                </body>
            </html>
            """
        
        logger.warning(f"Frontend not found at {FRONTEND_DIR}. Run 'cd frontend && npm run build'")
    
    return app
