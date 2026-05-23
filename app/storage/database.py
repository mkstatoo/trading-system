from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer, Boolean, Text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.sql import func
from app.core.settings import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class SignalHistoryModel(Base):
    __tablename__ = "signal_history"

    id = Column(Integer, primary_key=True, index=True)
    market = Column(String, index=True)
    passed = Column(Boolean, default=True)
    filters_json = Column(Text, default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TradeModel(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, unique=True, index=True)
    market = Column(String)
    side = Column(String)
    amount = Column(Float)
    price = Column(Float)
    status = Column(String, default="open")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


def init_db():
    Base.metadata.create_all(bind=engine)
