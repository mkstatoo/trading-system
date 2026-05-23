from sqlalchemy.orm import Session
from app.storage.database import TradeModel


class TradeRepository:

    def __init__(self, db: Session):
        self.db = db

    def save_trade(self, trade_data: dict) -> TradeModel:
        trade = TradeModel(**trade_data)
        self.db.add(trade)
        self.db.commit()
        self.db.refresh(trade)
        return trade

    def get_open_trades(self) -> list[TradeModel]:
        return self.db.query(TradeModel).filter(TradeModel.status == "open").all()

    def close_trade(self, order_id: str) -> None:
        trade = self.db.query(TradeModel).filter(TradeModel.order_id == order_id).first()
        if trade:
            trade.status = "closed"
            self.db.commit()
