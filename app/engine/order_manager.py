from app.exchanges.base import BaseExchange
from app.core.logger import setup_logger

logger = setup_logger()


class OrderManager:

    def __init__(self, exchange: BaseExchange):
        self.exchange = exchange
        self.active_orders: dict[str, dict] = {}

    async def place_limit_buy(self, symbol: str, amount: float, price: float) -> dict:
        order = await self.exchange.place_order(
            market=symbol,
            side="buy",
            amount=amount,
            price=price,
        )
        order_id = str(order.get("data", {}).get("order_id", ""))
        if order_id:
            self.active_orders[order_id] = order
            logger.info(f"buy order placed: {symbol} {amount}@{price}")
        return order

    async def place_limit_sell(self, symbol: str, amount: float, price: float) -> dict:
        order = await self.exchange.place_order(
            market=symbol,
            side="sell",
            amount=amount,
            price=price,
        )
        order_id = str(order.get("data", {}).get("order_id", ""))
        if order_id:
            self.active_orders[order_id] = order
            logger.info(f"sell order placed: {symbol} {amount}@{price}")
        return order

    async def cancel(self, order_id: str) -> dict:
        result = await self.exchange.cancel_order(order_id)
        self.active_orders.pop(order_id, None)
        return result
