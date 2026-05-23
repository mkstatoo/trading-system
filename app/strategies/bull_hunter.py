from typing import Optional

from app.strategies.base import BaseStrategy
from app.core.settings import settings


class BullHunterStrategy(BaseStrategy):
    """
    Momentum strategy (Bull Hunter):
    BUY when price rises above open by momentum_pct%.
  Position size = portfolio_notional * RISK_PER_TRADE / last_price.
    """

    def __init__(
        self,
        momentum_pct: float | None = None,
        notional_base: float | None = None,
    ):
        self.momentum_pct = momentum_pct or settings.BULL_HUNTER_MOMENTUM_PCT
        self.notional_base = notional_base or settings.INITIAL_BALANCE

    async def analyze(self, market_data: dict) -> Optional[dict]:
        try:
            last_price = float(market_data.get("last", 0))
            open_price = float(market_data.get("open", 0) or last_price)
        except (TypeError, ValueError):
            return None

        if last_price <= 0 or open_price <= 0:
            return None

        change_pct = ((last_price - open_price) / open_price) * 100

        if change_pct >= self.momentum_pct:
            risk_per_trade = settings.RISK_PER_TRADE
            amount = round((self.notional_base * risk_per_trade) / last_price, 8)
            if amount <= 0:
                return None
            return {
                "symbol": market_data.get("market", ""),
                "price": last_price,
                "amount": amount,
                "side": "buy",
                "reason": f"momentum {change_pct:.2f}% >= {self.momentum_pct}%",
            }

        return None
