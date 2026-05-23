from abc import ABC, abstractmethod
from typing import Optional


class BaseStrategy(ABC):

    @abstractmethod
    async def analyze(self, market_data: dict) -> Optional[dict]:
        """Return a signal dict or None."""
        raise NotImplementedError
