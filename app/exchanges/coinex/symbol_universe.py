import time

from app.core.settings import settings
from app.core.logger import setup_logger
from app.exchanges.coinex.market_data import fetch_all_tickers_public

logger = setup_logger()


class TopMarketsUniverse:
    """Top N USDT spot markets on CoinEx ranked by 24h quote volume (value)."""

    def __init__(self, limit: int | None = None):
        self.limit = limit or settings.TOP_MARKETS_COUNT
        self._symbols: list[str] = []
        self._updated_at: float = 0.0

    @property
    def ttl_seconds(self) -> int:
        return settings.TOP_MARKETS_REFRESH_HOURS * 3600

    def needs_refresh(self) -> bool:
        if not self._symbols:
            return True
        return (time.time() - self._updated_at) >= self.ttl_seconds

    def rank_from_tickers(self, tickers: dict[str, dict]) -> list[str]:
        ranked: list[tuple[str, float]] = []
        for market, ticker in tickers.items():
            if not market.endswith("USDT"):
                continue
            try:
                volume_usdt = float(ticker.get("value", 0) or 0)
            except (TypeError, ValueError):
                volume_usdt = 0.0
            if volume_usdt > 0:
                ranked.append((market, volume_usdt))
        ranked.sort(key=lambda x: x[1], reverse=True)
        return [market for market, _ in ranked[: self.limit]]

    async def refresh(self, tickers: dict[str, dict] | None = None) -> list[str]:
        if tickers is None:
            tickers = await fetch_all_tickers_public()
        self._symbols = self.rank_from_tickers(tickers)
        self._updated_at = time.time()
        logger.info(
            "top markets refreshed — count=%s top=%s",
            len(self._symbols),
            self._symbols[:5],
        )
        return self._symbols

    async def get_symbols(self, tickers: dict[str, dict] | None = None) -> list[str]:
        if self.needs_refresh():
            await self.refresh(tickers)
        return self._symbols
