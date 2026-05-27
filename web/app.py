"""
Altcoin Nexus - 一体式 Web 应用
单端口，不对外开放，多重验证，全功能管理面板
"""

import logging
import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi import Request, Depends, Body
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .auth import (
    authenticate, get_current_user, require_auth,
    check_ip_whitelist, get_active_sessions, revoke_session,
    TOTP_ENABLED, generate_totp_secret, get_totp_uri,
    hash_password, IP_WHITELIST, _get_client_ip,
)

logger = logging.getLogger("nexus.web")
FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"



# === Pydantic 模型 ===

class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: Optional[str] = None

class ConfigUpdateRequest(BaseModel):
    section: str  # strategy / risk / exchange / system / monitoring / telegram / optimization
    key: str
    value: Any

class SecretUpdateRequest(BaseModel):
    exchange: str  # binance / okx / bybit / gate / bitget
    api_key: str = ""
    api_secret: str = ""
    passphrase: str = ""

class BlacklistRequest(BaseModel):
    symbol: str
    reason: str = ""

class RegimeRequest(BaseModel):
    regime: str
    reason: str = ""

class PauseRequest(BaseModel):
    paused: bool
    reason: str = ""
    duration_minutes: int = 60



# === 应用工厂 ===

def create_app() -> FastAPI:
    """创建一体式 FastAPI 应用"""
    from core.config import get_settings
    settings = get_settings()

    app = FastAPI(
        title="Altcoin Nexus",
        description="L4级自治量化交易系统 - 一体式管理面板",
        version=settings.version,
        docs_url=None,  # 不暴露 Swagger
        redoc_url=None,
    )

    # WebSocket 连接池
    ws_connections: List[WebSocket] = []

    # ==================== 认证路由 ====================

    @app.post("/api/auth/login")
    async def login(request: Request, body: LoginRequest):
        """登录 - 多重验证"""
        result = authenticate(body.username, body.password, body.totp_code, request)
        return result

    @app.post("/api/auth/logout")
    async def logout(user: str = Depends(require_auth)):
        """登出"""
        return {"status": "ok"}

    @app.get("/api/auth/me")
    async def get_me(user: str = Depends(require_auth)):
        """获取当前用户信息"""
        return {
            "username": user,
            "totp_enabled": TOTP_ENABLED,
            "ip_whitelist": IP_WHITELIST,
        }


    @app.get("/api/auth/sessions")
    async def list_sessions(user: str = Depends(require_auth)):
        """获取活跃会话列表"""
        return {"sessions": get_active_sessions()}

    @app.delete("/api/auth/sessions/{session_id}")
    async def delete_session(session_id: str, user: str = Depends(require_auth)):
        """撤销指定会话"""
        revoke_session(session_id)
        return {"status": "ok"}

    @app.get("/api/auth/totp/setup")
    async def totp_setup(user: str = Depends(require_auth)):
        """获取 TOTP 设置信息"""
        secret = generate_totp_secret()
        uri = get_totp_uri(user)
        return {"secret": secret, "uri": uri, "enabled": TOTP_ENABLED}

    # ==================== 仪表盘路由 ====================

    @app.get("/api/dashboard/summary")
    async def dashboard_summary(user: str = Depends(require_auth)):
        """仪表盘摘要 - 所有关键指标"""
        from core.db import TradeRepository, CandidateRepository, RiskRepository
        from core.config import get_settings
        s = get_settings()

        open_trades = await TradeRepository.get_open()
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        # 今日盈亏
        today_pnl = 0.0
        today_trades_count = 0
        for t in open_trades:
            today_pnl += (t.get("tp1_locked_pnl") or 0) + (t.get("pnl") or 0)

        # 风控状态
        risk_state = await RiskRepository.get_or_create("default")
        daily_loss = await TradeRepository.get_today_realized_loss("default")
        consecutive_losses = await TradeRepository.get_consecutive_losses("default")


        # 候选池
        candidates = await CandidateRepository.get_active()

        return {
            "open_trades": len(open_trades),
            "today_pnl": round(today_pnl, 2),
            "total_stake": sum(t.get("stake_remaining", 0) for t in open_trades),
            "candidates_count": len(candidates),
            "daily_loss": round(daily_loss, 2),
            "daily_loss_limit": s.risk.max_daily_loss,
            "consecutive_losses": consecutive_losses,
            "today_trades": await TradeRepository.get_today_trades_count("default"),
            "max_daily_trades": s.risk.max_daily_trades,
            "system_version": s.version,
            "environment": s.environment,
        }

    # ==================== 交易路由 ====================

    @app.get("/api/trades")
    async def get_trades(
        status: Optional[str] = None,
        direction: Optional[str] = None,
        exchange: Optional[str] = None,
        limit: int = 100,
        user: str = Depends(require_auth),
    ):
        """获取交易列表"""
        from core.db import TradeRepository
        if status == "open":
            trades = await TradeRepository.get_open()
        else:
            trades = await TradeRepository.get_open()  # 简化，实际需分页
        # 过滤
        if direction:
            trades = [t for t in trades if t.get("direction") == direction]
        if exchange:
            trades = [t for t in trades if t.get("exchange") == exchange]
        return {"trades": trades[:limit]}


    @app.get("/api/trades/{trade_id}")
    async def get_trade(trade_id: str, user: str = Depends(require_auth)):
        """获取单笔交易详情"""
        from core.db import TradeRepository
        trade = await TradeRepository.get_by_id(trade_id)
        if not trade:
            raise HTTPException(404, "Trade not found")
        return trade

    @app.post("/api/trades/{trade_id}/close")
    async def close_trade(trade_id: str, user: str = Depends(require_auth)):
        """手动平仓"""
        from core.events import EventType, get_event_bus
        bus = await get_event_bus()
        await bus.publish(EventType.RISK_ALERT, {
            "alert_type": "manual_close",
            "trade_id": trade_id,
            "triggered_by": user,
        })
        return {"status": "ok", "trade_id": trade_id}

    @app.post("/api/trades/panic-close-all")
    async def panic_close_all(user: str = Depends(require_auth)):
        """紧急全平仓"""
        from core.events import EventType, get_event_bus
        from core.db import TradeRepository
        bus = await get_event_bus()
        await bus.publish(EventType.SYSTEM_PANIC, {
            "reason": f"Manual panic by {user}",
            "action": "close_all",
            "triggered_by": user,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        open_trades = await TradeRepository.get_open()
        return {"status": "ok", "positions_to_close": len(open_trades)}

    # ==================== 候选池路由 ====================

    @app.get("/api/candidates")
    async def get_candidates(
        strategy: Optional[str] = None,
        direction: Optional[str] = None,
        user: str = Depends(require_auth),
    ):
        """获取候选池"""
        from core.db import CandidateRepository
        candidates = await CandidateRepository.get_active(
            strategy=strategy, direction=direction
        )
        return {"candidates": candidates}


    # ==================== 信号路由 ====================

    @app.get("/api/signals")
    async def get_signals(
        strategy: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
        user: str = Depends(require_auth),
    ):
        """获取信号日志"""
        from core.db import SignalLogRepository
        signals = await SignalLogRepository.get_recent(
            symbol=symbol, strategy=strategy, limit=limit
        )
        return {"signals": signals}

    @app.get("/api/signals/stats")
    async def get_signal_stats(user: str = Depends(require_auth)):
        """获取信号统计"""
        from core.db import SignalLogRepository
        short_stats = await SignalLogRepository.get_trigger_rate("short_overbought")
        long_stats = await SignalLogRepository.get_trigger_rate("long_oversold")
        prepump_stats = await SignalLogRepository.get_trigger_rate("prepump_sniffer")
        return {
            "short_overbought": short_stats,
            "long_oversold": long_stats,
            "prepump_sniffer": prepump_stats,
        }

    # ==================== 风控路由 ====================

    @app.get("/api/risk/status")
    async def get_risk_status(user: str = Depends(require_auth)):
        """获取风控状态"""
        from core.db import TradeRepository, RiskRepository
        from core.config import get_settings
        s = get_settings()
        risk_state = await RiskRepository.get_or_create("default")
        daily_loss = await TradeRepository.get_today_realized_loss("default")
        consecutive = await TradeRepository.get_consecutive_losses("default")
        today_trades = await TradeRepository.get_today_trades_count("default")
        total_stake = await TradeRepository.get_total_open_stake("default")


        return {
            "is_paused": risk_state.get("paused_until") is not None,
            "paused_until": risk_state.get("paused_until"),
            "daily_loss": round(daily_loss, 2),
            "daily_loss_limit": s.risk.max_daily_loss,
            "consecutive_losses": consecutive,
            "consecutive_loss_limit": s.risk.consecutive_loss_pause,
            "today_trades": today_trades,
            "daily_trades_limit": s.risk.max_daily_trades,
            "total_stake": round(total_stake, 2),
            "max_stake": s.risk.max_stake,
            "max_daily_trades_short": s.risk.max_daily_trades_short,
            "max_daily_trades_long": s.risk.max_daily_trades_long,
            "cooldown_hours": s.risk.cooldown_hours,
        }

    @app.post("/api/risk/toggle-pause")
    async def toggle_risk_pause(body: PauseRequest, user: str = Depends(require_auth)):
        """手动暂停/恢复交易"""
        from core.events import EventType, get_event_bus
        bus = await get_event_bus()
        if body.paused:
            await bus.publish(EventType.RISK_PAUSED, {
                "reason": body.reason,
                "duration_minutes": body.duration_minutes,
                "paused_by": user,
            })
        else:
            await bus.publish(EventType.RISK_RESUMED, {
                "reason": body.reason,
                "resumed_by": user,
            })
        return {"status": "ok", "paused": body.paused}

    @app.get("/api/risk/events")
    async def get_risk_events(limit: int = 20, user: str = Depends(require_auth)):
        """获取风控事件"""
        from core.db import EventRepository
        events = await EventRepository.get_recent(event_type="risk.alert", limit=limit)
        return {"events": events}


    # ==================== 配置路由 ====================

    @app.get("/api/config/all")
    async def get_all_config(user: str = Depends(require_auth)):
        """获取所有配置 - 完整输出"""
        from core.config import get_settings
        s = get_settings()
        return {
            "system": {
                "version": s.version,
                "environment": s.environment,
                "debug": s.debug,
                "log_level": s.log_level,
            },
            "exchange": {
                "primary_exchange": s.exchange.primary_exchange,
                "leverage": s.exchange.leverage,
                "max_open_trades": s.exchange.max_open_trades,
                "position_mode": s.exchange.position_mode,
                "slippage_alert_pct": s.exchange.slippage_alert_pct,
                "price_divergence_max_pct": s.exchange.price_divergence_max_pct,
            },
            "risk": {
                "max_daily_loss": s.risk.max_daily_loss,
                "max_daily_trades": s.risk.max_daily_trades,
                "max_daily_trades_short": s.risk.max_daily_trades_short,
                "max_daily_trades_long": s.risk.max_daily_trades_long,
                "consecutive_loss_pause": s.risk.consecutive_loss_pause,
                "pause_hours": s.risk.pause_hours,
                "max_position_pct": s.risk.max_position_pct,
                "default_stake": s.risk.default_stake,
                "max_stake": s.risk.max_stake,
                "cooldown_hours": s.risk.cooldown_hours,
                "cooldown_scope": s.risk.cooldown_scope,
            },
            "strategy": {
                "vol_min": s.strategy.vol_min,
                "price_max": s.strategy.price_max,
                "pct_24h_min": s.strategy.pct_24h_min,
                "rsi_period": s.strategy.rsi_period,
                "daily_rsi_min": s.strategy.daily_rsi_min,
                "h4_rsi_enter": s.strategy.h4_rsi_enter,
                "h4_rsi_drop": s.strategy.h4_rsi_drop,


                "oi_change_min": s.strategy.oi_change_min,
                "funding_max": s.strategy.funding_max,
                "funding_min": s.strategy.funding_min,
                "funding_hot": s.strategy.funding_hot,
                "tp1_pct": s.strategy.tp1_pct,
                "tp2_pct": s.strategy.tp2_pct,
                "tp1_close_ratio": s.strategy.tp1_close_ratio,
                "hard_stop_pct": s.strategy.hard_stop_pct,
                "trail_activate_pct": s.strategy.trail_activate_pct,
                "trail_retrace_ratio": s.strategy.trail_retrace_ratio,
                "max_hold_hours": s.strategy.max_hold_hours,
                "score_full_threshold": s.strategy.score_full_threshold,
                "score_half_threshold": s.strategy.score_half_threshold,
                "score_skip_threshold": s.strategy.score_skip_threshold,
                "btc_filter_enabled": s.strategy.btc_filter_enabled,
                "btc_crash_threshold": s.strategy.btc_crash_threshold,
                "btc_pump_threshold": s.strategy.btc_pump_threshold,
            },
            "monitoring": {
                "prometheus_enabled": s.monitoring.prometheus_enabled,
                "prometheus_port": s.monitoring.prometheus_port,
                "health_check_interval": s.monitoring.health_check_interval,
                "reconciliation_interval_minutes": s.monitoring.reconciliation_interval_minutes,
            },
            "telegram": {
                "enabled": s.telegram.enabled,
                "bot_token_set": bool(s.telegram.bot_token),
                "chat_id_set": bool(s.telegram.chat_id),
            },
            "optimization": {
                "wfa_enabled": s.optimization.wfa_enabled,
                "wfa_schedule_day": s.optimization.wfa_schedule_day,
                "wfa_lookback_days": s.optimization.wfa_lookback_days,
                "wfa_sharpe_threshold": s.optimization.wfa_sharpe_threshold,
                "wfa_max_drawdown_threshold": s.optimization.wfa_max_drawdown_threshold,
                "auto_update_enabled": s.optimization.auto_update_enabled,
            },
        }


    @app.post("/api/config/update")
    async def update_config(body: ConfigUpdateRequest, user: str = Depends(require_auth)):
        """更新配置项"""
        from core.config import get_settings
        from core.events import EventType, get_event_bus
        from core.db import SystemStateRepository
        s = get_settings()

        section_map = {
            "exchange": s.exchange,
            "risk": s.risk,
            "strategy": s.strategy,
            "monitoring": s.monitoring,
            "telegram": s.telegram,
            "optimization": s.optimization,
        }
        target = section_map.get(body.section)
        if not target:
            raise HTTPException(400, f"Invalid section: {body.section}")
        if not hasattr(target, body.key):
            raise HTTPException(400, f"Invalid key: {body.section}.{body.key}")

        # 类型转换
        current = getattr(target, body.key)
        try:
            if isinstance(current, bool):
                value = bool(body.value)
            elif isinstance(current, int):
                value = int(body.value)
            elif isinstance(current, float):
                value = float(body.value)
            else:
                value = str(body.value)
        except (ValueError, TypeError) as e:
            raise HTTPException(400, f"Invalid value type: {e}")

        setattr(target, body.key, value)

        # 持久化
        config_key = f"config.{body.section}.{body.key}"
        await SystemStateRepository.set(config_key, str(value))

        # 发布事件
        bus = await get_event_bus()
        await bus.publish(EventType.CONFIG_CHANGED, {
            "key": f"{body.section}.{body.key}",
            "value": value,
            "changed_by": user,
        })
        return {"status": "ok", "key": f"{body.section}.{body.key}", "value": value}


    # ==================== 密钥管理路由 (多账户) ====================

    @app.get("/api/accounts")
    async def list_accounts(
        exchange: Optional[str] = None,
        user: str = Depends(require_auth),
    ):
        """获取所有交易所账户列表（密钥脱敏）"""
        from core.db import ExchangeAccountRepository
        accounts = await ExchangeAccountRepository.get_all(exchange=exchange)
        # 脱敏：不返回明文密钥
        safe_accounts = []
        for a in accounts:
            safe_accounts.append({
                "id": a["id"],
                "account_id": a["account_id"],
                "label": a["label"],
                "exchange": a["exchange"],
                "api_key_masked": _mask_key(a.get("api_key", "")),
                "has_secret": bool(a.get("api_secret")),
                "has_passphrase": bool(a.get("passphrase")),
                "leverage": a["leverage"],
                "position_mode": a["position_mode"],
                "max_stake": a["max_stake"],
                "is_active": a["is_active"],
                "is_primary": a["is_primary"],
                "note": a.get("note", ""),
                "created_at": str(a.get("created_at", "")),
            })
        return {"accounts": safe_accounts}

    @app.post("/api/accounts")
    async def create_account(
        body: Dict[str, Any] = Body(...),
        user: str = Depends(require_auth),
    ):
        """
        创建交易所账户
        {
            "account_id": "binance_main",
            "label": "Binance 主账户",
            "exchange": "binance",
            "api_key": "xxx",
            "api_secret": "xxx",
            "passphrase": "",
            "leverage": 10,
            "max_stake": 100,
            "is_primary": true,
            "note": ""
        }
        """
        from core.db import ExchangeAccountRepository
        required = ["account_id", "exchange", "api_key", "api_secret"]
        for field in required:
            if not body.get(field):
                raise HTTPException(400, f"Missing required field: {field}")

        valid_exchanges = ["binance", "okx", "bybit", "gate", "bitget"]
        if body["exchange"] not in valid_exchanges:
            raise HTTPException(400, f"Invalid exchange. Must be one of: {valid_exchanges}")

        # 检查 account_id 是否已存在
        existing = await ExchangeAccountRepository.get_by_id(body["account_id"])
        if existing:
            raise HTTPException(409, f"Account ID already exists: {body['account_id']}")

        account_data = {
            "account_id": body["account_id"],
            "label": body.get("label", body["account_id"]),
            "exchange": body["exchange"],
            "api_key": body["api_key"],
            "api_secret": body["api_secret"],
            "passphrase": body.get("passphrase", ""),
            "leverage": body.get("leverage", 10),
            "position_mode": body.get("position_mode", "one_way"),
            "max_stake": body.get("max_stake", 100.0),
            "is_active": body.get("is_active", True),
            "is_primary": body.get("is_primary", False),
            "note": body.get("note", ""),
        }

        # 如果设为主账户，先取消同交易所其他主账户
        if account_data["is_primary"]:
            all_accounts = await ExchangeAccountRepository.get_all(exchange=body["exchange"])
            for a in all_accounts:
                if a["is_primary"]:
                    await ExchangeAccountRepository.update(a["account_id"], {"is_primary": False})

        result = await ExchangeAccountRepository.create(account_data)
        logger.info(f"Exchange account created: {body['account_id']} ({body['exchange']}) by {user}")
        return {"status": "ok", "account_id": result["account_id"]}

    @app.put("/api/accounts/{account_id}")
    async def update_account(
        account_id: str,
        body: Dict[str, Any] = Body(...),
        user: str = Depends(require_auth),
    ):
        """
        更新交易所账户
        可更新字段: label, api_key, api_secret, passphrase, leverage,
                    position_mode, max_stake, is_active, is_primary, note
        """
        from core.db import ExchangeAccountRepository
        existing = await ExchangeAccountRepository.get_by_id(account_id)
        if not existing:
            raise HTTPException(404, f"Account not found: {account_id}")

        allowed_fields = {
            "label", "api_key", "api_secret", "passphrase",
            "leverage", "position_mode", "max_stake",
            "is_active", "is_primary", "note",
        }
        updates = {k: v for k, v in body.items() if k in allowed_fields and v is not None}

        # 空字符串的密钥字段不更新（保留原值）
        if "api_key" in updates and not updates["api_key"]:
            del updates["api_key"]
        if "api_secret" in updates and not updates["api_secret"]:
            del updates["api_secret"]
        if "passphrase" in updates and updates["passphrase"] == "":
            del updates["passphrase"]

        # 如果设为主账户
        if updates.get("is_primary"):
            await ExchangeAccountRepository.set_primary(account_id)
            updates.pop("is_primary", None)

        if updates:
            await ExchangeAccountRepository.update(account_id, updates)

        logger.info(f"Exchange account updated: {account_id} by {user}")
        return {"status": "ok", "account_id": account_id}

    @app.delete("/api/accounts/{account_id}")
    async def delete_account(account_id: str, user: str = Depends(require_auth)):
        """删除交易所账户"""
        from core.db import ExchangeAccountRepository
        success = await ExchangeAccountRepository.delete(account_id)
        if not success:
            raise HTTPException(404, f"Account not found: {account_id}")
        logger.info(f"Exchange account deleted: {account_id} by {user}")
        return {"status": "ok", "account_id": account_id}

    @app.post("/api/accounts/{account_id}/set-primary")
    async def set_account_primary(account_id: str, user: str = Depends(require_auth)):
        """将指定账户设为该交易所的主账户"""
        from core.db import ExchangeAccountRepository
        success = await ExchangeAccountRepository.set_primary(account_id)
        if not success:
            raise HTTPException(404, f"Account not found: {account_id}")
        return {"status": "ok", "account_id": account_id}

    @app.get("/api/accounts/grouped")
    async def get_accounts_grouped(user: str = Depends(require_auth)):
        """按交易所分组获取账户（用于下拉选择等）"""
        from core.db import ExchangeAccountRepository
        grouped = await ExchangeAccountRepository.get_active_by_exchange()
        # 脱敏
        safe_grouped = {}
        for exchange, accounts in grouped.items():
            safe_grouped[exchange] = [
                {
                    "account_id": a["account_id"],
                    "label": a["label"],
                    "is_primary": a["is_primary"],
                    "leverage": a["leverage"],
                    "max_stake": a["max_stake"],
                }
                for a in accounts
            ]
        return {"exchanges": safe_grouped}

    # ==================== Telegram 配置 ====================

    @app.get("/api/secrets/telegram")
    async def get_telegram_secrets(user: str = Depends(require_auth)):
        """获取 Telegram 配置状态"""
        from core.config import get_settings
        s = get_settings()
        return {
            "enabled": s.telegram.enabled,
            "bot_token_set": bool(s.telegram.bot_token),
            "bot_token_masked": _mask_key(s.telegram.bot_token),
            "chat_id": s.telegram.chat_id,
        }

    @app.post("/api/secrets/telegram")
    async def update_telegram_secrets(
        body: Dict[str, Any] = Body(...),
        user: str = Depends(require_auth),
    ):
        """更新 Telegram 配置"""
        from core.config import get_settings
        from core.db import SystemStateRepository
        s = get_settings()
        if "bot_token" in body and body["bot_token"]:
            s.telegram.bot_token = body["bot_token"]
            await SystemStateRepository.set("secret.telegram.bot_token", body["bot_token"])
        if "chat_id" in body and body["chat_id"]:
            s.telegram.chat_id = body["chat_id"]
            await SystemStateRepository.set("secret.telegram.chat_id", body["chat_id"])
        if "enabled" in body:
            s.telegram.enabled = bool(body["enabled"])
        return {"status": "ok"}


    # ==================== 策略路由 ====================

    @app.get("/api/strategy/blacklist")
    async def get_blacklist(user: str = Depends(require_auth)):
        """获取黑名单"""
        from core.db import SystemStateRepository
        stored = await SystemStateRepository.get("blacklist")
        blacklist = json.loads(stored) if stored else []
        return {"blacklist": blacklist, "count": len(blacklist)}

    @app.post("/api/strategy/blacklist")
    async def add_blacklist(body: BlacklistRequest, user: str = Depends(require_auth)):
        """添加黑名单"""
        from core.db import SystemStateRepository
        from core.events import get_event_bus
        stored = await SystemStateRepository.get("blacklist")
        blacklist = json.loads(stored) if stored else []
        if body.symbol not in blacklist:
            blacklist.append(body.symbol)
        await SystemStateRepository.set("blacklist", json.dumps(blacklist))
        bus = await get_event_bus()
        await bus.publish("strategy.blacklist_added", {
            "symbol": body.symbol, "reason": body.reason, "added_by": user,
        })
        return {"status": "ok", "blacklist": blacklist}

    @app.delete("/api/strategy/blacklist/{symbol:path}")
    async def remove_blacklist(symbol: str, user: str = Depends(require_auth)):
        """移除黑名单"""
        from core.db import SystemStateRepository
        stored = await SystemStateRepository.get("blacklist")
        blacklist = json.loads(stored) if stored else []
        blacklist = [s for s in blacklist if s != symbol]
        await SystemStateRepository.set("blacklist", json.dumps(blacklist))
        return {"status": "ok", "blacklist": blacklist}

    @app.post("/api/strategy/regime")
    async def force_regime(body: RegimeRequest, user: str = Depends(require_auth)):
        """强制设置市场状态"""
        from core.events import EventType, get_event_bus
        valid = ["trending_up", "trending_down", "ranging", "high_vol", "crash", "recovery"]
        if body.regime not in valid:
            raise HTTPException(400, f"Invalid regime. Must be one of: {valid}")
        bus = await get_event_bus()
        await bus.publish(EventType.MARKET_REGIME_CHANGED, {
            "old_regime": "manual",
            "new_regime": body.regime,
            "confidence": 1.0,
            "reason": body.reason,
            "forced_by": user,
        })
        return {"status": "ok", "regime": body.regime}


    # ==================== 系统路由 ====================

    @app.get("/api/system/health")
    async def system_health(user: str = Depends(require_auth)):
        """系统健康状态"""
        from core.config import get_settings
        s = get_settings()
        return {
            "status": "running",
            "version": s.version,
            "environment": s.environment,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/api/system/reconciliation")
    async def reconciliation_status(user: str = Depends(require_auth)):
        """对账状态"""
        from services.monitor.healing import get_healing_service
        healing = get_healing_service()
        return {
            "status": "active" if healing._running else "inactive",
            "stats": healing._reconciliation_stats,
            "circuit_breakers": healing.get_circuit_breakers(),
        }

    @app.post("/api/system/reconciliation/run")
    async def run_reconciliation(user: str = Depends(require_auth)):
        """手动触发对账"""
        from services.monitor.healing import get_healing_service
        healing = get_healing_service()
        result = await healing._run_reconciliation()
        return {"status": "ok", "result": result}

    @app.post("/api/system/circuit-breaker/reset")
    async def reset_circuit_breaker(
        body: Dict[str, str] = Body(...),
        user: str = Depends(require_auth),
    ):
        """重置熔断器"""
        from services.monitor.healing import get_healing_service, CircuitState
        exchange = body.get("exchange", "")
        if not exchange:
            raise HTTPException(400, "exchange required")
        healing = get_healing_service()
        if exchange in healing._circuit_breakers:
            b = healing._circuit_breakers[exchange]
            b.state = CircuitState.CLOSED
            b.failure_count = 0
            b.open_until = None
            return {"status": "ok", "exchange": exchange}
        raise HTTPException(404, f"No breaker for {exchange}")

    @app.post("/api/system/recover")
    async def system_recover(user: str = Depends(require_auth)):
        """系统一键恢复"""
        from services.monitor.healing import get_healing_service, CircuitState
        from core.events import EventType, get_event_bus
        healing = get_healing_service()
        reset_count = 0
        for ex, b in healing._circuit_breakers.items():
            if b.state != CircuitState.CLOSED:
                b.state = CircuitState.CLOSED
                b.failure_count = 0
                b.open_until = None
                reset_count += 1
        bus = await get_event_bus()
        await bus.publish(EventType.SYSTEM_RECOVER, {
            "reason": f"Recovery by {user}", "reset_breakers": reset_count,
        })
        return {"status": "ok", "reset_breakers": reset_count}


    @app.get("/api/system/events")
    async def get_system_events(
        event_type: Optional[str] = None,
        limit: int = 50,
        user: str = Depends(require_auth),
    ):
        """获取系统事件"""
        from core.db import EventRepository
        events = await EventRepository.get_recent(event_type=event_type, limit=limit)
        return {"events": events}

    @app.get("/api/system/validation")
    async def system_validation(user: str = Depends(require_auth)):
        """事件闭环验证"""
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
            },
        }

    @app.get("/api/config/manager")
    async def config_manager_status(user: str = Depends(require_auth)):
        """配置管理器状态"""
        from core.config.manager import get_config_manager
        manager = await get_config_manager()
        return manager.get_status()

    # ==================== 优化路由 ====================

    @app.post("/api/optimization/run")
    async def run_optimization(user: str = Depends(require_auth)):
        """立即触发 WFA 优化"""
        from core.events import EventType, get_event_bus
        bus = await get_event_bus()
        await bus.publish(EventType.OPTIMIZATION_COMPLETED, {
            "trigger": "manual", "triggered_by": user,
        })
        return {"status": "ok", "message": "Optimization queued"}

    @app.get("/api/optimization/history")
    async def get_optimization_history(user: str = Depends(require_auth)):
        """获取优化历史"""
        try:
            from services.optimization import OptimizationService
            svc = OptimizationService()
            history = await svc.get_optimization_history()
            return {"history": history}
        except Exception:
            return {"history": []}

    # ==================== 回测路由 ====================

    @app.post("/api/backtesting/monte-carlo")
    async def run_monte_carlo(user: str = Depends(require_auth)):
        """运行蒙特卡洛稳健性测试"""
        from backtesting.monte_carlo import MonteCarloSimulator
        from core.db import TradeRepository
        trades = await TradeRepository.get_closed(limit=1000)
        
        simulator = MonteCarloSimulator(n_simulations=1000)
        result = simulator.simulate(trades)
        
        return {
            "robustness_score": result.robustness_score,
            "is_robust": result.is_robust(),
            "mean_return": result.mean_return,
            "max_drawdown_mean": result.max_drawdown_mean,
            "win_rate_mean": result.win_rate_mean,
            "profit_factor_mean": result.profit_factor_mean,
            "var_95": result.var_95,
            "percentile_5": result.percentile_5,
            "percentile_95": result.percentile_95,
        }

    # ==================== WebSocket ====================

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket 实时推送"""
        await websocket.accept()
        ws_connections.append(websocket)
        try:
            while True:
                data = await websocket.receive_text()
                logger.debug(f"WS received: {data}")
        except WebSocketDisconnect:
            ws_connections.remove(websocket)
        except Exception:
            if websocket in ws_connections:
                ws_connections.remove(websocket)

    async def broadcast(message: Dict[str, Any]):
        """广播消息到所有 WS 连接"""
        for ws in ws_connections.copy():
            try:
                await ws.send_json(message)
            except Exception:
                ws_connections.remove(ws)


    # ==================== 事件监听注册 ====================

    @app.on_event("startup")
    async def on_startup():
        """启动时注册事件监听"""
        from core.events import EventType, get_event_bus
        bus = await get_event_bus()

        async def on_trade_opened(event):
            await broadcast({"type": "trade.opened", "data": event.data})
        async def on_trade_closed(event):
            await broadcast({"type": "trade.closed", "data": event.data})
        async def on_risk_alert(event):
            await broadcast({"type": "risk.alert", "data": event.data})
        async def on_signal(event):
            await broadcast({"type": "signal.triggered", "data": event.data})
        async def on_candidate(event):
            await broadcast({"type": "candidate.added", "data": event.data})
        async def on_config(event):
            await broadcast({"type": "config.changed", "data": event.data})

        await bus.subscribe(EventType.TRADE_OPENED, on_trade_opened)
        await bus.subscribe(EventType.TRADE_CLOSED, on_trade_closed)
        await bus.subscribe(EventType.RISK_ALERT, on_risk_alert)
        await bus.subscribe(EventType.SIGNAL_TRIGGERED, on_signal)
        await bus.subscribe(EventType.CANDIDATE_ADDED, on_candidate)
        await bus.subscribe(EventType.CONFIG_CHANGED, on_config)
        logger.info("Web event listeners registered")

    # ==================== 前端 SPA 托管 ====================

    if FRONTEND_DIR.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

        @app.get("/{path:path}", response_class=HTMLResponse)
        async def serve_spa(request: Request, path: str):
            if path.startswith("api/") or path.startswith("ws"):
                raise HTTPException(404)
            file_path = FRONTEND_DIR / path
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(FRONTEND_DIR / "index.html")
    else:
        @app.get("/", response_class=HTMLResponse)
        async def no_frontend():
            return "<html><body style='background:#111;color:#fff;font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh'><div style='text-align:center'><h1>Altcoin Nexus API</h1><p>Frontend not built. Run: cd frontend && npm run build</p></div></body></html>"

    return app



# === 工具函数 ===

def _mask_key(key: str) -> str:
    """遮蔽密钥，仅显示前4位和后4位"""
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}****{key[-4:]}"
