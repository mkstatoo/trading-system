from dataclasses import dataclass, field
from typing import Any


@dataclass
class Portfolio:
    balance: float = 0.0
    open_trades: int = 0
    daily_loss: float = 0.0
    positions: dict[str, Any] = field(default_factory=dict)

    def add_position(self, symbol: str, data: dict):
        self.positions[symbol] = data
        self.open_trades += 1

    def close_position(self, symbol: str, pnl: float = 0.0):
        if symbol in self.positions:
            del self.positions[symbol]
            self.open_trades -= 1
            if pnl < 0:
                self.daily_loss += abs(pnl) / max(self.balance, 1)
