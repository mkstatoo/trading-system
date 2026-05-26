"""
بهینه‌سازی سریع Bull Hunter (T0: رشد ۱–۲٪ در ۲ دقیقه / دو کندل ۱min).

  python scripts/optimize_bull_hunter.py          # API زنده + کش دیسک
  python scripts/optimize_bull_hunter.py --refresh
  python scripts/optimize_bull_hunter.py --demo   # داده مصنوعی (بدون شبکه)

کش: data/backtest_cache.pkl — اجرای بعدی بدون دانلود.
"""
from __future__ import annotations

import argparse
import asyncio
import bisect
import json
import pickle
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import product
from pathlib import Path

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.settings import settings
from app.exchanges.coinex.kline import fetch_klines
from app.exchanges.coinex.market_data import fetch_all_tickers_public
from app.exchanges.coinex.symbol_universe import TopMarketsUniverse
from app.strategies.filters import run_all_filters

ROOT = Path(__file__).resolve().parents[1]
CACHE_FILE = ROOT / "data" / "backtest_cache.pkl"

BACKTEST_DAYS = 7
SYMBOL_LIMIT = 55
MICRO_STEP = 2
T0_PREFILTER_PCT = 0.7
KLINE_CONCURRENCY = 16
MICRO_LIMIT = 1000
HOURLY_LIMIT = 120
DAILY_LIMIT = 60


@dataclass
class Snapshot:
    sym: str
    ts: int
    hourly_idx: int
    t0_chg: float
    t1_ratio: float
    statuses: dict[str, str]
    ret_1h: float | None = None
    ret_6h: float | None = None
    ret_12h: float | None = None


@dataclass
class SymbolData:
    sym: str
    hourly: list[dict]
    daily: list[dict]
    micro: list[dict]


def slice_by_ts(klines: list[dict], ts_ms: int) -> list[dict]:
    if not klines:
        return []
    times = [k["created_at"] for k in klines]
    return klines[: bisect.bisect_right(times, ts_ms)]


def build_ticker(h, d, m):
    last = h[-1]
    tail = h[-24:] if len(h) >= 24 else h
    return {
        "market": m,
        "last": last["close"],
        "open": d[-1]["open"] if d else last["open"],
        "value": str(sum(float(x.get("value", 0) or 0) for x in tail)),
    }


def t0_change(micro: list[dict], candles: int = 2) -> float | None:
    if len(micro) < candles + 1:
        return None
    try:
        p0 = float(micro[-1 - candles]["close"])
        p1 = float(micro[-1]["close"])
        if p0 <= 0:
            return None
        return ((p1 - p0) / p0) * 100
    except (TypeError, ValueError):
        return None


def t1_ratio_from(ticker: dict, daily: list[dict], hourly: list[dict]) -> float | None:
    """حداکثر نسبت روزانه یا ۳ ساعته (هم‌راستا با evaluate_t1)."""
    try:
        import numpy as np

        cur = float(ticker.get("value", 0) or 0)
        vals = [float(k.get("value", 0) or 0) for k in daily]
        if len(vals) < 6:
            return None
        avg = float(np.mean(vals[:-1][-20:]))
        if avg <= 0:
            return None
        daily_r = cur / avg
        hourly_r = None
        if len(hourly) >= 24:
            hvals = [float(k.get("value", 0) or 0) for k in hourly]
            recent = float(np.sum(hvals[-3:]))
            base = float(np.mean(hvals[-24:-3])) if len(hvals) >= 6 else float(np.mean(hvals[:-3]))
            if base > 0:
                hourly_r = recent / (base * 3)
        if hourly_r is not None:
            return max(daily_r, hourly_r)
        return daily_r
    except Exception:
        return None


def forward_return(hourly, idx, hours):
    if idx + hours >= len(hourly):
        return None
    p0, p1 = float(hourly[idx]["close"]), float(hourly[idx + hours]["close"])
    if p0 <= 0:
        return None
    return (p1 - p0) / p0 * 100


async def fetch_micro_extended(session: aiohttp.ClientSession, sym: str) -> list[dict]:
    """تا ۲ صفحه ۱min (~۳۳ ساعت) برای پوشش بهتر T0."""
    first = await fetch_klines(sym, "1min", MICRO_LIMIT, session)
    if len(first) < MICRO_LIMIT:
        return first
    oldest = first[0]["created_at"]
    url = settings.COINEX_BASE_URL + "/v2/spot/kline"
    params = {
        "market": sym,
        "period": "1min",
        "limit": MICRO_LIMIT,
        "end_time": oldest - 60_000,
    }
    try:
        async with session.get(url, params=params) as resp:
            data = await resp.json()
        second = sorted(data.get("data") or [], key=lambda x: x["created_at"])
    except Exception:
        second = []
    by_ts = {k["created_at"]: k for k in first + second}
    return sorted(by_ts.values(), key=lambda x: x["created_at"])


async def fetch_symbol_live(session: aiohttp.ClientSession, sym: str) -> SymbolData | None:
    micro, hourly, daily = await asyncio.gather(
        fetch_micro_extended(session, sym),
        fetch_klines(sym, "1hour", HOURLY_LIMIT, session),
        fetch_klines(sym, "1day", DAILY_LIMIT, session),
    )
    if len(micro) >= 20 and len(hourly) >= 40 and len(daily) >= 15:
        return SymbolData(sym, hourly, daily, micro)
    return None


async def load_cache_live(symbols: list[str], meta: dict, refresh: bool) -> list[SymbolData]:
    if not refresh and CACHE_FILE.exists():
        with open(CACHE_FILE, "rb") as f:
            blob = pickle.load(f)
        if blob.get("meta") == meta and blob.get("rows"):
            print(f"  کش دیسک: {len(blob['rows'])} نماد", flush=True)
            return blob["rows"]

    sem = asyncio.Semaphore(KLINE_CONCURRENCY)
    rows: list[SymbolData] = []

    async with aiohttp.ClientSession() as session:

        async def one(sym: str):
            async with sem:
                return await fetch_symbol_live(session, sym)

        tasks = [asyncio.create_task(one(s)) for s in symbols]
        done = 0
        for coro in asyncio.as_completed(tasks):
            done += 1
            row = await coro
            if row:
                rows.append(row)
            if done % 10 == 0 or done == len(tasks):
                print(f"    {done}/{len(tasks)} ok={len(rows)}", flush=True)

    if rows:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "wb") as f:
            pickle.dump({"meta": meta, "rows": rows}, f, protocol=pickle.HIGHEST_PROTOCOL)
    return rows


def make_demo_data(symbols: list[str], start_ms: int, end_ms: int) -> list[SymbolData]:
    """داده مصنوعی با چند اسپایک ۱.۵٪ برای تست pipeline."""
    rows = []
    step = 60_000
    for sym in symbols[:12]:
        micro, hourly, daily = [], [], []
        price = 100.0
        ts = start_ms
        i = 0
        while ts <= end_ms:
            if i % 47 == 0:
                chg = 1.5
            elif i % 91 == 0:
                chg = -0.3
            else:
                chg = random.uniform(-0.15, 0.15)
            price *= 1 + chg / 100
            vol = random.uniform(1e5, 5e5)
            micro.append(
                {
                    "created_at": ts,
                    "open": str(price * 0.999),
                    "close": str(price),
                    "high": str(price * 1.001),
                    "low": str(price * 0.998),
                    "volume": str(vol),
                    "value": str(vol * price),
                }
            )
            ts += step
            i += 1

        for j in range(80):
            t = start_ms + j * 3_600_000
            p = 100 * (1 + j * 0.002)
            hourly.append(
                {
                    "created_at": t,
                    "open": str(p),
                    "close": str(p * 1.001),
                    "high": str(p * 1.01),
                    "low": str(p * 0.99),
                    "volume": "1000",
                    "value": str(1e6 * (3 + random.random())),
                }
            )
        for j in range(30):
            t = start_ms - (30 - j) * 86_400_000
            daily.append(
                {
                    "created_at": t,
                    "open": str(100 + j),
                    "close": str(101 + j),
                    "high": str(102 + j),
                    "low": str(99 + j),
                    "volume": "50000",
                    "value": str(5e5),
                }
            )
        rows.append(SymbolData(sym, hourly, daily, micro))
    return rows


def build_snapshots(data: list[SymbolData], start_ms: int) -> list[Snapshot]:
    candles = settings.T0_MICRO_CANDLES
    out: list[Snapshot] = []

    for row in data:
        h_times = [k["created_at"] for k in row.hourly]
        for mi in range(candles + 1, len(row.micro), MICRO_STEP):
            ts = row.micro[mi]["created_at"]
            if ts < start_ms:
                continue
            micro = row.micro[: mi + 1]
            chg = t0_change(micro, candles)
            if chg is None or chg < T0_PREFILTER_PCT:
                continue

            h = slice_by_ts(row.hourly, ts)
            d = slice_by_ts(row.daily, ts)
            if len(h) < 30 or len(d) < 10:
                continue

            ticker = build_ticker(h, d, row.sym)
            ratio = t1_ratio_from(ticker, d, h)
            if ratio is None:
                continue

            rep = run_all_filters(row.sym, ticker, h, d, False, micro)
            idx = bisect.bisect_right(h_times, ts) - 1
            if idx < 0:
                continue

            out.append(
                Snapshot(
                    sym=row.sym,
                    ts=ts,
                    hourly_idx=idx,
                    t0_chg=chg,
                    t1_ratio=ratio,
                    statuses={r.code: r.status.value for r in rep.results},
                    ret_1h=forward_return(row.hourly, idx, 1),
                    ret_6h=forward_return(row.hourly, idx, 6),
                    ret_12h=forward_return(row.hourly, idx, 12),
                )
            )
    return out


def _warn_ok(code: str) -> bool:
    if code == "T2":
        return settings.T2_ALLOW_OVERBOUGHT_WARN
    if code == "T4":
        return settings.T4_ALLOW_MID_WARN
    if code == "T7":
        return settings.T7_ALLOW_MILD_WARN
    return False


def _counts_pass(st: dict[str, str]) -> int:
    n = 0
    for code in ("T0", "T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8"):
        s = st.get(code, "fail")
        if s == "pass":
            n += 1
        elif s == "warn" and _warn_ok(code):
            n += 1
    return n


def diagnose_snapshots(snapshots: list[Snapshot]) -> None:
    """چرا snapshotهای T0 به سیگنال تبدیل نمی‌شوند."""
    if not snapshots:
        print("  diagnose: no snapshots", flush=True)
        return
    reasons: dict[str, int] = {}
    t0_ok = [s for s in snapshots if settings.T0_MIN_PCT <= s.t0_chg <= settings.T0_MAX_PCT]
    for snap in t0_ok:
        st = dict(snap.statuses)
        st["T0"] = "pass"
        if snap.t1_ratio < settings.T1_MIN_VOLUME_RATIO:
            reasons["T1_low"] = reasons.get("T1_low", 0) + 1
            continue
        st["T1"] = "pass"
        if st.get("T2") == "fail":
            reasons["T2_fail"] = reasons.get("T2_fail", 0) + 1
            continue
        pc = _counts_pass(st)
        if pc < settings.MIN_FILTERS_PASS:
            reasons[f"pass_count<{settings.MIN_FILTERS_PASS}"] = (
                reasons.get(f"pass_count<{settings.MIN_FILTERS_PASS}", 0) + 1
            )
            continue
        blocked = None
        for code in ("T3", "T4", "T5", "T6", "T7", "T8"):
            s = st.get(code, "fail")
            if s == "warn" and not _warn_ok(code):
                blocked = f"{code}_warn"
                break
        reasons[blocked or "would_pass"] = reasons.get(blocked or "would_pass", 0) + 1

    print(f"  diagnose: T0 in band [{settings.T0_MIN_PCT}-{settings.T0_MAX_PCT}%]: {len(t0_ok)}", flush=True)
    for k, v in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"    {k}: {v}", flush=True)


def is_snap_trade(
    snap: Snapshot, t0_min: float, t0_max: float, t1_min: float, min_pass: int
) -> bool:
    chg, ratio = snap.t0_chg, snap.t1_ratio
    if chg >= settings.T0_SPIKE_WARN_PCT:
        return False
    if not (t0_min <= chg <= t0_max):
        return False
    if ratio < t1_min:
        return False

    st = dict(snap.statuses)
    st["T0"] = "pass"
    st["T1"] = "pass"

    t2 = st.get("T2", "fail")
    if t2 == "fail":
        return False
    if t2 == "warn" and not settings.T2_ALLOW_OVERBOUGHT_WARN:
        return False

    if _counts_pass(st) < min_pass:
        return False

    for code in ("T3", "T4", "T5", "T6", "T7", "T8"):
        s = st.get(code, "fail")
        if s == "warn" and not _warn_ok(code):
            return False
    return True


def score_signals(signals: list[Snapshot]) -> dict:
    r12 = [s.ret_12h for s in signals if s.ret_12h is not None]
    r6 = [s.ret_6h for s in signals if s.ret_6h is not None]
    r1 = [s.ret_1h for s in signals if s.ret_1h is not None]
    n = len(r12)
    if n < 1:
        return {"signals": n, "win12": 0, "avg12": -999, "score": -999}

    win12 = sum(1 for v in r12 if v > 0) / n
    avg12 = sum(r12) / n
    win6 = sum(1 for v in r6 if v > 0) / len(r6) if r6 else 0
    win1 = sum(1 for v in r1 if v > 0) / len(r1) if r1 else 0
    avg1 = sum(r1) / len(r1) if r1 else 0
    over = max(0, n - 25) * 0.4
    score = win12 * 45 + avg12 * 2.5 + win6 * 12 + win1 * 8 + avg1 * 1.5 + min(n, 18) * 0.4 - over
    return {
        "signals": n,
        "win12": round(win12 * 100, 1),
        "win6": round(win6 * 100, 1),
        "win1": round(win1 * 100, 1),
        "avg12": round(avg12, 2),
        "score": round(score, 2),
    }


def grid_search(snapshots: list[Snapshot]) -> list[dict]:
    results = []
    for t0min, t0max, t1, mn in product(
        [1.0, 1.2],
        [2.0],
        [2.0, 2.5, 3.0, 3.5],
        [5, 6, 7],
    ):
        picked = [s for s in snapshots if is_snap_trade(s, t0min, t0max, t1, mn)]
        results.append(
            {
                "T0_MIN_PCT": t0min,
                "T0_MAX_PCT": t0max,
                "T1_MIN_VOLUME_RATIO": t1,
                "MIN_FILTERS_PASS": mn,
                **score_signals(picked),
            }
        )
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def apply_settings(best: dict) -> None:
    path = ROOT / "app" / "core" / "settings.py"
    text = path.read_text(encoding="utf-8")
    repl = {
        "T0_MIN_PCT": float(best.get("T0_MIN_PCT", 1.0)),
        "T0_MAX_PCT": float(best.get("T0_MAX_PCT", 2.0)),
        "T1_MIN_VOLUME_RATIO": float(best.get("T1_MIN_VOLUME_RATIO", 3.0)),
        "MIN_FILTERS_PASS": int(best.get("MIN_FILTERS_PASS", 6)),
    }
    import re

    for key, val in repl.items():
        line = f"    {key}: int = {int(val)}" if key == "MIN_FILTERS_PASS" else f"    {key}: float = {val}"
        text = re.sub(rf"    {key}: [^\n]+", line, text, count=1)
    path.write_text(text, encoding="utf-8")
    print(f"Applied settings: {repl}", flush=True)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--demo", action="store_true", help="داده مصنوعی، بدون API")
    parser.add_argument("--analyze", action="store_true", help="فقط تحلیل گلوگاه فیلترها")
    args = parser.parse_args()

    t_all = time.time()
    start_ms = int(
        (datetime.now(timezone.utc) - timedelta(days=BACKTEST_DAYS)).timestamp() * 1000
    )
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    if args.demo:
        symbols = [f"DEMO{i}USDT" for i in range(12)]
        print("Demo mode (synthetic data)", flush=True)
        cache = make_demo_data(symbols, start_ms, end_ms)
    else:
        tickers = await fetch_all_tickers_public()
        symbols = TopMarketsUniverse().rank_from_tickers(tickers)[:SYMBOL_LIMIT]
        meta = {
            "days": BACKTEST_DAYS,
            "limit": SYMBOL_LIMIT,
            "micro_limit": MICRO_LIMIT,
            "v": 5,
        }
        print(
            f"Live API | {BACKTEST_DAYS}d | {len(symbols)} symbols | aiohttp x{KLINE_CONCURRENCY}",
            flush=True,
        )
        t0 = time.time()
        cache = await load_cache_live(symbols, meta, args.refresh)
        print(f"Download: {len(cache)} symbols in {time.time()-t0:.1f}s", flush=True)
        if not cache:
            print(
                "ERROR: no kline data (check internet / DNS). Try: python scripts/optimize_bull_hunter.py --demo",
                flush=True,
            )
            return

    t1 = time.time()
    snapshots = build_snapshots(cache, start_ms)
    print(f"Snapshots: {len(snapshots)} in {time.time()-t1:.1f}s", flush=True)
    diagnose_snapshots(snapshots)

    if args.analyze:
        return

    t2 = time.time()
    results = grid_search(snapshots)
    print(f"Grid: {len(results)} combos in {time.time()-t2:.4f}s", flush=True)

    best = results[0] if results and results[0].get("score", -999) > -900 else {}
    lines = [
        f"Total {time.time()-t_all:.1f}s | symbols={len(cache)} snapshots={len(snapshots)}",
        "",
    ]
    for r in results[:8]:
        lines.append(
            f"  score={r['score']} sig={r['signals']} win12={r['win12']}% avg12={r['avg12']}% "
            f"T0=[{r['T0_MIN_PCT']}-{r['T0_MAX_PCT']}] T1={r['T1_MIN_VOLUME_RATIO']}x min={r['MIN_FILTERS_PASS']}/9"
        )
    lines.append("")
    lines.append("BEST: " + json.dumps(best, ensure_ascii=False))
    report = "\n".join(lines)
    print("\n" + report)

    with open(ROOT / "optimize_results.json", "w", encoding="utf-8") as f:
        json.dump({"best": best, "all": results, "snapshots": len(snapshots)}, f, indent=2)
    with open(ROOT / "optimize_report.txt", "w", encoding="utf-8") as f:
        f.write(report)

    if best and not args.demo:
        apply_settings(best)
    elif best and args.demo:
        print("(demo — settings not written)", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
