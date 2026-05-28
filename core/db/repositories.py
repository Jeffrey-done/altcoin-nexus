"""
异步 Repository 层
封装所有数据库 CRUD 操作，纯异步实现
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, func, select, update, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .connection import get_db
from .models import (
    CandidateModel,
    ExecutionEventModel,
    RiskStateModel,
    SignalLogModel,
    TradeModel,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _today_str() -> str:
    return _utcnow().strftime("%Y-%m-%d")


class TradeRepository:
    """交易记录 Repository - 异步实现"""

    @staticmethod
    async def create(trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建新交易"""
        db = await get_db()
        async with db.session() as session:
            trade = TradeModel(**trade_data)
            session.add(trade)
            await session.flush()
            await session.refresh(trade)
            return {c.name: getattr(trade, c.name) for c in trade.__table__.columns}

    @staticmethod
    async def get_by_id(trade_id: str) -> Optional[Dict[str, Any]]:
        """按ID获取交易"""
        db = await get_db()
        async with db.session() as session:
            result = await session.execute(
                select(TradeModel).where(TradeModel.id == trade_id)
            )
            trade = result.scalar_one_or_none()
            if trade:
                return {c.name: getattr(trade, c.name) for c in trade.__table__.columns}
            return None

    @staticmethod
    async def get_open(
        account_id: Optional[str] = None,
        exchange: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取所有未平仓交易"""
        db = await get_db()
        async with db.session() as session:
            query = select(TradeModel).where(TradeModel.status == "open")
            if account_id:
                query = query.where(TradeModel.account_id == account_id)
            if exchange:
                query = query.where(TradeModel.exchange == exchange)
            
            result = await session.execute(query)
            trades = result.scalars().all()
            return [{c.name: getattr(t, c.name) for c in t.__table__.columns} for t in trades]

    @staticmethod
    async def get_closed(
        account_id: Optional[str] = None,
        exchange: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """获取已平仓交易"""
        db = await get_db()
        async with db.session() as session:
            query = select(TradeModel).where(TradeModel.status == "closed").order_by(desc(TradeModel.closed_at))
            if account_id:
                query = query.where(TradeModel.account_id == account_id)
            if exchange:
                query = query.where(TradeModel.exchange == exchange)
            if limit > 0:
                query = query.limit(limit)
            
            result = await session.execute(query)
            trades = result.scalars().all()
            return [{c.name: getattr(t, c.name) for c in t.__table__.columns} for t in trades]

    @staticmethod
    async def get_open_symbols(account_id: Optional[str] = None) -> set:
        """获取当前持仓的symbol集合"""
        db = await get_db()
        async with db.session() as session:
            query = select(TradeModel.symbol).where(TradeModel.status == "open")
            if account_id:
                query = query.where(TradeModel.account_id == account_id)
            
            result = await session.execute(query)
            return {row[0] for row in result.all()}

    @staticmethod
    async def update(trade_id: str, updates: Dict[str, Any]) -> bool:
        """更新交易字段"""
        db = await get_db()
        async with db.session() as session:
            updates["updated_at"] = _utcnow()
            await session.execute(
                update(TradeModel)
                .where(TradeModel.id == trade_id)
                .values(**updates)
            )
            return True

    @staticmethod
    async def update_with_lock(trade_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        带行级锁的更新 - 防止并发冲突
        
        使用 SELECT ... FOR UPDATE 锁定行，确保读-改-写的原子性
        """
        db = await get_db()
        async with db.session() as session:
            async with session.begin():
                # 使用行级锁
                result = await session.execute(
                    select(TradeModel)
                    .where(TradeModel.id == trade_id)
                    .with_for_update()
                )
                trade = result.scalar_one_or_none()
                
                if not trade:
                    return None
                
                # 应用更新
                for key, value in updates.items():
                    if hasattr(trade, key):
                        setattr(trade, key, value)
                trade.updated_at = _utcnow()
                
                await session.flush()
                return {c.name: getattr(trade, c.name) for c in trade.__table__.columns}

    @staticmethod
    async def close_trade(
        trade_id: str,
        pnl: float,
        close_price: float,
        close_reason: str,
        close_type: str,
        close_order_id: Optional[str] = None,
        exit_ref_price: float = 0.0,
        exit_slippage_pct: float = 0.0,
    ) -> bool:
        """
        平仓 - 使用行级锁防止并发冲突
        """
        db = await get_db()
        async with db.session() as session:
            async with session.begin():
                # 使用行级锁
                result = await session.execute(
                    select(TradeModel)
                    .where(TradeModel.id == trade_id)
                    .where(TradeModel.status == "open")  # 只处理未平仓的
                    .with_for_update()
                )
                trade = result.scalar_one_or_none()
                
                if not trade:
                    return False
                
                # 更新状态
                trade.status = "closed"
                trade.pnl = pnl
                trade.current_price = close_price
                trade.close_reason = close_reason
                trade.close_type = close_type
                trade.close_order_id = close_order_id
                trade.exit_ref_price = exit_ref_price
                trade.exit_slippage_pct = exit_slippage_pct
                trade.closed_at = _utcnow()
                trade.updated_at = _utcnow()
                
                await session.flush()
                return True

    @staticmethod
    async def trigger_tp1_with_lock(
        trade_id: str,
        tp1_price: float,
        tp1_close_order_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        触发止盈1 - 使用行级锁
        
        返回更新后的交易数据，如果已经触发过则返回 None
        """
        db = await get_db()
        async with db.session() as session:
            async with session.begin():
                # 使用行级锁
                result = await session.execute(
                    select(TradeModel)
                    .where(TradeModel.id == trade_id)
                    .where(TradeModel.status == "open")
                    .where(TradeModel.tp1_triggered == False)  # 只处理未触发的
                    .with_for_update()
                )
                trade = result.scalar_one_or_none()
                
                if not trade:
                    return None
                
                # 计算止盈
                close_ratio = 0.5  # 平仓比例
                closed_shares = trade.shares * close_ratio
                locked_pnl = closed_shares * (tp1_price - trade.entry_price)
                
                if trade.direction == "SHORT":
                    locked_pnl = -locked_pnl  # 做空盈亏相反
                
                # 更新状态
                trade.tp1_triggered = True
                trade.tp1_locked_pnl = locked_pnl
                trade.tp1_close_order_id = tp1_close_order_id
                trade.stake_remaining = trade.stake * (1 - close_ratio)
                trade.updated_at = _utcnow()
                
                await session.flush()
                return {c.name: getattr(trade, c.name) for c in trade.__table__.columns}

    @staticmethod
    async def get_total_open_stake(account_id: Optional[str] = None) -> float:
        """计算持仓总保证金"""
        db = await get_db()
        async with db.session() as session:
            query = select(func.coalesce(func.sum(TradeModel.stake_remaining), 0.0)).where(
                TradeModel.status == "open"
            )
            if account_id:
                query = query.where(TradeModel.account_id == account_id)
            
            result = await session.execute(query)
            return float(result.scalar() or 0.0)

    @staticmethod
    async def get_today_trades_count(account_id: Optional[str] = None) -> int:
        """今日开仓数"""
        today_start = _utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        db = await get_db()
        async with db.session() as session:
            query = select(func.count(TradeModel.id)).where(
                TradeModel.opened_at >= today_start
            )
            if account_id:
                query = query.where(TradeModel.account_id == account_id)
            
            result = await session.execute(query)
            return int(result.scalar() or 0)

    @staticmethod
    async def get_today_realized_loss(account_id: Optional[str] = None) -> float:
        """今日已实现亏损"""
        today_start = _utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        db = await get_db()
        async with db.session() as session:
            query = select(TradeModel).where(
                and_(
                    TradeModel.status == "closed",
                    TradeModel.closed_at >= today_start,
                )
            )
            if account_id:
                query = query.where(TradeModel.account_id == account_id)
            
            result = await session.execute(query)
            trades = result.scalars().all()
            
            total_loss = 0.0
            for t in trades:
                realized = (t.tp1_locked_pnl or 0) + (t.pnl or 0)
                if realized < 0:
                    total_loss += abs(realized)
            return round(total_loss, 2)

    @staticmethod
    async def get_consecutive_losses(account_id: Optional[str] = None) -> int:
        """获取当前连续亏损次数"""
        db = await get_db()
        async with db.session() as session:
            query = select(TradeModel).where(TradeModel.status == "closed")
            if account_id:
                query = query.where(TradeModel.account_id == account_id)
            query = query.order_by(desc(TradeModel.closed_at)).limit(50)
            
            result = await session.execute(query)
            trades = result.scalars().all()
            
            cnt = 0
            for t in trades:
                realized = (t.tp1_locked_pnl or 0) + (t.pnl or 0)
                if realized < 0:
                    cnt += 1
                elif realized > 0:
                    break
            return cnt


class CandidateRepository:
    """候选池 Repository - 异步实现"""

    @staticmethod
    async def upsert(candidate_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建或更新候选 - 使用原子 upsert 防止竞态条件
        """
        db = await get_db()
        async with db.session() as session:
            candidate_data = dict(candidate_data)
            candidate_data.setdefault("strategy", "short_overbought")
            candidate_data.setdefault("direction", "SHORT")

            if "metadata" in candidate_data and isinstance(candidate_data["metadata"], dict):
                candidate_data["metadata_json"] = json.dumps(
                    candidate_data["metadata"], ensure_ascii=False
                )
                del candidate_data["metadata"]

            model_fields = {c.name for c in CandidateModel.__table__.columns}
            insert_data = {k: v for k, v in candidate_data.items() if k in model_fields and k != "id"}

            now = _utcnow()
            insert_data.setdefault("created_at", now)
            insert_data["updated_at"] = now

            update_data = {
                k: v for k, v in insert_data.items()
                if k not in ("id", "created_at", "symbol", "strategy")
            }
            update_data["updated_at"] = now

            stmt = pg_insert(CandidateModel).values(**insert_data)
            stmt = stmt.on_conflict_do_update(
                index_elements=["symbol", "strategy"],
                set_=update_data,
            ).returning(CandidateModel)

            result = await session.execute(stmt)
            row = result.scalar_one()
            return {c.name: getattr(row, c.name) for c in row.__table__.columns}

    @staticmethod
    async def get_active(
        exclude_triggered: bool = True,
        strategy: Optional[str] = None,
        direction: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取活跃候选"""
        db = await get_db()
        async with db.session() as session:
            query = select(CandidateModel)
            if exclude_triggered:
                query = query.where(CandidateModel.triggered == False)
            if strategy:
                query = query.where(CandidateModel.strategy == strategy)
            if direction:
                query = query.where(CandidateModel.direction == direction)
            
            now = _utcnow()
            query = query.where(
                (CandidateModel.expires_at == None) | (CandidateModel.expires_at > now)
            )
            
            result = await session.execute(query.order_by(CandidateModel.added_at))
            candidates = result.scalars().all()
            return [{col.name: getattr(c, col.name) for col in c.__table__.columns} for c in candidates]

    @staticmethod
    async def mark_triggered(
        symbol: str,
        trigger_type: str,
        trigger_reason: str,
        strategy: str = "short_overbought",
    ) -> bool:
        """标记候选已触发"""
        db = await get_db()
        async with db.session() as session:
            await session.execute(
                update(CandidateModel)
                .where(
                    and_(
                        CandidateModel.symbol == symbol,
                        CandidateModel.strategy == strategy,
                    )
                )
                .values(
                    triggered=True,
                    trigger_type=trigger_type,
                    trigger_reason=trigger_reason,
                    updated_at=_utcnow(),
                )
            )
            return True

    @staticmethod
    async def remove_expired(expire_hours: int = 12) -> int:
        """清理过期候选"""
        cutoff = _utcnow() - timedelta(hours=expire_hours)
        db = await get_db()
        async with db.session() as session:
            result = await session.execute(
                delete(CandidateModel).where(
                    (CandidateModel.triggered == True) | (CandidateModel.added_at < cutoff)
                )
            )
            return result.rowcount


class RiskRepository:
    """风控状态 Repository - 异步实现"""

    @staticmethod
    async def get_or_create(account_id: str) -> Dict[str, Any]:
        """获取今日风控状态"""
        today = _today_str()
        db = await get_db()
        async with db.session() as session:
            stmt = pg_insert(RiskStateModel).values(account_id=account_id, date=today)
            stmt = stmt.on_conflict_do_nothing(index_elements=["account_id", "date"])
            await session.execute(stmt)

            result = await session.execute(
                select(RiskStateModel)
                .where(
                    and_(
                        RiskStateModel.account_id == account_id,
                        RiskStateModel.date == today,
                    )
                )
                .with_for_update()
            )
            state = result.scalar_one()
            return {c.name: getattr(state, c.name) for c in state.__table__.columns}

    @staticmethod
    async def update(account_id: str, updates: Dict[str, Any]) -> bool:
        """更新风控状态"""
        today = _today_str()
        db = await get_db()
        async with db.session() as session:
            updates["updated_at"] = _utcnow()
            await session.execute(
                update(RiskStateModel)
                .where(
                    and_(
                        RiskStateModel.account_id == account_id,
                        RiskStateModel.date == today,
                    )
                )
                .values(**updates)
            )
            return True

    @staticmethod
    async def update_with_lock(account_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        带行级锁的更新 - 防止并发冲突
        """
        today = _today_str()
        db = await get_db()
        async with db.session() as session:
            async with session.begin():
                # 使用行级锁
                result = await session.execute(
                    select(RiskStateModel)
                    .where(
                        and_(
                            RiskStateModel.account_id == account_id,
                            RiskStateModel.date == today,
                        )
                    )
                    .with_for_update()
                )
                state = result.scalar_one_or_none()
                
                if not state:
                    # 不存在则创建
                    state = RiskStateModel(account_id=account_id, date=today)
                    session.add(state)
                    await session.flush()
                
                # 应用更新
                for key, value in updates.items():
                    if hasattr(state, key):
                        setattr(state, key, value)
                state.updated_at = _utcnow()
                
                await session.flush()
                return {c.name: getattr(state, c.name) for c in state.__table__.columns}

    @staticmethod
    async def increment_daily_trades(account_id: str) -> int:
        """递增今日开仓次数"""
        today = _today_str()
        db = await get_db()
        async with db.session() as session:
            # 使用行级锁
            result = await session.execute(
                select(RiskStateModel)
                .where(
                    and_(
                        RiskStateModel.account_id == account_id,
                        RiskStateModel.date == today,
                    )
                )
                .with_for_update()
            )
            state = result.scalar_one_or_none()
            
            if not state:
                state = RiskStateModel(account_id=account_id, date=today)
                session.add(state)
                await session.flush()
            
            state.daily_trades_opened += 1
            state.updated_at = _utcnow()
            return state.daily_trades_opened

    @staticmethod
    async def add_daily_loss(account_id: str, loss: float) -> float:
        """累加今日亏损"""
        today = _today_str()
        db = await get_db()
        async with db.session() as session:
            # 使用行级锁
            result = await session.execute(
                select(RiskStateModel)
                .where(
                    and_(
                        RiskStateModel.account_id == account_id,
                        RiskStateModel.date == today,
                    )
                )
                .with_for_update()
            )
            state = result.scalar_one_or_none()
            
            if not state:
                state = RiskStateModel(account_id=account_id, date=today)
                session.add(state)
                await session.flush()
            
            state.daily_loss += abs(loss)
            state.updated_at = _utcnow()
            return state.daily_loss


class EventRepository:
    """执行事件 Repository - 异步实现"""

    @staticmethod
    async def log(event_type: str, **kwargs: Any) -> int:
        """记录执行事件"""
        db = await get_db()
        async with db.session() as session:
            known_fields = {
                "exchange", "symbol", "direction", "account_id",
                "client_order_id", "order_id", "stake", "leverage",
                "fill_price", "fill_amount", "error", "error_code",
            }
            model_data = {"event_type": event_type}
            extra = {}

            for key, value in kwargs.items():
                if key in known_fields:
                    model_data[key] = value
                else:
                    extra[key] = value

            if extra:
                model_data["extra_data"] = json.dumps(extra, ensure_ascii=False)

            event = ExecutionEventModel(**model_data)
            session.add(event)
            await session.flush()
            return event.id

    @staticmethod
    async def get_recent(
        event_type: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """查询最近的执行事件"""
        db = await get_db()
        async with db.session() as session:
            query = select(ExecutionEventModel)
            if event_type:
                query = query.where(ExecutionEventModel.event_type == event_type)
            if symbol:
                query = query.where(ExecutionEventModel.symbol == symbol)
            query = query.order_by(desc(ExecutionEventModel.timestamp)).limit(limit)
            
            result = await session.execute(query)
            events = result.scalars().all()
            return [{c.name: getattr(e, c.name) for c in e.__table__.columns} for e in events]


class SignalLogRepository:
    """信号评分日志 Repository - 异步实现"""

    @staticmethod
    async def log(signal_data: Dict[str, Any]) -> int:
        """记录信号评分"""
        db = await get_db()
        async with db.session() as session:
            entry = SignalLogModel(**signal_data)
            session.add(entry)
            await session.flush()
            return entry.id

    @staticmethod
    async def get_recent(
        symbol: Optional[str] = None,
        strategy: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """查询最近的信号"""
        db = await get_db()
        async with db.session() as session:
            query = select(SignalLogModel)
            if symbol:
                query = query.where(SignalLogModel.symbol == symbol)
            if strategy:
                query = query.where(SignalLogModel.strategy == strategy)
            query = query.order_by(desc(SignalLogModel.timestamp)).limit(limit)
            
            result = await session.execute(query)
            logs = result.scalars().all()
            return [{c.name: getattr(s, c.name) for c in s.__table__.columns} for s in logs]

    @staticmethod
    async def get_trigger_rate(strategy: str, days: int = 30) -> Dict[str, Any]:
        """统计信号触发率"""
        since = _utcnow() - timedelta(days=days)
        db = await get_db()
        async with db.session() as session:
            # 总信号数
            total_result = await session.execute(
                select(func.count(SignalLogModel.id)).where(
                    and_(
                        SignalLogModel.strategy == strategy,
                        SignalLogModel.timestamp >= since,
                    )
                )
            )
            total = total_result.scalar() or 0
            
            # 触发数
            triggered_result = await session.execute(
                select(func.count(SignalLogModel.id)).where(
                    and_(
                        SignalLogModel.strategy == strategy,
                        SignalLogModel.timestamp >= since,
                        SignalLogModel.triggered_open == True,
                    )
                )
            )
            triggered = triggered_result.scalar() or 0
            
            return {
                "total_signals": total,
                "triggered": triggered,
                "trigger_rate": round(triggered / max(total, 1) * 100, 1),
            }


class SystemStateRepository:
    """系统状态 Repository - 用于持久化黑名单等运行时状态"""

    @staticmethod
    async def get(key: str) -> Optional[str]:
        """获取系统状态值"""
        from .models import SystemStateModel
        db = await get_db()
        async with db.session() as session:
            result = await session.execute(
                select(SystemStateModel).where(SystemStateModel.key == key)
            )
            state = result.scalar_one_or_none()
            return state.value if state else None

    @staticmethod
    async def set(key: str, value: str) -> None:
        """设置系统状态值"""
        from .models import SystemStateModel
        db = await get_db()
        async with db.session() as session:
            result = await session.execute(
                select(SystemStateModel).where(SystemStateModel.key == key)
            )
            state = result.scalar_one_or_none()
            
            if state:
                state.value = value
                state.updated_at = _utcnow()
            else:
                state = SystemStateModel(key=key, value=value)
                session.add(state)
            
            await session.flush()

    @staticmethod
    async def delete(key: str) -> bool:
        """删除系统状态"""
        from .models import SystemStateModel
        db = await get_db()
        async with db.session() as session:
            result = await session.execute(
                delete(SystemStateModel).where(SystemStateModel.key == key)
            )
            return result.rowcount > 0

    @staticmethod
    async def get_all() -> Dict[str, str]:
        """获取所有系统状态"""
        from .models import SystemStateModel
        db = await get_db()
        async with db.session() as session:
            result = await session.execute(select(SystemStateModel))
            states = result.scalars().all()
            return {s.key: s.value for s in states}



class ExchangeAccountRepository:
    """
    交易所账户 Repository - 多账户CRUD
    
    支持同一交易所配置多个独立API Key
    """

    @staticmethod
    async def create(account_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建新账户"""
        from .models import ExchangeAccountModel
        db = await get_db()
        async with db.session() as session:
            account = ExchangeAccountModel(**account_data)
            session.add(account)
            await session.flush()
            await session.refresh(account)
            return {c.name: getattr(account, c.name) for c in account.__table__.columns}

    @staticmethod
    async def get_by_id(account_id: str) -> Optional[Dict[str, Any]]:
        """按 account_id 获取账户"""
        from .models import ExchangeAccountModel
        db = await get_db()
        async with db.session() as session:
            result = await session.execute(
                select(ExchangeAccountModel).where(
                    ExchangeAccountModel.account_id == account_id
                )
            )
            account = result.scalar_one_or_none()
            if account:
                return {c.name: getattr(account, c.name) for c in account.__table__.columns}
            return None

    @staticmethod
    async def get_all(
        exchange: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """获取所有账户（可按交易所/状态过滤）"""
        from .models import ExchangeAccountModel
        db = await get_db()
        async with db.session() as session:
            query = select(ExchangeAccountModel)
            if exchange:
                query = query.where(ExchangeAccountModel.exchange == exchange)
            if is_active is not None:
                query = query.where(ExchangeAccountModel.is_active == is_active)
            query = query.order_by(ExchangeAccountModel.exchange, ExchangeAccountModel.created_at)
            result = await session.execute(query)
            accounts = result.scalars().all()
            return [{c.name: getattr(a, c.name) for c in a.__table__.columns} for a in accounts]

    @staticmethod
    async def update(account_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新账户信息"""
        from .models import ExchangeAccountModel
        db = await get_db()
        async with db.session() as session:
            result = await session.execute(
                select(ExchangeAccountModel).where(
                    ExchangeAccountModel.account_id == account_id
                )
            )
            account = result.scalar_one_or_none()
            if not account:
                return None
            for key, value in updates.items():
                if hasattr(account, key) and key not in ("id", "account_id", "created_at"):
                    setattr(account, key, value)
            account.updated_at = datetime.now(timezone.utc)
            await session.flush()
            return {c.name: getattr(account, c.name) for c in account.__table__.columns}

    @staticmethod
    async def delete(account_id: str) -> bool:
        """删除账户"""
        from .models import ExchangeAccountModel
        db = await get_db()
        async with db.session() as session:
            result = await session.execute(
                delete(ExchangeAccountModel).where(
                    ExchangeAccountModel.account_id == account_id
                )
            )
            return result.rowcount > 0

    @staticmethod
    async def get_primary(exchange: str) -> Optional[Dict[str, Any]]:
        """获取指定交易所的主账户"""
        from .models import ExchangeAccountModel
        db = await get_db()
        async with db.session() as session:
            result = await session.execute(
                select(ExchangeAccountModel).where(
                    and_(
                        ExchangeAccountModel.exchange == exchange,
                        ExchangeAccountModel.is_primary == True,
                        ExchangeAccountModel.is_active == True,
                    )
                )
            )
            account = result.scalar_one_or_none()
            if account:
                return {c.name: getattr(account, c.name) for c in account.__table__.columns}
            # 如果没有主账户，返回该交易所第一个活跃账户
            result = await session.execute(
                select(ExchangeAccountModel).where(
                    and_(
                        ExchangeAccountModel.exchange == exchange,
                        ExchangeAccountModel.is_active == True,
                    )
                ).limit(1)
            )
            account = result.scalar_one_or_none()
            if account:
                return {c.name: getattr(account, c.name) for c in account.__table__.columns}
            return None

    @staticmethod
    async def set_primary(account_id: str) -> bool:
        """将指定账户设为主账户（同时取消同交易所其他主账户）"""
        from .models import ExchangeAccountModel
        db = await get_db()
        async with db.session() as session:
            # 先获取该账户的交易所
            result = await session.execute(
                select(ExchangeAccountModel).where(
                    ExchangeAccountModel.account_id == account_id
                )
            )
            account = result.scalar_one_or_none()
            if not account:
                return False
            exchange = account.exchange
            # 取消该交易所所有主账户标记
            await session.execute(
                update(ExchangeAccountModel)
                .where(ExchangeAccountModel.exchange == exchange)
                .values(is_primary=False)
            )
            # 设置新的主账户
            account.is_primary = True
            account.updated_at = datetime.now(timezone.utc)
            await session.flush()
            return True

    @staticmethod
    async def get_active_by_exchange() -> Dict[str, List[Dict[str, Any]]]:
        """按交易所分组获取所有活跃账户"""
        from .models import ExchangeAccountModel
        db = await get_db()
        async with db.session() as session:
            result = await session.execute(
                select(ExchangeAccountModel)
                .where(ExchangeAccountModel.is_active == True)
                .order_by(ExchangeAccountModel.exchange, ExchangeAccountModel.is_primary.desc())
            )
            accounts = result.scalars().all()
            grouped: Dict[str, List[Dict[str, Any]]] = {}
            for a in accounts:
                ex = a.exchange
                if ex not in grouped:
                    grouped[ex] = []
                grouped[ex].append(
                    {c.name: getattr(a, c.name) for c in a.__table__.columns}
                )
            return grouped
