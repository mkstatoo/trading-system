import asyncio
from app.exchanges.base import BaseExchange
from app.strategies.base import BaseStrategy
from app.core.logger import setup_logger

logger = setup_logger()


class MarketScanner:

    def __init__(self, strategy: BaseStrategy, exchange: BaseExchange):
        self.strategy = strategy
        self.exchange = exchange
        self.running = False

    async def scan_market(self, symbols: list[str]):
        self.running = True
        while self.running:
            tasks = [self.process_symbol(symbol) for symbol in symbols]
            await asyncio.gather(*tasks)
            await asyncio.sleep(5)

    async def process_symbol(self, symbol: str):
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return await self.process_ticker(ticker)
        except Exception as e:
            logger.error(f"scanner error [{symbol}]: {e}")
            return None

    async def process_ticker(self, ticker: dict):
        symbol = ticker.get("market", "")
        try:
            signal = await self.strategy.analyze(ticker)
            if signal:
                logger.info(f"signal generated: {symbol} → {signal}")
            return signal
        except Exception as e:
            logger.error(f"scanner error [{symbol}]: {e}")
            return None

    def stop(self):
        self.running = False
