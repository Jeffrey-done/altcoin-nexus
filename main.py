"""
Altcoin Nexus - L4级自治量化交易系统
主启动脚本
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
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

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("nexus")


class NexusSystem:
    """Nexus 系统主类"""
    
    def __init__(self):
        self.settings = get_settings()
        self._running = False
        
        # 服务实例
        self.datafeed: DataFeedService = None
        self.strategy_engine: StrategyEngine = None
        self.execution_router: ExecutionRouter = None
        self.risk_control: RiskControlService = None
        self.monitoring: MonitoringService = None
        self.optimization: OptimizationService = None
    
    async def start(self) -> None:
        """启动系统"""
        logger.info(f"Starting Altcoin Nexus v{self.settings.version}")
        logger.info(f"Environment: {self.settings.environment}")
        
        self._running = True
        
        # 初始化数据库
        db = await get_db()
        await db.create_all()
        logger.info("Database initialized")
        
        # 初始化事件总线
        bus = await get_event_bus()
        logger.info("Event bus initialized")
        
        # 初始化服务
        self.datafeed = DataFeedService()
        await self.datafeed.start()
        
        self.execution_router = ExecutionRouter()
        await self.execution_router.start()
        
        self.risk_control = RiskControlService()
        await self.risk_control.start()
        
        self.strategy_engine = StrategyEngine(self.datafeed)
        await self.strategy_engine.start()
        
        self.monitoring = MonitoringService(self.datafeed)
        await self.monitoring.start()
        
        self.optimization = OptimizationService()
        await self.optimization.start()
        
        logger.info("All services started")
        
        # 注册信号处理
        self._register_signal_handlers()
        
        # 发布系统启动事件
        await bus.publish("system.startup", {
            "version": self.settings.version,
            "environment": self.settings.environment,
        })
    
    async def stop(self) -> None:
        """停止系统"""
        logger.info("Stopping Altcoin Nexus...")
        
        self._running = False
        
        # 停止服务
        if self.optimization:
            await self.optimization.stop()
        
        if self.monitoring:
            await self.monitoring.stop()
        
        if self.strategy_engine:
            await self.strategy_engine.stop()
        
        if self.risk_control:
            await self.risk_control.stop()
        
        if self.execution_router:
            await self.execution_router.stop()
        
        if self.datafeed:
            await self.datafeed.stop()
        
        # 关闭事件总线
        await close_event_bus()
        
        # 关闭数据库
        await close_db()
        
        logger.info("Altcoin Nexus stopped")
    
    def _register_signal_handlers(self) -> None:
        """注册信号处理"""
        loop = asyncio.get_event_loop()
        
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
            except NotImplementedError:
                # Windows 不支持 add_signal_handler
                pass
    
    async def run(self) -> None:
        """运行系统"""
        await self.start()
        
        try:
            # 保持运行
            while self._running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            await self.stop()
    
    async def get_status(self) -> dict:
        """获取系统状态"""
        return {
            "version": self.settings.version,
            "environment": self.settings.environment,
            "running": self._running,
            "services": {
                "datafeed": await self.datafeed.health_check() if self.datafeed else None,
                "strategy": await self.strategy_engine.health_check() if self.strategy_engine else None,
                "execution": await self.execution_router.health_check() if self.execution_router else None,
                "risk": await self.risk_control.health_check() if self.risk_control else None,
                "monitoring": await self.monitoring.health_check() if self.monitoring else None,
                "optimization": await self.optimization.health_check() if self.optimization else None,
            },
        }


async def main():
    """主函数"""
    system = NexusSystem()
    await system.run()


if __name__ == "__main__":
    asyncio.run(main())
