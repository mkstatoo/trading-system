"""Bull Hunter T1–T8 filter evaluation."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from app.core.settings import settings
from app.strategies import indicators as ind


class FilterStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"


@dataclass
class FilterResult:
    code: str
    name: str
    status: FilterStatus
    detail: str


@dataclass
class FilterReport:
    market: str
    results: list[FilterResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(r.status == FilterStatus.PASS for r in self.results)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if counts_as_pass(r))

    @property
    def strict_pass_count(self) -> int:
        return sum(1 for r in self.results if r.status == FilterStatus.PASS)

    def to_dict(self) -> dict:
        return {
            "market": self.market,
            "all_passed": self.all_passed,
            "passed_count": self.passed_count,
            "filters": [
                {
                    "code": r.code,
                    "name": r.name,
                    "status": r.status.value,
                    "detail": r.detail,
                }
                for r in self.results
            ],
        }


def evaluate_t0_micro_momentum(micro_klines: list[dict]) -> FilterResult:
    """رشد قیمت در ۲ دقیقه اخیر (دو کندل ۱ دقیقه‌ای)."""
    candles = settings.T0_MICRO_CANDLES
    name = f"T0 — رشد {candles} دقیقه (۱min)"
    if len(micro_klines) < candles + 1:
        return FilterResult("T0", name, FilterStatus.FAIL, "داده ۱min کافی نیست")
    try:
        p0 = float(micro_klines[-1 - candles]["close"])
        p1 = float(micro_klines[-1]["close"])
        if p0 <= 0:
            return FilterResult("T0", name, FilterStatus.FAIL, "قیمت پایه صفر")
        chg = ((p1 - p0) / p0) * 100
        detail = f"{candles}m: {chg:+.2f}% ({p0:.6g} → {p1:.6g})"
        if chg >= settings.T0_SPIKE_WARN_PCT:
            return FilterResult("T0", name, FilterStatus.FAIL, f"{detail} — پامپ شدید")
        if settings.T0_MIN_PCT <= chg <= settings.T0_MAX_PCT:
            return FilterResult("T0", name, FilterStatus.PASS, detail)
        if chg >= settings.T0_MIN_PCT:
            return FilterResult("T0", name, FilterStatus.WARN, f"{detail} — بالای {settings.T0_MAX_PCT}%")
        return FilterResult(
            "T0",
            name,
            FilterStatus.FAIL,
            f"{detail} — کمتر از {settings.T0_MIN_PCT}%",
        )
    except (TypeError, ValueError) as e:
        return FilterResult("T0", name, FilterStatus.FAIL, str(e))


def evaluate_t1_volume_ratio(
    ticker: dict,
    daily_klines: list[dict],
    hourly_klines: list[dict] | None = None,
) -> FilterResult:
    name = f"T1 — حجم نسبی ≥{settings.T1_MIN_VOLUME_RATIO:.0f}×"
    try:
        current_value = float(ticker.get("value", 0) or 0)
        if not daily_klines or len(daily_klines) < 6:
            return FilterResult("T1", name, FilterStatus.FAIL, "داده روزانه کافی نیست")
        values = [float(k.get("value", 0) or 0) for k in daily_klines]
        avg_value = float(np.mean(values[:-1][-20:]))
        if avg_value <= 0:
            return FilterResult("T1", name, FilterStatus.FAIL, "میانگین حجم صفر")
        ratio = current_value / avg_value
        detail = f"۲۴h: ${current_value/1e6:.2f}M | نسبت روزانه: ~{ratio:.1f}×"

        hourly_ratio = None
        if hourly_klines and len(hourly_klines) >= 24:
            hvals = [float(k.get("value", 0) or 0) for k in hourly_klines]
            recent = float(np.sum(hvals[-3:]))
            base = float(np.mean(hvals[-24:-3])) if len(hvals) >= 6 else float(np.mean(hvals[:-3]))
            if base > 0:
                hourly_ratio = recent / (base * 3)
                detail += f" | نسبت ۳h: ~{hourly_ratio:.1f}×"

        passed = ratio >= settings.T1_MIN_VOLUME_RATIO
        if not passed and hourly_ratio is not None:
            passed = hourly_ratio >= settings.T1_MIN_VOLUME_RATIO

        if passed:
            return FilterResult("T1", name, FilterStatus.PASS, detail)
        return FilterResult(
            "T1",
            name,
            FilterStatus.FAIL,
            f"{detail} — کمتر از {settings.T1_MIN_VOLUME_RATIO:.0f}×",
        )
    except Exception as e:
        return FilterResult("T1", name, FilterStatus.FAIL, str(e))


def evaluate_t2_rsi(hourly: dict[str, np.ndarray]) -> FilterResult:
    name = f"T2 — RSI({settings.T2_RSI_PERIOD}) بین {settings.T2_RSI_MIN:.0f}–{settings.T2_RSI_MAX:.0f}"
    closes = hourly["close"]
    val = ind.rsi(closes, settings.T2_RSI_PERIOD)
    if val is None:
        return FilterResult("T2", name, FilterStatus.FAIL, "RSI محاسبه نشد")
    detail = f"RSI: ~{val:.1f}"
    if settings.T2_RSI_MIN <= val <= settings.T2_RSI_MAX:
        return FilterResult("T2", name, FilterStatus.PASS, detail)
    if val > settings.T2_RSI_MAX:
        if val <= settings.T2_RSI_EXTREME:
            return FilterResult(
                "T2", name, FilterStatus.WARN, f"{detail} (اشباع — مجاز محتاط)"
            )
        return FilterResult("T2", name, FilterStatus.FAIL, f"{detail} (اشباع شدید ≥{settings.T2_RSI_EXTREME:.0f})")
    return FilterResult("T2", name, FilterStatus.FAIL, f"{detail} (ضعیف)")


def evaluate_t3_macd(hourly: dict[str, np.ndarray]) -> FilterResult:
    name = "T3 — MACD Histogram مثبت"
    hist = ind.macd_histogram(
        hourly["close"],
        settings.T3_MACD_FAST,
        settings.T3_MACD_SLOW,
        settings.T3_MACD_SIGNAL,
    )
    if hist is None:
        return FilterResult("T3", name, FilterStatus.FAIL, "MACD محاسبه نشد")
    detail = f"histogram: {hist:.6f}"
    if hist > 0:
        return FilterResult("T3", name, FilterStatus.PASS, detail)
    return FilterResult("T3", name, FilterStatus.FAIL, detail)


def evaluate_t4_bollinger(hourly: dict[str, np.ndarray], price: float) -> FilterResult:
    name = "T4 — Bollinger Breakout"
    bb = ind.bollinger_bands(hourly["close"], settings.T4_BB_PERIOD, settings.T4_BB_STD)
    if bb is None:
        return FilterResult("T4", name, FilterStatus.FAIL, "بولینگر محاسبه نشد")
    mid, upper, lower = bb
    detail = f"قیمت: ${price:.6g} | باند بالا: ~${upper:.6g}"
    if price > upper:
        return FilterResult("T4", name, FilterStatus.PASS, detail)
    if price > mid:
        return FilterResult("T4", name, FilterStatus.WARN, f"{detail} — بالای میانه، زیر باند بالا")
    return FilterResult("T4", name, FilterStatus.FAIL, detail)


def evaluate_t5_vwap(hourly: dict[str, np.ndarray], price: float) -> FilterResult:
    name = "T5 — قیمت بالاتر از VWAP"
    vwap_val = ind.vwap(hourly["high"], hourly["low"], hourly["close"], hourly["volume"])
    if vwap_val is None:
        return FilterResult("T5", name, FilterStatus.FAIL, "VWAP محاسبه نشد")
    detail = f"قیمت ${price:.6g} | VWAP ~${vwap_val:.6g}"
    if price > vwap_val:
        return FilterResult("T5", name, FilterStatus.PASS, detail)
    return FilterResult("T5", name, FilterStatus.FAIL, detail)


def evaluate_t6_cooldown(market: str, has_recent_signal: bool) -> FilterResult:
    name = f"T6 — فیلتر {settings.T6_COOLDOWN_DAYS} روزه"
    if has_recent_signal:
        return FilterResult(
            "T6",
            name,
            FilterStatus.FAIL,
            f"سیگنال در {settings.T6_COOLDOWN_DAYS} روز اخیر ثبت شده",
        )
    return FilterResult("T6", name, FilterStatus.PASS, "سابقه سیگنال پاک")


def evaluate_t7_ema_trend(daily: dict[str, np.ndarray]) -> FilterResult:
    name = f"T7 — EMA{settings.T7_EMA_FAST} صعودی (۵ روز)"
    closes = daily["close"]
    need = settings.T7_EMA_FAST + settings.T7_EMA_LOOKBACK_DAYS + 5
    if len(closes) < need:
        return FilterResult("T7", name, FilterStatus.FAIL, "کندل روزانه کافی نیست")
    ema_series = ind.ema(closes, settings.T7_EMA_FAST)
    if len(ema_series) < settings.T7_EMA_LOOKBACK_DAYS + 1:
        return FilterResult("T7", name, FilterStatus.FAIL, "EMA محاسبه نشد")
    ema_now = float(ema_series[-1])
    ema_prev = float(ema_series[-1 - settings.T7_EMA_LOOKBACK_DAYS])
    if ema_prev <= 0:
        return FilterResult("T7", name, FilterStatus.FAIL, "EMA قبلی صفر")
    rise_pct = ((ema_now - ema_prev) / ema_prev) * 100
    detail = f"EMA20: {ema_prev:.6g} → {ema_now:.6g} ({rise_pct:+.2f}% در {settings.T7_EMA_LOOKBACK_DAYS}d)"
    if rise_pct >= settings.T7_EMA_MIN_RISE_PCT:
        return FilterResult("T7", name, FilterStatus.PASS, detail)
    if rise_pct >= 0:
        return FilterResult("T7", name, FilterStatus.WARN, f"{detail} — صعود خفیف")
    return FilterResult("T7", name, FilterStatus.FAIL, f"EMA20 نزولی — {detail}")


def evaluate_t8_atr_squeeze(hourly: dict[str, np.ndarray]) -> FilterResult:
    name = "T8 — ATR Squeeze (انرژی آزاد)"
    ratio = ind.bollinger_width_ratio(
        hourly["close"], settings.T4_BB_PERIOD, settings.T4_BB_STD
    )
    atr_ratio = ind.atr_expansion_ratio(
        hourly["high"], hourly["low"], hourly["close"], settings.T8_ATR_PERIOD
    )
    if ratio is None and atr_ratio is None:
        return FilterResult("T8", name, FilterStatus.FAIL, "ATR/BB محاسبه نشد")
    parts = []
    passed = False
    if ratio is not None:
        parts.append(f"BB width ratio: {ratio:.2f}×")
        if ratio >= settings.T8_BB_WIDTH_EXPAND_RATIO:
            passed = True
    if atr_ratio is not None:
        parts.append(f"ATR ratio: {atr_ratio:.2f}×")
        if atr_ratio >= settings.T8_ATR_EXPAND_RATIO:
            passed = True
    detail = " | ".join(parts)
    if passed:
        if atr_ratio and atr_ratio > settings.T8_ATR_EXPAND_RATIO * 1.5:
            return FilterResult("T8", name, FilterStatus.WARN, f"{detail} — نوسان تیز")
        return FilterResult("T8", name, FilterStatus.PASS, detail)
    return FilterResult("T8", name, FilterStatus.FAIL, detail)


def run_all_filters(
    market: str,
    ticker: dict,
    hourly_klines: list[dict],
    daily_klines: list[dict],
    has_recent_signal: bool,
    micro_klines: list[dict] | None = None,
) -> FilterReport:
    price = float(ticker.get("last", 0) or 0)
    hourly = ind.klines_to_arrays(hourly_klines)
    daily = ind.klines_to_arrays(daily_klines)

    report = FilterReport(market=market)
    t0 = (
        evaluate_t0_micro_momentum(micro_klines)
        if micro_klines
        else FilterResult("T0", "T0", FilterStatus.FAIL, "بدون داده 1min")
    )
    report.results = [
        t0,
        evaluate_t1_volume_ratio(ticker, daily_klines, hourly_klines),
        evaluate_t2_rsi(hourly),
        evaluate_t3_macd(hourly),
        evaluate_t4_bollinger(hourly, price),
        evaluate_t5_vwap(hourly, price),
        evaluate_t6_cooldown(market, has_recent_signal),
        evaluate_t7_ema_trend(daily),
        evaluate_t8_atr_squeeze(hourly),
    ]
    return report


def counts_as_pass(result: FilterResult) -> bool:
    if result.status == FilterStatus.PASS:
        return True
    if result.status != FilterStatus.WARN:
        return False
    if result.code == "T2" and settings.T2_ALLOW_OVERBOUGHT_WARN:
        return True
    if result.code == "T4" and settings.T4_ALLOW_MID_WARN:
        return True
    if result.code == "T7" and settings.T7_ALLOW_MILD_WARN:
        return True
    return False


def _allowed_warn_codes() -> set[str]:
    codes = set()
    if settings.T2_ALLOW_OVERBOUGHT_WARN:
        codes.add("T2")
    if settings.T4_ALLOW_MID_WARN:
        codes.add("T4")
    if settings.T7_ALLOW_MILD_WARN:
        codes.add("T7")
    return codes


def is_trade_allowed(report: FilterReport) -> bool:
    """
    حداقل MIN_FILTERS_PASS از TOTAL_FILTERS؛ T0/T1/T2 اجباری.
    T0 فقط PASS (مومنتوم ۲ دقیقه ۱–۲٪)؛ T2 WARN مجاز؛ سایر WARN رد.
    """
    by_code = {r.code: r for r in report.results}
    required = settings.required_filter_codes

    t0 = by_code.get("T0")
    if not t0 or t0.status != FilterStatus.PASS:
        return False

    t1 = by_code.get("T1")
    if not t1 or t1.status != FilterStatus.PASS:
        return False

    t2 = by_code.get("T2")
    if not t2 or t2.status == FilterStatus.FAIL:
        return False
    if t2.status == FilterStatus.WARN and not settings.T2_ALLOW_OVERBOUGHT_WARN:
        return False

    for code in required:
        if code not in by_code:
            return False

    pass_count = sum(1 for r in report.results if counts_as_pass(r))
    if pass_count < settings.MIN_FILTERS_PASS:
        return False

    allowed_warn = _allowed_warn_codes()
    for r in report.results:
        if r.code in allowed_warn and r.status == FilterStatus.WARN:
            continue
        if r.status == FilterStatus.WARN:
            return False
    return True
