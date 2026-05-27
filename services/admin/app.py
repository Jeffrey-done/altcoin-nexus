"""
FastAPI 管理面板
支持 API + 前端静态文件托管
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.config import get_settings, reload_settings
from core.db import TradeRepository, CandidateRepository, RiskRepository, EventRepository
from core.events import EventType, get_event_bus

logger = logging.getLogger("nexus.admin")

# 前端构建目录
FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend" / "dist"


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
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # WebSocket 连接管理
    ws_connections: List[WebSocket] = []
    
    @app.on_event("startup")
    async def startup():
        logger.info("Admin panel started")
    
    @app.on_event("shutdown")
    async def shutdown():
        logger.info("Admin panel shutting down")
    
    # 健康检查
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
    async def update_config(request: ConfigUpdateRequest):
        # 发布配置变更事件
        bus = await get_event_bus()
        await bus.publish(EventType.CONFIG_CHANGED, {
            "key": request.key,
            "value": request.value,
            "changed_by": "admin",
        })
        return {"status": "ok"}
    
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
