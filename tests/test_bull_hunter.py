import pytest
from unittest.mock import AsyncMock, patch

from app.strategies.bull_hunter import BullHunterStrategy
from app.strategies.filters import FilterReport, FilterResult, FilterStatus


def _make_report(market: str, all_pass: bool) -> FilterReport:
    status = FilterStatus.PASS if all_pass else FilterStatus.FAIL
    results = [
        FilterResult(f"T{i}", f"test{i}", status, "ok") for i in range(0, 9)
    ]
    return FilterReport(market=market, results=results)


@pytest.mark.asyncio
async def test_analyze_returns_signal_when_all_pass():
    strategy = BullHunterStrategy(notional_base=10_000)
    ticker = {"market": "BTCUSDT", "last": "50000", "value": "1000000"}

    report = _make_report("BTCUSDT", True)
    with (
        patch.object(strategy, "evaluate", AsyncMock(return_value=report)),
        patch("app.strategies.bull_hunter.signal_history.record_signal"),
        patch("app.strategies.bull_hunter.signal_history.has_recent_signal", return_value=False),
    ):
        signal = await strategy.analyze(ticker)

    assert signal is not None
    assert signal["symbol"] == "BTCUSDT"
    assert "filters" in signal


@pytest.mark.asyncio
async def test_analyze_none_when_filter_fails():
    strategy = BullHunterStrategy()
    ticker = {"market": "ETHUSDT", "last": "3000"}
    report = _make_report("ETHUSDT", False)

    with patch.object(strategy, "evaluate", AsyncMock(return_value=report)):
        assert await strategy.analyze(ticker) is None
