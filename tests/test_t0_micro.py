from app.strategies.filters import evaluate_t0_micro_momentum, FilterStatus


def test_t0_pass_on_2pct_rise():
    klines = [
        {"close": "100"},
        {"close": "100"},
        {"close": "102"},
    ]
    r = evaluate_t0_micro_momentum(klines)
    assert r.status == FilterStatus.PASS


def test_t0_fail_low_move():
    klines = [{"close": "100"}, {"close": "100"}, {"close": "100.5"}]
    r = evaluate_t0_micro_momentum(klines)
    assert r.status == FilterStatus.FAIL
