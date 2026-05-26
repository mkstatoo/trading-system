"""Quick probe CoinEx historical kline availability."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.exchanges.coinex.kline_history import fetch_klines_range, _fetch_page

now = datetime.now(timezone.utc)
for days in (7, 14, 30, 45, 60, 85):
    end = now - timedelta(days=days - 4)
    start = now - timedelta(days=days)
    s, e = int(start.timestamp() * 1000), int(end.timestamp() * 1000)
    print(f"\n--- {days}d ago: {start.date()} -> {end.date()} ---")
    for period in ("1min", "3min", "1hour", "1day"):
        n = len(fetch_klines_range("BTCUSDT", period, s, e))
        print(f"  {period}: {n}")

print("\nRaw page test (1min end only):")
end_ms = int((now - timedelta(days=45)).timestamp() * 1000)
batch = _fetch_page("BTCUSDT", "1min", limit=5, end_ms=end_ms)
print("  batch", len(batch), batch[0] if batch else "empty")
