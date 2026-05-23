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
) -> list[dict]:
    """CoinEx spot klines — public endpoint."""
    path = "/v2/spot/kline"
    url = settings.COINEX_BASE_URL + path
    params = {"market": market, "period": period, "limit": limit}
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
            return sorted(rows, key=lambda x: x.get("created_at", 0))
        except Exception as e:
            logger.error("kline fetch failed [%s %s]: %s", market, period, e)
            return []
        finally:
            if owns_session:
                await session.close()
