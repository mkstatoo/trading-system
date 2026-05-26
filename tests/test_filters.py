import numpy as np

from app.strategies.filters import (
    run_all_filters,
    is_trade_allowed,
    counts_as_pass,
    FilterStatus,
    FilterReport,
    FilterResult,
    evaluate_t1_volume_ratio,
)
from app.strategies import indicators as ind


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


def test_counts_as_pass_t2_warn():
    r = FilterResult("T2", "t2", FilterStatus.WARN, "")
    assert counts_as_pass(r) is True


def test_is_trade_allowed_seven_of_nine():
    results = [
        FilterResult("T0", "t0", FilterStatus.PASS, ""),
        FilterResult("T1", "t1", FilterStatus.PASS, ""),
        FilterResult("T2", "t2", FilterStatus.WARN, ""),
        FilterResult("T3", "t3", FilterStatus.PASS, ""),
        FilterResult("T4", "t4", FilterStatus.PASS, ""),
        FilterResult("T5", "t5", FilterStatus.PASS, ""),
        FilterResult("T6", "t6", FilterStatus.PASS, ""),
        FilterResult("T7", "t7", FilterStatus.FAIL, ""),
        FilterResult("T8", "t8", FilterStatus.FAIL, ""),
    ]
    report = FilterReport(market="X", results=results)
    assert is_trade_allowed(report) is True


def test_is_trade_allowed_t1_fail_blocks():
    results = [
        FilterResult("T0", "t0", FilterStatus.PASS, ""),
        FilterResult("T1", "t1", FilterStatus.FAIL, ""),
        FilterResult("T2", "t2", FilterStatus.PASS, ""),
    ] + [FilterResult(f"T{i}", "t", FilterStatus.PASS, "") for i in range(3, 9)]
    report = FilterReport(market="X", results=results)
    assert is_trade_allowed(report) is False


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
    micro = [
        {"close": "1.0", "created_at": 0},
        {"close": "1.0", "created_at": 1},
        {"close": "1.02", "created_at": 2},
    ]
    report = run_all_filters(
        "TESTUSDT", ticker, hourly_klines, daily_klines, False, micro
    )
    assert report.passed_count >= 5
    assert len(report.results) == 9
