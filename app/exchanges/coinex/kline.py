import asyncio

import aiohttp

from app.core.settings import settings
from app.core.logger import setup_logger

logger = setup_logger()

_kline_semaphore: asyncio.Semaphore | None = None


def _semaphore() -> asyncio.Semaphore:
    global _kline_semaphore
    if _kline_semaphore is None:
        _kline_semaphore = asyncio.Semaphore(settings.KLINE_CONCURRENCY)
    return _kline_semaphore


async def fetch_klines(
    market: str,
    period: str = "1hour",
    limit: int = 100,
    session: aiohttp.ClientSession | None = None,
    *,
    start_ms: int | None = None,
    end_ms: int | None = None,
) -> list[dict]:
    """CoinEx spot klines — public endpoint (start_time/end_time in milliseconds)."""
    path = "/v2/spot/kline"
    url = settings.COINEX_BASE_URL + path
    params: dict = {"market": market, "period": period, "limit": limit}
    if start_ms is not None:
        params["start_time"] = start_ms
    if end_ms is not None:
        params["end_time"] = end_ms
    owns_session = session is None
    if owns_session:
        session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20))

    async with _semaphore():
        try:
            async with session.get(url, params=params) as resp:
                data = await resp.json()
            if data.get("code") != 0:
                logger.warning("kline error [%s %s]: %s", market, period, data)
                return []
            rows = data.get("data") or []
            for row in rows:
                ts = int(row.get("created_at", 0))
                if ts > 10_000_000_000_000:
                    ts //= 1000
                elif ts < 10_000_000_000:
                    ts *= 1000
                row["created_at"] = ts
            return sorted(rows, key=lambda x: x.get("created_at", 0))
        except Exception as e:
            logger.error("kline fetch failed [%s %s]: %s", market, period, e)
            return []
        finally:
            if owns_session:
                await session.close()
