import json
import aiohttp

from app.exchanges.base import BaseExchange
from app.exchanges.coinex.auth import CoinExAuth
from app.exchanges.coinex.market_data import fetch_ticker_public
from app.core.settings import settings
from app.core.logger import setup_logger

logger = setup_logger()


class CoinExClient(BaseExchange):

    def __init__(self):
        self.auth = CoinExAuth(
            settings.COINEX_ACCESS_ID,
            settings.COINEX_SECRET_KEY,
        )
        self.base_url = settings.COINEX_BASE_URL
        self._session: aiohttp.ClientSession | None = None

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_balance(self) -> dict:
        path = "/v2/assets/spot/balance"
        headers = self.auth.headers("GET", path)
        async with self.session.get(self.base_url + path, headers=headers) as resp:
            return await resp.json()

    async def fetch_ticker(self, market: str) -> dict:
        return await fetch_ticker_public(market, session=self.session)

    async def place_order(self, market: str, side: str, amount: float, price: float) -> dict:
        path = "/v2/spot/order"
        body = {
            "market": market,
            "market_type": "SPOT",
            "side": side,
            "type": "limit",
            "amount": str(amount),
            "price": str(price),
        }
        body_json = json.dumps(body, separators=(",", ":"))
        headers = self.auth.headers("POST", path, body_json)
        async with self.session.post(
            self.base_url + path, data=body_json, headers=headers
        ) as resp:
            return await resp.json()

    async def cancel_order(self, order_id: str) -> dict:
        path = "/v2/spot/cancel-order"
        body = {"order_id": int(order_id)}
        body_json = json.dumps(body, separators=(",", ":"))
        headers = self.auth.headers("POST", path, body_json)
        async with self.session.post(
            self.base_url + path, data=body_json, headers=headers
        ) as resp:
            return await resp.json()
