"""
بک‌تست واقعی Bull Hunter — فقط داده CoinEx API.

  python scripts/backtest_real.py
  python scripts/backtest_real.py --days-ago-start 50 --window-days 4
  python scripts/backtest_real.py --walk-forward   # چند پنجره ۴ روزه در ۹۰ روز گذشته

خروجی: reports/backtest_real_report.txt + backtest_real_signals.json
"""
from __future__ import annotations

import argparse
import asyncio
import bisect
import json
import math
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.settings import settings
import aiohttp

from app.exchanges.coinex.kline import fetch_klines
from app.exchanges.coinex.market_data import fetch_all_tickers_public
from app.exchanges.coinex.symbol_universe import TopMarketsUniverse
from app.strategies.filters import (
    FilterStatus,
    counts_as_pass,
    is_trade_allowed,
    run_all_filters,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"

SYMBOL_LIMIT = 80
MICRO_STEP = 2
T0_PREFILTER = 0.7
KLINE_CONCURRENCY = 12
WARMUP_DAILY_DAYS = 90
WARMUP_HOURLY_DAYS = 14

_PERIOD_MS = {
    "1min": 60_000,
    "3min": 180_000,
    "1hour": 3_600_000,
    "1day": 86_400_000,
}


@dataclass
class TradeSignal:
    market: str
    ts: int
    price: float
    t0_chg: float
    pass_count: int
    filters: list[dict]
    ret_1h: float | None = None
    ret_6h: float | None = None
    ret_12h: float | None = None
    ret_24h: float | None = None


@dataclass
class WindowResult:
    label: str
    start_ms: int
    end_ms: int
    symbols_loaded: int
    signals: list[TradeSignal] = field(default_factory=list)


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


def t0_change(micro: list[dict], candles: int) -> float | None:
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


def forward_return(hourly: list[dict], idx: int, hours: int) -> float | None:
    j = idx + hours
    if j >= len(hourly):
        return None
    p0, p1 = float(hourly[idx]["close"]), float(hourly[j]["close"])
    if p0 <= 0:
        return None
    return (p1 - p0) / p0 * 100


async def fetch_period_range(
    session: aiohttp.ClientSession,
    sym: str,
    period: str,
    start_ms: int,
    end_ms: int,
) -> list[dict]:
    """دریافت بازه — ابتدا start+end؛ در صورت نیاز paginate با end_time (ms)."""
    batch = await fetch_klines(
        sym, period, 1000, session, start_ms=start_ms, end_ms=end_ms
    )
    if batch and batch[0]["created_at"] <= start_ms + _PERIOD_MS.get(period, 60_000) * 2:
        return batch

    step = _PERIOD_MS.get(period, 60_000)
    by_ts: dict[int, dict] = {r["created_at"]: r for r in batch if start_ms <= r["created_at"] <= end_ms}
    cursor_end = end_ms
    for _ in range(80):
        page = await fetch_klines(sym, period, 1000, session, end_ms=cursor_end)
        if not page:
            break
        for row in page:
            ts = row["created_at"]
            if start_ms <= ts <= end_ms:
                by_ts[ts] = row
        oldest = page[0]["created_at"]
        if oldest <= start_ms:
            break
        nxt = oldest - step
        if nxt >= cursor_end:
            break
        cursor_end = nxt
        if len(page) < 1000:
            break
        await asyncio.sleep(0.06)
    return sorted(by_ts.values(), key=lambda x: x["created_at"])


async def load_symbol_klines(
    session: aiohttp.ClientSession,
    sem: asyncio.Semaphore,
    sym: str,
    win_start: int,
    win_end: int,
) -> tuple[str, list, list, list] | None:
    async with sem:
        try:
            micro = await fetch_period_range(session, sym, "1min", win_start, win_end)
            hourly = await fetch_period_range(
                session,
                sym,
                "1hour",
                win_start - WARMUP_HOURLY_DAYS * 86400 * 1000,
                win_end,
            )
            daily = await fetch_period_range(
                session,
                sym,
                "1day",
                win_start - WARMUP_DAILY_DAYS * 86400 * 1000,
                win_end,
            )
            if len(micro) < 50 or len(hourly) < 40 or len(daily) < 15:
                return None
            return sym, hourly, daily, micro
        except Exception:
            return None


def backtest_symbol(
    sym: str,
    hourly: list[dict],
    daily: list[dict],
    micro: list[dict],
    win_start: int,
    win_end: int,
) -> list[TradeSignal]:
    candles = settings.T0_MICRO_CANDLES
    cooldown_ms = settings.T6_COOLDOWN_DAYS * 86400 * 1000
    recent_ts: int | None = None
    h_times = [k["created_at"] for k in hourly]
    out: list[TradeSignal] = []

    for mi in range(candles + 1, len(micro), MICRO_STEP):
        ts = micro[mi]["created_at"]
        if ts < win_start or ts > win_end:
            continue
        micro_slice = micro[: mi + 1]
        chg = t0_change(micro_slice, candles)
        if chg is None or chg < T0_PREFILTER:
            continue

        h = slice_by_ts(hourly, ts)
        d = slice_by_ts(daily, ts)
        if len(h) < 30 or len(d) < 10:
            continue

        has_recent = recent_ts is not None and (ts - recent_ts) < cooldown_ms
        ticker = build_ticker(h, d, sym)
        report = run_all_filters(sym, ticker, h, d, has_recent, micro_slice)
        if not is_trade_allowed(report):
            continue

        idx = bisect.bisect_right(h_times, ts) - 1
        if idx < 0:
            continue

        price = float(ticker["last"])
        out.append(
            TradeSignal(
                market=sym,
                ts=ts,
                price=price,
                t0_chg=chg,
                pass_count=sum(1 for r in report.results if counts_as_pass(r)),
                filters=[
                    {
                        "code": r.code,
                        "status": r.status.value,
                        "detail": r.detail,
                    }
                    for r in report.results
                ],
                ret_1h=forward_return(hourly, idx, 1),
                ret_6h=forward_return(hourly, idx, 6),
                ret_12h=forward_return(hourly, idx, 12),
                ret_24h=forward_return(hourly, idx, 24),
            )
        )
        recent_ts = ts
    return out


async def run_window(
    symbols: list[str],
    win_start: int,
    win_end: int,
    label: str,
) -> WindowResult:
    result = WindowResult(label=label, start_ms=win_start, end_ms=win_end, symbols_loaded=0)
    print(f"\n=== {label} ===", flush=True)
    print(
        f"  {datetime.fromtimestamp(win_start/1000, tz=timezone.utc).date()} "
        f"→ {datetime.fromtimestamp(win_end/1000, tz=timezone.utc).date()} UTC",
        flush=True,
    )

    loaded = []
    sem = asyncio.Semaphore(KLINE_CONCURRENCY)
    async with aiohttp.ClientSession() as session:
        tasks = [
            asyncio.create_task(load_symbol_klines(session, sem, s, win_start, win_end))
            for s in symbols
        ]
        done = 0
        for coro in asyncio.as_completed(tasks):
            done += 1
            row = await coro
            if row:
                loaded.append(row)
            if done % 20 == 0 or done == len(tasks):
                print(f"  API load {done}/{len(tasks)} ok={len(loaded)}", flush=True)

    result.symbols_loaded = len(loaded)
    for sym, hourly, daily, micro in loaded:
        result.signals.extend(backtest_symbol(sym, hourly, daily, micro, win_start, win_end))

    print(f"  signals: {len(result.signals)}", flush=True)
    return result


def wilson_ci(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """فاصله اطمینان ۹۵٪ برای نرخ برد (Wilson score)."""
    if n == 0:
        return 0.0, 0.0
    p = wins / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = z * math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / denom
    return max(0, center - margin) * 100, min(1, center + margin) * 100


def summarize(signals: list[TradeSignal], horizon: str) -> dict:
    key = f"ret_{horizon}"
    vals = [getattr(s, key) for s in signals if getattr(s, key) is not None]
    if not vals:
        return {"n": 0, "win_pct": 0, "avg": 0, "median": 0, "ci_low": 0, "ci_high": 0}
    wins = sum(1 for v in vals if v > 0)
    n = len(vals)
    vals_sorted = sorted(vals)
    med = vals_sorted[n // 2]
    lo, hi = wilson_ci(wins, n)
    return {
        "n": n,
        "win_pct": round(100 * wins / n, 1),
        "avg": round(sum(vals) / n, 2),
        "median": round(med, 2),
        "ci_low": round(lo, 1),
        "ci_high": round(hi, 1),
    }


def aggregate_stats(results: list[WindowResult]) -> dict:
    all_sig = []
    for r in results:
        all_sig.extend(r.signals)
    return {
        "windows": len(results),
        "total_signals": len(all_sig),
        "h1": summarize(all_sig, "1h"),
        "h6": summarize(all_sig, "6h"),
        "h12": summarize(all_sig, "12h"),
        "h24": summarize(all_sig, "24h"),
    }


def format_report(
    results: list[WindowResult],
    symbols_count: int,
    settings_snapshot: dict,
) -> str:
    lines = [
        "=" * 60,
        "گزارش بک‌تست واقعی Bull Hunter (CoinEx API)",
        "=" * 60,
        f"تاریخ گزارش: {datetime.now(timezone.utc).isoformat()}",
        f"منبع داده: {settings.COINEX_BASE_URL} (klines واقعی)",
        f"نمادها: Top {symbols_count} بر اساس حجم (لیست فعلی)",
        "",
        "تنظیمات استراتژی:",
        json.dumps(settings_snapshot, indent=2, ensure_ascii=False),
        "",
    ]

    agg = aggregate_stats(results)
    lines.append("--- خلاصه کل ---")
    lines.append(f"پنجره‌ها: {agg['windows']} | کل سیگنال: {agg['total_signals']}")
    for hname, key in [("۱h", "h1"), ("۶h", "h6"), ("۱۲h", "h12"), ("۲۴h", "h24")]:
        s = agg[key]
        lines.append(
            f"  {hname}: n={s['n']} برد={s['win_pct']}% میانگین={s['avg']}% "
            f"میانه={s['median']}% | CI95%=[{s['ci_low']}-{s['ci_high']}]"
        )

    for wr in results:
        lines.append("")
        lines.append(f"--- پنجره: {wr.label} ---")
        lines.append(
            f"UTC: {datetime.fromtimestamp(wr.start_ms/1000, tz=timezone.utc).date()} "
            f"تا {datetime.fromtimestamp(wr.end_ms/1000, tz=timezone.utc).date()}"
        )
        lines.append(f"نماد بارگذاری‌شده: {wr.symbols_loaded} | سیگنال: {len(wr.signals)}")
        for hname, hk in [("۱h", "1h"), ("۶h", "6h"), ("۱۲h", "12h"), ("۲۴h", "24h")]:
            s = summarize(wr.signals, hk)
            lines.append(f"  {hname}: برد={s['win_pct']}% avg={s['avg']}% (n={s['n']})")

        if wr.signals:
            lines.append("  سیگنال‌ها:")
            for sig in wr.signals[:25]:
                ts_s = datetime.fromtimestamp(sig.ts / 1000, tz=timezone.utc).strftime(
                    "%Y-%m-%d %H:%M"
                )
                r12 = sig.ret_12h
                r12s = f"{r12:+.2f}%" if r12 is not None else "n/a"
                lines.append(
                    f"    {sig.market} @ {ts_s} T0={sig.t0_chg:+.2f}% "
                    f"pass={sig.pass_count}/9 ret12h={r12s}"
                )
            if len(wr.signals) > 25:
                lines.append(f"    ... و {len(wr.signals)-25} مورد دیگر")

    lines.extend(
        [
            "",
            "=" * 60,
            "آیا می‌توان ۱۰۰٪ از نرخ برد مطمئن شد؟",
            "=" * 60,
            "خیر — در بازار رمزارز هیچ استراتژی نرخ برد ثابت ۱۰۰٪ ندارد و بک‌تست",
            "گذشته تضمین آینده نیست. برای اطمینان آماری بیشتر:",
            "",
            "۱) نمونه بزرگ: حداقل ۳۰–۵۰ سیگنال (این گزارش: "
            f"{agg['total_signals']} سیگنال).",
            "۲) Walk-forward: چند پنجره ۴ روزه جدا (پرچم --walk-forward).",
            "۳) فاصله اطمینان Wilson: اگر CI95% برای برد ۱۲h شامل ۵۰٪ باشد،",
            "   استراتژی هنوز اثبات‌شده نیست.",
            "۴) Paper trading زنده ۳۰+ روز بدون تغییر پارامتر.",
            "۵) جلوگیری از overfitting: پارامتر را فقط روی train تنظیم و روی test جدا ارزیابی کنید.",
            "",
            "معیار پیشنهادی برای «قابل اعتماد بودن»:",
            "  - ≥۴۰ سیگنال در walk-forward",
            "  - win12h > ۵۵٪ با CI95% پایین > ۴۵٪",
            "  - میانگین ret12h مثبت",
            "  - paper trading ۳۰ روز هم‌جهت با بک‌تست",
            "",
            "ابزارهای پروژه:",
            "  python scripts/backtest_real.py --walk-forward",
            "  python scripts/optimize_bull_hunter.py --refresh",
            "  داشبورد paper: http://127.0.0.1:7000",
            "=" * 60,
        ]
    )
    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(description="بک‌تست واقعی ۴ روزه")
    parser.add_argument(
        "--days-ago-start",
        type=int,
        default=45,
        help="شروع پنجره: چند روز قبل از امروز (پیش‌فرض ۴۵ ≈ میانه ۳ ماه)",
    )
    parser.add_argument("--window-days", type=int, default=4)
    parser.add_argument(
        "--walk-forward",
        action="store_true",
        help="۶ پنجره ۴ روزه در ۹۰ روز گذشته برای اطمینان آماری",
    )
    parser.add_argument("--symbols", type=int, default=SYMBOL_LIMIT)
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    tickers = await fetch_all_tickers_public()
    symbols = TopMarketsUniverse().rank_from_tickers(tickers)[: args.symbols]
    print(f"Symbols: {len(symbols)} | API: {settings.COINEX_BASE_URL}", flush=True)

    windows: list[tuple[str, int, int]] = []
    if args.walk_forward:
        # ۶ پنجره ۴ روزه در ۹۰ روز گذشته (همه داخل ۳ ماه)
        for d_start in (85, 70, 55, 40, 28, 14):
            end = now - timedelta(days=d_start - args.window_days)
            start = now - timedelta(days=d_start)
            windows.append(
                (
                    f"WF_{d_start}d_ago",
                    int(start.timestamp() * 1000),
                    int(end.timestamp() * 1000),
                )
            )
    else:
        end = now - timedelta(days=args.days_ago_start - args.window_days)
        start = now - timedelta(days=args.days_ago_start)
        windows.append(
            (
                "PRIMARY_4D",
                int(start.timestamp() * 1000),
                int(end.timestamp() * 1000),
            )
        )

    t0 = time.time()
    results: list[WindowResult] = []
    for label, ws, we in windows:
        results.append(await run_window(symbols, ws, we, label))

    settings_snap = {
        "T0_MIN_PCT": settings.T0_MIN_PCT,
        "T0_MAX_PCT": settings.T0_MAX_PCT,
        "T1_MIN_VOLUME_RATIO": settings.T1_MIN_VOLUME_RATIO,
        "MIN_FILTERS_PASS": settings.MIN_FILTERS_PASS,
        "REQUIRED_FILTERS": settings.REQUIRED_FILTERS,
        "T6_COOLDOWN_DAYS": settings.T6_COOLDOWN_DAYS,
    }

    report = format_report(results, len(symbols), settings_snap)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "backtest_real_report.txt"
    json_path = REPORT_DIR / "backtest_real_signals.json"

    payload = {
        "generated_at": now.isoformat(),
        "api": settings.COINEX_BASE_URL,
        "settings": settings_snap,
        "aggregate": aggregate_stats(results),
        "windows": [
            {
                "label": r.label,
                "start": datetime.fromtimestamp(r.start_ms / 1000, tz=timezone.utc).isoformat(),
                "end": datetime.fromtimestamp(r.end_ms / 1000, tz=timezone.utc).isoformat(),
                "symbols_loaded": r.symbols_loaded,
                "signals": [
                    {
                        "market": s.market,
                        "ts": datetime.fromtimestamp(s.ts / 1000, tz=timezone.utc).isoformat(),
                        "price": s.price,
                        "t0_chg": s.t0_chg,
                        "pass_count": s.pass_count,
                        "ret_1h": s.ret_1h,
                        "ret_6h": s.ret_6h,
                        "ret_12h": s.ret_12h,
                        "ret_24h": s.ret_24h,
                    }
                    for s in r.signals
                ],
            }
            for r in results
        ],
    }

    report_path.write_text(report, encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + report)
    print(f"\nSaved: {report_path}", flush=True)
    print(f"Saved: {json_path}", flush=True)
    print(f"Total time: {time.time()-t0:.1f}s", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
