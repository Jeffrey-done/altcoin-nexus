"""
异步风控服务
事件驱动 + 行级锁，毫秒级响应
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from core.config import get_settings
from core.config.refresh import ConfigRefreshMixin
from core.db import RiskRepository, TradeRepository, get_db
from core.events import EventType, get_event_bus

logger = logging.getLogger("nexus.risk")


class RiskControlService(ConfigRefreshMixin):
    """
    风控服务 - 事件驱动模式
    
    设计原则：
    1. 主动风控：订阅信号/订单事件，毫秒级拦截
    2. 被动风控：定时轮询作为兜底
    3. 行级锁：所有状态更新使用数据库行级锁
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._running = False
        
        # 事件订阅 ID
        self._subscriptions: List[str] = []
        
        # 被动监控任务
        self._monitor_task: Optional[asyncio.Task] = None
        
        # 风控状态缓存（内存快速访问）
        self._risk_cache: Dict[str, Dict[str, Any]] = {}
        self._paused_until: Dict[str, datetime] = {}
        
        # 统计
        self._stats = {
            "checks_total": 0,
            "blocks_total": 0,
            "last_check": None,
        }
    
    async def start(self) -> None:
        """启动风控服务"""
        if self._running:
            return
        
        self._running = True
        
        # 从数据库加载暂停状态
        await self._load_paused_states()
        
        # 注册事件监听（主动风控）
        await self._register_event_listeners()
        
        # 设置配置热刷新
        await self._setup_config_refresh()
        
        # 启动被动监控（兜底）
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        
        logger.info("RiskControlService started (event-driven mode)")
    
    async def _load_paused_states(self) -> None:
        """从数据库加载暂停状态"""
        try:
            # 获取所有风控状态
            from core.db import get_db
            from core.db.models import RiskStateModel
            from sqlalchemy import select, and_
            
            db = await get_db()
            async with db.session() as session:
                now = datetime.now(timezone.utc)
                result = await session.execute(
                    select(RiskStateModel).where(
                        and_(
                            RiskStateModel.paused_until != None,
                            RiskStateModel.paused_until > now.isoformat(),
                        )
                    )
                )
                states = result.scalars().all()
                
                for state in states:
                    try:
                        paused_until = datetime.fromisoformat(state.paused_until)
                        if paused_until > now:
                            self._paused_until[state.account_id] = paused_until
                            logger.info(f"Loaded paused state: {state.account_id} until {paused_until}")
                    except Exception as e:
                        logger.warning(f"Failed to parse paused_until for {state.account_id}: {e}")
        except Exception as e:
            logger.warning(f"Failed to load paused states: {e}")
    
    async def stop(self) -> None:
        """停止风控服务"""
        self._running = False
        
        # 取消事件订阅
        bus = await get_event_bus()
        for sub_id in self._subscriptions:
            await bus.unsubscribe(sub_id)
        self._subscriptions.clear()
        
        # 清理配置刷新监听
        await self._cleanup_config_refresh()
        
        # 停止被动监控
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("RiskControlService stopped")
    
    async def _register_event_listeners(self) -> None:
        """注册事件监听 - 实现主动风控"""
        bus = await get_event_bus()
        
        # 监听信号生成事件 - 预审
        sub_id = await bus.subscribe(
            EventType.SIGNAL_TRIGGERED,
            self._on_signal_triggered,
            "risk_signal_precheck"
        )
        self._subscriptions.append(sub_id)
        
        # 监听订单成交事件 - 更新风控状态
        sub_id = await bus.subscribe(
            EventType.EXECUTION_ORDER_FILLED,
            self._on_order_filled,
            "risk_order_filled"
        )
        self._subscriptions.append(sub_id)
        
        # 监听订单失败事件
        sub_id = await bus.subscribe(
            EventType.EXECUTION_ORDER_FAILED,
            self._on_order_failed,
            "risk_order_failed"
        )
        self._subscriptions.append(sub_id)
        
        # 监听平仓事件
        sub_id = await bus.subscribe(
            EventType.TRADE_CLOSED,
            self._on_trade_closed,
            "risk_trade_closed"
        )
        self._subscriptions.append(sub_id)
        
        logger.info("Risk event listeners registered")
    
    async def _on_signal_triggered(self, event) -> None:
        """
        信号预审 - 毫秒级风控拦截
        
        在信号产生的瞬间进行风控检查，如果不通过则阻止开仓
        """
        signal_data = event.data
        symbol = signal_data.get("symbol", "")
        account_id = signal_data.get("account_id", "default")
        stake = signal_data.get("stake", self.settings.risk.default_stake)
        direction = signal_data.get("direction", "SHORT")
        
        self._stats["checks_total"] += 1
        
        # 快速风控检查 - 异常时默认拒绝
        can_open = False
        reason = "Risk system initialization state"
        try:
            can_open, reason = await self.check_can_open(
                account_id=account_id,
                symbol=symbol,
                direction=direction,
                stake=stake,
            )
        except Exception as e:
            logger.critical(
                f"CRITICAL: Risk check encountered exception: {e} - FORCE BLOCK",
                exc_info=True,
            )
            can_open = False
            reason = f"Internal Risk Exception: {e}"
        
        if not can_open:
            self._stats["blocks_total"] += 1
            logger.warning(f"Risk BLOCKED signal: {symbol} - {reason}")
            
            # 发布风控阻止事件
            bus = await get_event_bus()
            await bus.publish(EventType.RISK_ALERT, {
                "alert_type": "signal_blocked",
                "symbol": symbol,
                "reason": reason,
                "account_id": account_id,
            })
            
            # 修改信号数据，标记为被风控阻止
            signal_data["risk_blocked"] = True
            signal_data["risk_block_reason"] = reason
    
    async def _on_order_filled(self, event) -> None:
        """订单成交 - 更新风控状态"""
        order_data = event.data
        account_id = order_data.get("account_id", "default")
        
        # 更新今日开仓数
        await RiskRepository.increment_daily_trades(account_id)
        
        # 更新缓存
        if account_id in self._risk_cache:
            self._risk_cache[account_id]["daily_trades_opened"] = \
                self._risk_cache[account_id].get("daily_trades_opened", 0) + 1
        
        logger.info(f"Risk updated: order filled for {account_id}")
    
    async def _on_order_failed(self, event) -> None:
        """订单失败 - 记录但不影响风控状态"""
        order_data = event.data
        logger.warning(f"Order failed: {order_data}")
    
    async def _on_trade_closed(self, event) -> None:
        """平仓 - 更新风控状态"""
        trade_data = event.data
        account_id = trade_data.get("account_id", "default")
        pnl = trade_data.get("pnl", 0)
        trade_id = trade_data.get("trade_id", "")
        
        # 记录盈亏
        if pnl < 0:
            await self.record_trade_closed(account_id, trade_id, pnl)
        
        logger.info(f"Risk updated: trade closed pnl={pnl}")
    
    async def _monitor_loop(self) -> None:
        """被动监控循环 - 作为兜底"""
        while self._running:
            try:
                await self._check_all_accounts()
                self._stats["last_check"] = datetime.now(timezone.utc).isoformat()
                await asyncio.sleep(60)  # 每分钟检查一次
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Risk monitor error: {e}", exc_info=True)
                await asyncio.sleep(30)
    
    async def _check_all_accounts(self) -> None:
        """检查所有账户的风控状态"""
        # 获取所有持仓
        open_trades = await TradeRepository.get_open()
        
        # 检查止损/止盈价格
        await self._check_stop_levels(open_trades)
        
        # 按账户分组
        accounts: Dict[str, List[Dict]] = {}
        for trade in open_trades:
            account_id = trade.get("account_id", "")
            if account_id not in accounts:
                accounts[account_id] = []
            accounts[account_id].append(trade)
        
        # 检查每个账户
        for account_id, trades in accounts.items():
            try:
                await self._check_account(account_id, trades)
            except Exception as e:
                logger.error(f"Risk check error for {account_id}: {e}")
    
    async def _check_stop_levels(self, open_trades: List[Dict[str, Any]]) -> None:
        """
        检查止损/止盈价格 - 主动触发平仓
        """
        bus = await get_event_bus()
        
        for trade in open_trades:
            try:
                symbol = trade.get("symbol", "")
                direction = trade.get("direction", "SHORT")
                trade_id = trade.get("id", "")
                
                # 获取当前价格（从缓存或交易所）
                current_price = trade.get("current_price")
                if not current_price:
                    continue
                
                # 硬止损检查
                hard_stop = trade.get("hard_stop_price")
                if hard_stop:
                    if direction == "SHORT" and current_price >= hard_stop:
                        logger.warning(f"HARD STOP triggered: {symbol} price={current_price} >= {hard_stop}")
                        await bus.publish(EventType.RISK_ALERT, {
                            "alert_type": "hard_stop_triggered",
                            "trade_id": trade_id,
                            "symbol": symbol,
                            "current_price": current_price,
                            "stop_price": hard_stop,
                        })
                    elif direction == "LONG" and current_price <= hard_stop:
                        logger.warning(f"HARD STOP triggered: {symbol} price={current_price} <= {hard_stop}")
                        await bus.publish(EventType.RISK_ALERT, {
                            "alert_type": "hard_stop_triggered",
                            "trade_id": trade_id,
                            "symbol": symbol,
                            "current_price": current_price,
                            "stop_price": hard_stop,
                        })
                
                # 移动止损检查
                trail_stop = trade.get("trail_stop_price")
                if trail_stop:
                    if direction == "SHORT" and current_price >= trail_stop:
                        logger.warning(f"TRAIL STOP triggered: {symbol} price={current_price} >= {trail_stop}")
                        await bus.publish(EventType.RISK_ALERT, {
                            "alert_type": "trail_stop_triggered",
                            "trade_id": trade_id,
                            "symbol": symbol,
                            "current_price": current_price,
                            "stop_price": trail_stop,
                        })
                    elif direction == "LONG" and current_price <= trail_stop:
                        logger.warning(f"TRAIL STOP triggered: {symbol} price={current_price} <= {trail_stop}")
                        await bus.publish(EventType.RISK_ALERT, {
                            "alert_type": "trail_stop_triggered",
                            "trade_id": trade_id,
                            "symbol": symbol,
                            "current_price": current_price,
                            "stop_price": trail_stop,
                        })
                
                # 止盈检查
                tp1 = trade.get("take_profit_1")
                if tp1 and not trade.get("tp1_triggered"):
                    if direction == "SHORT" and current_price <= tp1:
                        logger.info(f"TP1 triggered: {symbol} price={current_price} <= {tp1}")
                        await bus.publish(EventType.TRADE_TP1, {
                            "trade_id": trade_id,
                            "symbol": symbol,
                            "current_price": current_price,
                            "tp_price": tp1,
                        })
                    elif direction == "LONG" and current_price >= tp1:
                        logger.info(f"TP1 triggered: {symbol} price={current_price} >= {tp1}")
                        await bus.publish(EventType.TRADE_TP1, {
                            "trade_id": trade_id,
                            "symbol": symbol,
                            "current_price": current_price,
                            "tp_price": tp1,
                        })
            
            except Exception as e:
                logger.error(f"Stop level check error for {trade.get('symbol')}: {e}")
    
    async def _check_account(
        self,
        account_id: str,
        open_trades: List[Dict[str, Any]],
    ) -> None:
        """检查单个账户的风控状态"""
        risk_config = self.settings.risk
        bus = await get_event_bus()
        
        # 获取风控状态
        risk_state = await RiskRepository.get_or_create(account_id)
        
        # 检查日亏损
        daily_loss = await TradeRepository.get_today_realized_loss(account_id)
        if daily_loss >= risk_config.max_daily_loss:
            logger.warning(
                f"Account {account_id} daily loss limit reached: "
                f"{daily_loss} >= {risk_config.max_daily_loss}"
            )
            await bus.publish(EventType.RISK_ALERT, {
                "alert_type": "daily_loss_limit",
                "account_id": account_id,
                "daily_loss": daily_loss,
                "limit": risk_config.max_daily_loss,
            })
            # 暂停交易
            self._paused_until[account_id] = (
                datetime.now(timezone.utc) + timedelta(hours=risk_config.pause_hours)
            )
            return
        
        # 检查连续亏损
        consecutive_losses = await TradeRepository.get_consecutive_losses(account_id)
        if consecutive_losses >= risk_config.consecutive_loss_pause:
            logger.warning(
                f"Account {account_id} consecutive losses: {consecutive_losses}"
            )
            await bus.publish(EventType.RISK_ALERT, {
                "alert_type": "consecutive_losses",
                "account_id": account_id,
                "consecutive_losses": consecutive_losses,
                "limit": risk_config.consecutive_loss_pause,
            })
            # 持久化暂停状态
            paused_until = datetime.now(timezone.utc) + timedelta(hours=risk_config.pause_hours)
            self._paused_until[account_id] = paused_until
            await RiskRepository.update(account_id, {
                "paused_until": paused_until.isoformat()
            })
            return
        
        # 更新缓存
        self._risk_cache[account_id] = {
            "daily_loss": daily_loss,
            "consecutive_losses": consecutive_losses,
            "daily_trades_opened": risk_state.get("daily_trades_opened", 0),
            "total_open_stake": sum(t.get("stake_remaining", 0) for t in open_trades),
        }
    
    async def check_can_open(
        self,
        account_id: str,
        symbol: str,
        direction: str,
        stake: float,
    ) -> tuple[bool, str]:
        """
        检查是否可以开仓
        
        Returns:
            (可以开仓, 原因)
        """
        risk_config = self.settings.risk
        
        # 检查是否暂停
        if account_id in self._paused_until:
            if datetime.now(timezone.utc) < self._paused_until[account_id]:
                return False, "Account paused due to risk limits"
            else:
                del self._paused_until[account_id]
        
        # 优先使用缓存（快速路径）
        cached = self._risk_cache.get(account_id, {})
        
        # 检查日亏损
        daily_loss = cached.get("daily_loss") or await TradeRepository.get_today_realized_loss(account_id)
        if daily_loss >= risk_config.max_daily_loss:
            return False, f"Daily loss limit reached: {daily_loss}"
        
        # 检查连续亏损
        consecutive_losses = cached.get("consecutive_losses") or await TradeRepository.get_consecutive_losses(account_id)
        if consecutive_losses >= risk_config.consecutive_loss_pause:
            return False, f"Consecutive losses: {consecutive_losses}"
        
        # 检查今日开仓数
        today_trades = cached.get("daily_trades_opened") or await TradeRepository.get_today_trades_count(account_id)
        if today_trades >= risk_config.max_daily_trades:
            return False, f"Daily trades limit: {today_trades}"
        
        # 检查方向限制
        if direction == "SHORT":
            open_trades = await TradeRepository.get_open(account_id)
            short_count = len([t for t in open_trades if t.get("direction") == "SHORT"])
            if short_count >= risk_config.max_daily_trades_short:
                return False, f"Short trades limit: {short_count}"
        elif direction == "LONG":
            open_trades = await TradeRepository.get_open(account_id)
            long_count = len([t for t in open_trades if t.get("direction") == "LONG"])
            if long_count >= risk_config.max_daily_trades_long:
                return False, f"Long trades limit: {long_count}"
        
        # 检查持仓总额
        total_stake = cached.get("total_open_stake") or await TradeRepository.get_total_open_stake(account_id)
        if total_stake + stake > risk_config.max_stake:
            return False, f"Total stake would exceed limit: {total_stake + stake}"
        
        # 检查单一标的重复持仓
        open_trades = await TradeRepository.get_open(account_id)
        symbol_trades = [t for t in open_trades if t.get("symbol") == symbol]
        if symbol_trades:
            return False, f"Already have position in {symbol}"
        
        return True, "OK"
    
    async def record_trade_closed(
        self,
        account_id: str,
        trade_id: str,
        pnl: float,
    ) -> None:
        """记录平仓 - 使用行级锁"""
        if pnl < 0:
            await self.increment_daily_loss(account_id, pnl)
        
        # 更新连续亏损
        consecutive_losses = await TradeRepository.get_consecutive_losses(account_id)
        await RiskRepository.update_with_lock(account_id, {
            "consecutive_losses": consecutive_losses,
        })
        
        # 更新缓存 - 修复清零Bug
        if account_id in self._risk_cache:
            if pnl < 0:
                # 只在亏损时累加，盈利时不修改
                self._risk_cache[account_id]["daily_loss"] = \
                    self._risk_cache[account_id].get("daily_loss", 0) + abs(pnl)
            self._risk_cache[account_id]["consecutive_losses"] = consecutive_losses
        
        # 发布事件
        bus = await get_event_bus()
        await bus.publish(EventType.RISK_STATE_CHANGED, {
            "account_id": account_id,
            "trade_id": trade_id,
            "pnl": pnl,
        })

    async def increment_daily_loss(self, account_id: str, pnl: float) -> None:
        """
        累加日亏损并立即持久化。

        仅处理亏损，盈利不增加亏损度量。
        """
        if pnl >= 0:
            return

        loss_amount = abs(pnl)

        if account_id not in self._risk_cache:
            self._risk_cache[account_id] = {"daily_loss": 0.0}

        self._risk_cache[account_id]["daily_loss"] = (
            self._risk_cache[account_id].get("daily_loss", 0.0) + loss_amount
        )
        current_total_loss = self._risk_cache[account_id]["daily_loss"]

        await RiskRepository.update_with_lock(account_id, {
            "daily_loss": current_total_loss,
            "updated_at": datetime.now(timezone.utc),
        })
    
    async def get_risk_status(self, account_id: str) -> Dict[str, Any]:
        """获取风控状态"""
        risk_config = self.settings.risk
        
        risk_state = await RiskRepository.get_or_create(account_id)
        daily_loss = await TradeRepository.get_today_realized_loss(account_id)
        consecutive_losses = await TradeRepository.get_consecutive_losses(account_id)
        today_trades = await TradeRepository.get_today_trades_count(account_id)
        total_stake = await TradeRepository.get_total_open_stake(account_id)
        
        is_paused = account_id in self._paused_until and \
                    datetime.now(timezone.utc) < self._paused_until[account_id]
        
        return {
            "account_id": account_id,
            "is_paused": is_paused,
            "paused_until": self._paused_until.get(account_id),
            "daily_loss": daily_loss,
            "daily_loss_limit": risk_config.max_daily_loss,
            "consecutive_losses": consecutive_losses,
            "consecutive_loss_limit": risk_config.consecutive_loss_pause,
            "today_trades": today_trades,
            "daily_trades_limit": risk_config.max_daily_trades,
            "total_stake": total_stake,
            "max_stake": risk_config.max_stake,
            "stats": self._stats,
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "running": self._running,
            "mode": "event-driven",
            "subscriptions": len(self._subscriptions),
            "monitor_task": self._monitor_task is not None and not self._monitor_task.done(),
            "paused_accounts": list(self._paused_until.keys()),
            "stats": self._stats,
        }
