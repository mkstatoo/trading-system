from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Order:
    order_id: str
    market: str
    side: str
    amount: float
    price: float
    status: str = "pending"
    filled: float = 0.0
