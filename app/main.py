from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.exchanges.coinex.client import CoinExClient
from app.engine.paper_exchange import PaperExchange
from app.engine.portfolio import Portfolio
from app.engine.risk import RiskEngine
from app.engine.order_manager import OrderManager
from app.engine.executor import Executor
from app.engine.scanner import MarketScanner
from app.engine.trading_engine import TradingEngine
from app.strategies.bull_hunter import BullHunterStrategy
from app.api.routes.health import router as health_router
from app.api.routes.trading import router as trading_router
from app.api.websocket.manager import manager as ws_manager
from app.storage.database import init_db
from app.core.logger import setup_logger
from app.core.settings import settings

logger = setup_logger()

# Global singletons
paper_exchange = PaperExchange(initial_balance=settings.INITIAL_BALANCE)
live_exchange = CoinExClient()
portfolio = Portfolio(balance=settings.INITIAL_BALANCE)
risk_engine = RiskEngine()
order_manager = OrderManager(paper_exchange)
strategy = BullHunterStrategy()
active_exchange = paper_exchange if settings.PAPER_TRADING else live_exchange
scanner = MarketScanner(strategy, active_exchange)
executor = Executor(active_exchange, risk_engine)
trading_engine = TradingEngine(scanner, executor, portfolio)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info(
        "trading system started — paper=%s auto=%s symbols=%s",
        settings.PAPER_TRADING,
        settings.AUTO_TRADING,
        settings.symbol_list,
    )
    if settings.AUTO_TRADING:
        trading_engine.start()
    yield
    await trading_engine.stop()
    await live_exchange.close()
    logger.info("trading system stopped")


app = FastAPI(
    title="Trading System",
    description="CoinEx crypto trading bot — Bull Hunter strategy",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(trading_router)


@app.get("/")
async def root():
    return {
        "name": "trading-system",
        "paper_trading": settings.PAPER_TRADING,
        "auto_trading": settings.AUTO_TRADING,
        "docs": "/docs",
    }


@app.get("/status")
async def status():
    return trading_engine.status()


@app.get("/balance")
async def balance():
    """Live CoinEx balance (requires valid API keys)."""
    return await live_exchange.get_balance()


@app.get("/paper/balance")
async def paper_balance():
    return await paper_exchange.get_balance()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await ws_manager.broadcast({"type": "echo", "data": data})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
