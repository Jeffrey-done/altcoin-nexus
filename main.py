"""
Altcoin Nexus - L4 Autonomous Quantitative Trading System
Main entry point
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.config import get_settings
from core.db import get_db, close_db
from core.events import get_event_bus, close_event_bus
from services.datafeed import DataFeedService
from services.strategy import StrategyEngine
from services.execution import ExecutionRouter
from services.risk import RiskControlService
from services.monitor import MonitoringService
from services.optimization import OptimizationService
from services.trade_manager import TradeManagerService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("nexus")


class NexusSystem:
    """Nexus system main class"""
    
    def __init__(self):
        self.settings = get_settings()
        self._running = False
        
        self.datafeed: DataFeedService = None
        self.strategy_engine: StrategyEngine = None
        self.execution_router: ExecutionRouter = None
        self.risk_control: RiskControlService = None
        self.trade_manager: TradeManagerService = None
        self.monitoring: MonitoringService = None
        self.optimization: OptimizationService = None
    
    async def start(self) -> None:
        logger.info(f"Starting Altcoin Nexus v{self.settings.version}")
        logger.info(f"Environment: {self.settings.environment}")
        
        self._running = True
        
        # Database
        db = await get_db()
        await db.create_all()
        logger.info("Database initialized")
        
        # Event bus
        bus = await get_event_bus()
        logger.info("Event bus initialized")
        
        # Services - order matters for dependencies
        self.datafeed = DataFeedService()
        await self.datafeed.start()
        
        self.execution_router = ExecutionRouter()
        await self.execution_router.start()
        
        self.risk_control = RiskControlService()
        await self.risk_control.start()
        
        # Trade Manager - THE critical missing piece
        self.trade_manager = TradeManagerService(self.execution_router, self.datafeed)
        await self.trade_manager.start()
        
        self.strategy_engine = StrategyEngine(self.datafeed)
        await self.strategy_engine.start()
        
        self.monitoring = MonitoringService(self.datafeed)
        await self.monitoring.start()
        
        self.optimization = OptimizationService()
        await self.optimization.start()
        
        logger.info("All services started")
        logger.info("Pipeline: Market Scan -> Strategy Filter -> Signal -> TradeManager -> Execute -> TP/SL")
        
        self._register_signal_handlers()
        
        await bus.publish("system.startup", {
            "version": self.settings.version,
            "environment": self.settings.environment,
        })
    
    async def stop(self) -> None:
        logger.info("Stopping Altcoin Nexus...")
        self._running = False
        
        # Stop in reverse dependency order
        for service in (self.optimization, self.monitoring, self.strategy_engine,
                       self.trade_manager, self.risk_control, self.execution_router, self.datafeed):
            if service:
                try:
                    await service.stop()
                except Exception as e:
                    logger.error(f"Error stopping service: {e}")
        
        await close_event_bus()
        await close_db()
        logger.info("Altcoin Nexus stopped")
    
    def _register_signal_handlers(self) -> None:
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
            except NotImplementedError:
                pass
    
    async def run(self) -> None:
        await self.start()
        try:
            while self._running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            await self.stop()
    
    async def get_status(self) -> dict:
        return {
            "version": self.settings.version,
            "environment": self.settings.environment,
            "running": self._running,
            "services": {
                "datafeed": await self.datafeed.health_check() if self.datafeed else None,
                "strategy": await self.strategy_engine.health_check() if self.strategy_engine else None,
                "execution": await self.execution_router.health_check() if self.execution_router else None,
                "risk": await self.risk_control.health_check() if self.risk_control else None,
                "trade_manager": await self.trade_manager.health_check() if self.trade_manager else None,
                "monitoring": await self.monitoring.health_check() if self.monitoring else None,
                "optimization": await self.optimization.health_check() if self.optimization else None,
            },
        }


async def main():
    system = NexusSystem()
    await system.run()


if __name__ == "__main__":
    asyncio.run(main())
