import asyncio

from app.engine.scanner import MarketScanner
from app.engine.executor import Executor
from app.engine.portfolio import Portfolio
from app.api.websocket.manager import manager as ws_manager
from app.core.settings import settings
from app.core.logger import setup_logger

logger = setup_logger()


class TradingEngine:
    """Runs scan → signal → risk → execute loop."""

    def __init__(
        self,
        scanner: MarketScanner,
        executor: Executor,
        portfolio: Portfolio,
        symbols: list[str] | None = None,
        interval: int | None = None,
    ):
        self.scanner = scanner
        self.executor = executor
        self.portfolio = portfolio
        self.symbols = symbols or settings.symbol_list
        self.interval = interval or settings.SCAN_INTERVAL_SECONDS
        self._task: asyncio.Task | None = None
        self.running = False
        self.last_scan_at: str | None = None
        self.signals_count = 0
        self.trades_count = 0

    async def run_loop(self):
        self.running = True
        logger.info(f"trading engine started — symbols={self.symbols}")
        while self.running:
            for symbol in self.symbols:
                if not self.running:
                    break
                signal = await self.scanner.process_symbol(symbol)
                if signal:
                    self.signals_count += 1
                    await ws_manager.broadcast({"type": "signal", "data": signal})
                    order = await self.executor.execute(self.portfolio, signal)
                    if order:
                        self.trades_count += 1
                        await ws_manager.broadcast({"type": "order", "data": order})
            from datetime import datetime, timezone

            self.last_scan_at = datetime.now(timezone.utc).isoformat()
            await asyncio.sleep(self.interval)

    def start(self) -> asyncio.Task:
        self._task = asyncio.create_task(self.run_loop())
        return self._task

    async def stop(self):
        self.running = False
        self.scanner.stop()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def status(self) -> dict:
        return {
            "running": self.running,
            "symbols": self.symbols,
            "interval_seconds": self.interval,
            "last_scan_at": self.last_scan_at,
            "signals_count": self.signals_count,
            "trades_count": self.trades_count,
            "open_trades": self.portfolio.open_trades,
            "balance": self.portfolio.balance,
        }
