from app.exchanges.coinex.symbol_universe import TopMarketsUniverse


def test_rank_top_usdt_by_value():
    universe = TopMarketsUniverse(limit=3)
    tickers = {
        "BTCUSDT": {"market": "BTCUSDT", "value": "1000000", "last": "1"},
        "ETHUSDT": {"market": "ETHUSDT", "value": "500000", "last": "1"},
        "DOGEUSDT": {"market": "DOGEUSDT", "value": "10000", "last": "1"},
        "BTCUSD": {"market": "BTCUSD", "value": "9999999", "last": "1"},
    }
    ranked = universe.rank_from_tickers(tickers)
    assert ranked == ["BTCUSDT", "ETHUSDT", "DOGEUSDT"]
