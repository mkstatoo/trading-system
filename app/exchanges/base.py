from abc import ABC, abstractmethod


class BaseExchange(ABC):

    @abstractmethod
    async def get_balance(self) -> dict:
        pass

    @abstractmethod
    async def place_order(self, market: str, side: str, amount: float, price: float) -> dict:
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> dict:
        pass

    @abstractmethod
    async def fetch_ticker(self, market: str) -> dict:
        pass
