import uuid

from app.exchanges.base import BaseExchange
from app.exchanges.coinex.market_data import fetch_ticker_public
from app.core.logger import setup_logger

logger = setup_logger()


class PaperExchange(BaseExchange):
    """Simulated exchange — uses live CoinEx tickers, simulated fills."""

    def __init__(self, initial_balance: float = 10_000.0):
        self.balance = initial_balance
        self.positions: dict[str, dict] = {}
        self.order_history: list[dict] = []

    async def get_balance(self) -> dict:
        return {"code": 0, "data": {"USDT": {"available": str(round(self.balance, 8))}}}

    async def fetch_ticker(self, market: str) -> dict:
        return await fetch_ticker_public(market)

    async def place_order(self, market: str, side: str, amount: float, price: float) -> dict:
        order_id = str(uuid.uuid4())[:12]
        cost = amount * price

        if side == "buy":
            if cost > self.balance:
                return {"code": 1, "message": "insufficient balance"}
            self.balance -= cost
            self.positions[market] = {
                "amount": amount,
                "entry_price": price,
            }
        elif side == "sell":
            if market not in self.positions:
                return {"code": 1, "message": "no position to sell"}
            self.balance += amount * price
            del self.positions[market]
        else:
            return {"code": 1, "message": f"unsupported side: {side}"}

        order = {
            "code": 0,
            "status": "filled",
            "market": market,
            "side": side,
            "amount": amount,
            "price": price,
            "data": {"order_id": order_id},
        }
        self.order_history.append(order)
        logger.info(f"[PAPER] {side.upper()} {amount} {market} @ {price}")
        return order

    async def cancel_order(self, order_id: str) -> dict:
        return {"code": 0, "message": "cancelled (paper)"}
