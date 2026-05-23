import asyncio
from datetime import datetime, timezone

from app.engine.scanner import MarketScanner
from app.engine.executor import Executor
from app.engine.portfolio import Portfolio
from app.exchanges.coinex.symbol_universe import TopMarketsUniverse
from app.exchanges.coinex.market_data import fetch_all_tickers_public
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
        universe: TopMarketsUniverse | None = None,
        symbols: list[str] | None = None,
        interval: int | None = None,
    ):
        self.scanner = scanner
        self.executor = executor
        self.portfolio = portfolio
        self.universe = universe
        self.symbols = symbols or settings.symbol_list
        self.interval = interval or settings.SCAN_INTERVAL_SECONDS
        self._task: asyncio.Task | None = None
        self.running = False
        self.last_scan_at: str | None = None
        self.signals_count = 0
        self.trades_count = 0
        self.scanned_count = 0
        self.symbol_mode = "top300" if settings.use_top_markets else "manual"

    async def run_loop(self):
        self.running = True
        mode = self.symbol_mode
        logger.info(
            "trading engine started — mode=%s count=%s",
            mode,
            settings.TOP_MARKETS_COUNT if settings.use_top_markets else len(self.symbols),
        )
        while self.running:
            try:
                all_tickers = await fetch_all_tickers_public()

                if settings.use_top_markets and self.universe:
                    self.symbols = await self.universe.get_symbols(all_tickers)
                elif not self.symbols:
                    logger.warning("no symbols configured for manual mode")
                    await asyncio.sleep(self.interval)
                    continue

                self.scanned_count = 0
                for symbol in self.symbols:
                    if not self.running:
                        break
                    ticker = all_tickers.get(symbol)
                    if not ticker:
                        continue
                    self.scanned_count += 1
                    signal = await self.scanner.process_ticker(ticker)
                    if signal:
                        self.signals_count += 1
                        await ws_manager.broadcast({"type": "signal", "data": signal})
                        order = await self.executor.execute(self.portfolio, signal)
                        if order:
                            self.trades_count += 1
                            await ws_manager.broadcast({"type": "order", "data": order})

                self.last_scan_at = datetime.now(timezone.utc).isoformat()
            except Exception as e:
                logger.error(f"trading loop error: {e}")

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
            "symbol_mode": self.symbol_mode,
            "symbols_count": len(self.symbols),
            "symbols_preview": self.symbols[:12],
            "scanned_last_cycle": self.scanned_count,
            "interval_seconds": self.interval,
            "last_scan_at": self.last_scan_at,
            "signals_count": self.signals_count,
            "trades_count": self.trades_count,
            "open_trades": self.portfolio.open_trades,
            "balance": self.portfolio.balance,
        }
