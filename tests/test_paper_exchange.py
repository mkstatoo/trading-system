import asyncio
import pytest
from app.engine.paper_exchange import PaperExchange


def test_paper_buy_sell():
    exchange = PaperExchange(initial_balance=1000.0)

    async def run():
        # Buy
        result = await exchange.place_order("BTCUSDT", "buy", 0.1, 500.0)
        assert result["status"] == "filled"
        assert exchange.balance == pytest.approx(950.0)

        # Sell
        result = await exchange.place_order("BTCUSDT", "sell", 0.1, 600.0)
        assert result["status"] == "filled"
        assert exchange.balance == pytest.approx(1010.0)

    asyncio.run(run())


def test_paper_insufficient_balance():
    exchange = PaperExchange(initial_balance=10.0)

    async def run():
        result = await exchange.place_order("BTCUSDT", "buy", 1.0, 50_000.0)
        assert result["code"] == 1

    asyncio.run(run())
