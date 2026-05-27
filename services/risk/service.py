"""
异步风控服务
基于数据库行级锁的实时风控
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from core.config import get_settings
from core.db import RiskRepository, TradeRepository, get_db
from core.events import EventType, get_event_bus

logger = logging.getLogger("nexus.risk")


class RiskControlService:
    """
    风控服务
    
    职责:
    - 账户级风控
    - 组合级风控
    - 策略级风控
    - 实时监控和告警
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        # 风控状态缓存
        self._risk_states: Dict[str, Dict[str, Any]] = {}
        self._paused_until: Dict[str, datetime] = {}
    
    async def start(self) -> None:
        """启动风控服务"""
        if self._running:
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("RiskControlService started")
    
    async def stop(self) -> None:
        """停止风控服务"""
        self._running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("RiskControlService stopped")
    
    async def _monitor_loop(self) -> None:
        """监控循环"""
        while self._running:
            try:
                await self._check_all_accounts()
                await asyncio.sleep(60)  # 每分钟检查一次
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Risk monitor error: {e}", exc_info=True)
                await asyncio.sleep(30)
    
    async def _check_all_accounts(self) -> None:
        """检查所有账户的风控状态"""
        bus = await get_event_bus()
        
        # 获取所有持仓
        open_trades = await TradeRepository.get_open()
        
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
            self._paused_until[account_id] = (
                datetime.now(timezone.utc) + timedelta(hours=risk_config.pause_hours)
            )
            return
        
        # 检查今日开仓数
        today_trades = await TradeRepository.get_today_trades_count(account_id)
        if today_trades >= risk_config.max_daily_trades:
            logger.warning(
                f"Account {account_id} daily trades limit: {today_trades}"
            )
            return
        
        # 检查持仓集中度
        total_stake = sum(t.get("stake_remaining", 0) for t in open_trades)
        if total_stake > risk_config.max_stake:
            logger.warning(
                f"Account {account_id} total stake too high: {total_stake}"
            )
            await bus.publish(EventType.RISK_ALERT, {
                "alert_type": "high_stake",
                "account_id": account_id,
                "total_stake": total_stake,
                "limit": risk_config.max_stake,
            })
        
        # 更新风控状态
        await RiskRepository.update(account_id, {
            "daily_loss": daily_loss,
            "daily_trades_opened": today_trades,
            "consecutive_losses": consecutive_losses,
            "total_open_stake": total_stake,
        })
    
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
        
        # 检查日亏损
        daily_loss = await TradeRepository.get_today_realized_loss(account_id)
        if daily_loss >= risk_config.max_daily_loss:
            return False, f"Daily loss limit reached: {daily_loss}"
        
        # 检查连续亏损
        consecutive_losses = await TradeRepository.get_consecutive_losses(account_id)
        if consecutive_losses >= risk_config.consecutive_loss_pause:
            return False, f"Consecutive losses: {consecutive_losses}"
        
        # 检查今日开仓数
        today_trades = await TradeRepository.get_today_trades_count(account_id)
        if today_trades >= risk_config.max_daily_trades:
            return False, f"Daily trades limit: {today_trades}"
        
        # 检查方向限制
        if direction == "SHORT":
            short_count = len([
                t for t in await TradeRepository.get_open(account_id)
                if t.get("direction") == "SHORT"
            ])
            if short_count >= risk_config.max_daily_trades_short:
                return False, f"Short trades limit: {short_count}"
        elif direction == "LONG":
            long_count = len([
                t for t in await TradeRepository.get_open(account_id)
                if t.get("direction") == "LONG"
            ])
            if long_count >= risk_config.max_daily_trades_long:
                return False, f"Long trades limit: {long_count}"
        
        # 检查持仓总额
        total_stake = await TradeRepository.get_total_open_stake(account_id)
        if total_stake + stake > risk_config.max_stake:
            return False, f"Total stake would exceed limit: {total_stake + stake}"
        
        # 检查单一标的重复持仓
        open_trades = await TradeRepository.get_open(account_id)
        symbol_trades = [t for t in open_trades if t.get("symbol") == symbol]
        if symbol_trades:
            return False, f"Already have position in {symbol}"
        
        # 检查冷却期
        if risk_config.cooldown_scope == "symbol":
            recent_closed = [
                t for t in await TradeRepository.get_open(account_id)
                if t.get("symbol") == symbol and t.get("status") == "closed"
            ]
            if recent_closed:
                last_close = max(t.get("closed_at", datetime.min) for t in recent_closed)
                if isinstance(last_close, str):
                    from datetime import datetime as dt
                    last_close = dt.fromisoformat(last_close.replace("Z", "+00:00"))
                cooldown_until = last_close + timedelta(hours=risk_config.cooldown_hours)
                if datetime.now(timezone.utc) < cooldown_until:
                    return False, f"Cooldown period for {symbol}"
        
        return True, "OK"
    
    async def record_trade_closed(
        self,
        account_id: str,
        trade_id: str,
        pnl: float,
    ) -> None:
        """记录平仓"""
        # 累加日亏损
        if pnl < 0:
            await RiskRepository.add_daily_loss(account_id, abs(pnl))
        
        # 更新连续亏损
        consecutive_losses = await TradeRepository.get_consecutive_losses(account_id)
        await RiskRepository.update(account_id, {
            "consecutive_losses": consecutive_losses,
        })
        
        # 发布事件
        bus = await get_event_bus()
        await bus.publish(EventType.RISK_STATE_CHANGED, {
            "account_id": account_id,
            "trade_id": trade_id,
            "pnl": pnl,
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
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "running": self._running,
            "monitor_task": self._monitor_task is not None and not self._monitor_task.done(),
            "paused_accounts": list(self._paused_until.keys()),
        }
