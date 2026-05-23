from app.exchanges.base import BaseExchange
from app.engine.risk import RiskEngine
from app.core.logger import setup_logger
from app.storage.database import SessionLocal, TradeModel

logger = setup_logger()


class Executor:

    def __init__(self, exchange: BaseExchange, risk_engine: RiskEngine):
        self.exchange = exchange
        self.risk_engine = risk_engine

    async def _sync_portfolio_balance(self, portfolio) -> None:
        bal = await self.exchange.get_balance()
        try:
            portfolio.balance = float(bal["data"]["USDT"]["available"])
        except (KeyError, TypeError, ValueError):
            pass

    async def execute(self, portfolio, signal: dict) -> dict | None:
        await self._sync_portfolio_balance(portfolio)

        approved = self.risk_engine.validate_trade(portfolio, signal)
        if not approved:
            logger.warning("trade rejected by risk engine")
            return None

        side = signal.get("side", "buy")
        order = await self.exchange.place_order(
            market=signal["symbol"],
            side=side,
            amount=signal["amount"],
            price=signal["price"],
        )

        if order.get("code") == 1 or order.get("status") != "filled":
            logger.warning(f"order failed: {order}")
            return None

        logger.info(f"order executed: {order}")
        portfolio.add_position(signal["symbol"], {"order": order, "signal": signal})
        await self._sync_portfolio_balance(portfolio)
        self._persist_trade(order, signal)
        return order

    def _persist_trade(self, order: dict, signal: dict) -> None:
        order_id = str(order.get("data", {}).get("order_id", ""))
        if not order_id:
            return
        db = SessionLocal()
        try:
            db.add(
                TradeModel(
                    order_id=order_id,
                    market=order.get("market", signal.get("symbol", "")),
                    side=order.get("side", signal.get("side", "buy")),
                    amount=float(order.get("amount", signal.get("amount", 0))),
                    price=float(order.get("price", signal.get("price", 0))),
                    status="filled",
                )
            )
            db.commit()
        except Exception as e:
            logger.error(f"failed to persist trade: {e}")
            db.rollback()
        finally:
            db.close()
