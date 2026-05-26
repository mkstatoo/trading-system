"""Paginated historical klines for backtests (CoinEx: start_time/end_time in ms)."""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

from app.core.settings import settings

_PERIOD_MS = {
    "1min": 60_000,
    "3min": 180_000,
    "5min": 300_000,
    "15min": 900_000,
    "30min": 1_800_000,
    "1hour": 3_600_000,
    "2hour": 7_200_000,
    "4hour": 14_400_000,
    "6hour": 21_600_000,
    "12hour": 43_200_000,
    "1day": 86_400_000,
}


def _normalize_ts_ms(ts: int) -> int:
    if ts > 10_000_000_000_000:
        return ts // 1000
    if ts < 10_000_000_000:
        return ts * 1000
    return ts


def _fetch_page(
    market: str,
    period: str,
    *,
    limit: int,
    end_ms: int | None = None,
    retries: int = 4,
) -> list[dict]:
    params: dict = {"market": market, "period": period, "limit": min(limit, 1000)}
    if end_ms is not None:
        params["end_time"] = end_ms
    url = f"{settings.COINEX_BASE_URL}/v2/spot/kline?{urllib.parse.urlencode(params)}"
    for _ in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=25) as resp:
                data = json.loads(resp.read().decode())
            if data.get("code") == 0:
                rows = data.get("data") or []
                for row in rows:
                    row["created_at"] = _normalize_ts_ms(int(row["created_at"]))
                return sorted(rows, key=lambda x: x["created_at"])
        except Exception:
            time.sleep(1.0)
    return []


def fetch_klines_range(
    market: str,
    period: str,
    start_ms: int,
    end_ms: int,
    *,
    page_limit: int = 1000,
) -> list[dict]:
    step = _PERIOD_MS.get(period, 60_000)
    by_ts: dict[int, dict] = {}
    cursor_end = end_ms
    max_pages = 80

    for _ in range(max_pages):
        batch = _fetch_page(market, period, limit=page_limit, end_ms=cursor_end)
        if not batch:
            break
        for row in batch:
            ts = row["created_at"]
            if start_ms <= ts <= end_ms:
                by_ts[ts] = row
        oldest = batch[0]["created_at"]
        if oldest <= start_ms:
            break
        next_end = oldest - step
        if next_end >= cursor_end:
            break
        cursor_end = next_end
        if len(batch) < page_limit:
            break
        time.sleep(0.1)

    return sorted(by_ts.values(), key=lambda x: x["created_at"])
