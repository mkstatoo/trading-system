import aiohttp

from app.core.settings import settings
from app.core.logger import setup_logger

logger = setup_logger()


def normalize_ticker(market: str, raw: dict) -> dict:
    last = raw.get("last") or raw.get("close", "0")
    return {
        "market": raw.get("market", market),
        "last": last,
        "open": raw.get("open", "0"),
        "high": raw.get("high", "0"),
        "low": raw.get("low", "0"),
        "volume": raw.get("volume", "0"),
        "value": raw.get("value", "0"),
    }


async def fetch_all_tickers_public(
    session: aiohttp.ClientSession | None = None,
) -> dict[str, dict]:
    """All spot tickers in one request — used for top-N universe scanning."""
    path = "/v2/spot/ticker"
    url = settings.COINEX_BASE_URL + path
    owns_session = session is None
    if owns_session:
        session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))

    try:
        async with session.get(url) as resp:
            data = await resp.json()
        result: dict[str, dict] = {}
        for item in data.get("data") or []:
            market = item.get("market", "")
            if market:
                result[market] = normalize_ticker(market, item)
        return result
    finally:
        if owns_session:
            await session.close()


async def fetch_ticker_public(
    market: str,
    session: aiohttp.ClientSession | None = None,
) -> dict:
    """Public CoinEx spot ticker — no API key required."""
    path = "/v2/spot/ticker"
    url = settings.COINEX_BASE_URL + path
    params = {"market": market}
    owns_session = session is None
    if owns_session:
        session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))

    try:
        async with session.get(url, params=params) as resp:
            data = await resp.json()
        if data.get("code") not in (0, None) and "data" not in data:
            logger.warning(f"ticker API warning [{market}]: {data}")
        ticker_list = data.get("data") or []
        if ticker_list:
            return normalize_ticker(market, ticker_list[0])
        return normalize_ticker(market, {})
    finally:
        if owns_session:
            await session.close()
