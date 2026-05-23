import pytest
from app.strategies.bull_hunter import BullHunterStrategy


@pytest.mark.asyncio
async def test_bull_hunter_momentum_signal():
    strategy = BullHunterStrategy(momentum_pct=0.5, notional_base=10_000)
    ticker = {
        "market": "BTCUSDT",
        "last": "101",
        "open": "100",
    }
    signal = await strategy.analyze(ticker)
    assert signal is not None
    assert signal["symbol"] == "BTCUSDT"
    assert signal["side"] == "buy"


@pytest.mark.asyncio
async def test_bull_hunter_no_signal_below_threshold():
    strategy = BullHunterStrategy(momentum_pct=2.0)
    ticker = {"market": "BTCUSDT", "last": "100.5", "open": "100"}
    assert await strategy.analyze(ticker) is None
