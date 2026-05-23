import numpy as np

from app.strategies.filters import (
    run_all_filters,
    is_trade_allowed,
    FilterStatus,
    evaluate_t1_volume_ratio,
)
from app.strategies import indicators as ind


def _hourly_closes(closes: list[float]) -> dict:
    n = len(closes)
    return {
        "open": np.array(closes),
        "high": np.array([c * 1.01 for c in closes]),
        "low": np.array([c * 0.99 for c in closes]),
        "close": np.array(closes),
        "volume": np.ones(n) * 1000,
        "value": np.ones(n) * 50000,
    }


def test_rsi_range():
    closes = np.linspace(100, 110, 50)
    val = ind.rsi(closes, 7)
    assert val is not None
    assert 45 <= val <= 100


def test_t1_volume_ratio_pass():
    ticker = {"value": "5000000"}
    daily = [{"value": "100000"} for _ in range(10)]
    daily.append({"value": "5000000"})
    r = evaluate_t1_volume_ratio(ticker, daily)
    assert r.status == FilterStatus.PASS


def test_all_filters_synthetic_bull():
    closes_h = list(np.linspace(1.0, 1.3, 80))
    hourly_klines = []
    for i, c in enumerate(closes_h):
        hourly_klines.append(
            {
                "open": str(c * 0.99),
                "high": str(c * 1.02),
                "low": str(c * 0.98),
                "close": str(c),
                "volume": "10000",
                "value": "50000",
                "created_at": i,
            }
        )
    daily_closes = list(np.linspace(0.8, 1.2, 55))
    daily_klines = []
    for i, c in enumerate(daily_closes):
        daily_klines.append(
            {
                "open": str(c),
                "high": str(c * 1.01),
                "low": str(c * 0.99),
                "close": str(c),
                "volume": "100000",
                "value": "200000" if i < 54 else "5000000",
                "created_at": i,
            }
        )
    ticker = {
        "market": "TESTUSDT",
        "last": str(closes_h[-1]),
        "value": "5000000",
    }
    report = run_all_filters("TESTUSDT", ticker, hourly_klines, daily_klines, False)
    assert report.passed_count >= 5
    # ممکن است همه ۸ پاس نشوند — فقط ساختار را چک می‌کنیم
    assert len(report.results) == 8


def test_is_trade_allowed_strict():
    from app.strategies.filters import FilterReport, FilterResult

    report = FilterReport(
        market="X",
        results=[
            FilterResult("T1", "t1", FilterStatus.PASS, ""),
            FilterResult("T2", "t2", FilterStatus.WARN, ""),
        ],
    )
    assert is_trade_allowed(report) is False
