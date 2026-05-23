from app.core.settings import settings
from app.core.logger import setup_logger

logger = setup_logger()


class RiskEngine:

    def __init__(self):
        self.max_daily_loss: float = settings.MAX_DAILY_LOSS
        self.max_open_trades: int = settings.MAX_OPEN_TRADES
        self.risk_per_trade: float = settings.RISK_PER_TRADE

    def validate_trade(self, portfolio, signal: dict) -> bool:
        if portfolio.daily_loss >= self.max_daily_loss:
            logger.warning("risk rejected: daily loss limit reached")
            return False

        if portfolio.open_trades >= self.max_open_trades:
            logger.warning("risk rejected: max open trades reached")
            return False

        amount = float(signal.get("amount", 0) or 0)
        price = float(signal.get("price", 0) or 0)
        if amount <= 0 or price <= 0:
            logger.warning("risk rejected: invalid amount or price")
            return False

        notional = amount * price
        max_notional = portfolio.balance * self.risk_per_trade * 2
        if notional > portfolio.balance:
            logger.warning("risk rejected: insufficient balance for notional")
            return False
        if notional > max_notional and max_notional > 0:
            logger.warning("risk rejected: position exceeds risk budget")
            return False

        symbol = signal.get("symbol", "")
        if symbol and symbol in portfolio.positions:
            logger.warning(f"risk rejected: already in position {symbol}")
            return False

        return True
