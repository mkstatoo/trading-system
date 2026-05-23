from app.exchanges.coinex.client import CoinExClient
from app.core.logger import setup_logger

logger = setup_logger()


class AccountManager:

    def __init__(self, client: CoinExClient):
        self.client = client

    async def get_usdt_balance(self) -> float:
        data = await self.client.get_balance()
        balances = data.get("data", {})
        usdt = balances.get("USDT", {})
        return float(usdt.get("available", 0))
