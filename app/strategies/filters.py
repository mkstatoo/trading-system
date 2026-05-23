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


def evaluate_t1_volume_ratio(ticker: dict, daily_klines: list[dict]) -> FilterResult:
    name = "T1 — حجم نسبی ≥5×"
    try:
        current_value = float(ticker.get("value", 0) or 0)
        if not daily_klines or len(daily_klines) < 6:
            return FilterResult("T1", name, FilterStatus.FAIL, "داده روزانه کافی نیست")
        values = [float(k.get("value", 0) or 0) for k in daily_klines]
        # میانگین حجم روزانه قبل از امروز
        avg_value = float(np.mean(values[:-1][-20:]))
        if avg_value <= 0:
            return FilterResult("T1", name, FilterStatus.FAIL, "میانگین حجم صفر")
        ratio = current_value / avg_value
        detail = f"حجم: ${current_value/1e6:.2f}M | نسبت: ~{ratio:.1f}×"
        if ratio >= settings.T1_MIN_VOLUME_RATIO:
            return FilterResult("T1", name, FilterStatus.PASS, detail)
        return FilterResult(
            "T1",
            name,
            FilterStatus.FAIL,
            f"{detail} — کمتر از آستانه {settings.T1_MIN_VOLUME_RATIO:.0f}×",
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
        return FilterResult("T2", name, FilterStatus.WARN, f"{detail} (اشباع خرید)")
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
    name = "T7 — EMA20 > EMA50"
    closes = daily["close"]
    if len(closes) < settings.T7_EMA_SLOW + 5:
        return FilterResult("T7", name, FilterStatus.FAIL, "کندل روزانه کافی نیست")
    ema20 = ind.ema_last(closes, settings.T7_EMA_FAST)
    ema50 = ind.ema_last(closes, settings.T7_EMA_SLOW)
    if ema20 is None or ema50 is None:
        return FilterResult("T7", name, FilterStatus.FAIL, "EMA محاسبه نشد")
    change_30d = None
    if len(closes) >= 30:
        change_30d = ((closes[-1] - closes[-30]) / closes[-30]) * 100
    ch = f" | 30d: {change_30d:+.1f}%" if change_30d is not None else ""
    detail = f"EMA20={ema20:.6g} EMA50={ema50:.6g}{ch}"
    if ema20 > ema50:
        return FilterResult("T7", name, FilterStatus.PASS, detail)
    return FilterResult("T7", name, FilterStatus.FAIL, f"روند نزولی — {detail}")


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
) -> FilterReport:
    price = float(ticker.get("last", 0) or 0)
    hourly = ind.klines_to_arrays(hourly_klines)
    daily = ind.klines_to_arrays(daily_klines)

    report = FilterReport(market=market)
    report.results = [
        evaluate_t1_volume_ratio(ticker, daily_klines),
        evaluate_t2_rsi(hourly),
        evaluate_t3_macd(hourly),
        evaluate_t4_bollinger(hourly, price),
        evaluate_t5_vwap(hourly, price),
        evaluate_t6_cooldown(market, has_recent_signal),
        evaluate_t7_ema_trend(daily),
        evaluate_t8_atr_squeeze(hourly),
    ]
    return report


def is_trade_allowed(report: FilterReport) -> bool:
    """همه فیلترها باید PASS باشند؛ WARN در T2/T8 = رد."""
    for r in report.results:
        if r.status != FilterStatus.PASS:
            return False
    return True
