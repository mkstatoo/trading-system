"""Technical indicators for Bull Hunter T1–T8 (numpy)."""
from __future__ import annotations

import numpy as np


def ema(values: np.ndarray, period: int) -> np.ndarray:
    if len(values) < period:
        return np.array([])
    alpha = 2.0 / (period + 1)
    out = np.empty(len(values))
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return out


def rsi(closes: np.ndarray, period: int = 7) -> float | None:
    if len(closes) < period + 1:
        return None
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = float(np.mean(gains[-period:]))
    avg_loss = float(np.mean(losses[-period:]))
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def macd_histogram(
    closes: np.ndarray,
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> float | None:
    if len(closes) < slow + signal_period:
        return None
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal_period)
    if len(macd_line) == 0 or len(signal_line) == 0:
        return None
    return float(macd_line[-1] - signal_line[-1])


def bollinger_bands(
    closes: np.ndarray,
    period: int = 20,
    num_std: float = 2.0,
) -> tuple[float, float, float] | None:
    if len(closes) < period:
        return None
    window = closes[-period:]
    mid = float(np.mean(window))
    std = float(np.std(window))
    return mid, mid + num_std * std, mid - num_std * std


def bollinger_width_ratio(closes: np.ndarray, period: int = 20, num_std: float = 2.0) -> float | None:
    if len(closes) < period * 2:
        return None
    widths = []
    for i in range(period, len(closes) + 1):
        w = closes[i - period : i]
        mid = float(np.mean(w))
        if mid <= 0:
            continue
        std = float(np.std(w))
        widths.append((2 * num_std * std) / mid)
    if len(widths) < 2:
        return None
    recent = widths[-1]
    avg = float(np.mean(widths[:-1]))
    if avg <= 0:
        return None
    return recent / avg


def vwap(high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray) -> float | None:
    if len(close) == 0 or float(np.sum(volume)) <= 0:
        return None
    typical = (high + low + close) / 3.0
    return float(np.sum(typical * volume) / np.sum(volume))


def ema_last(closes: np.ndarray, period: int) -> float | None:
    series = ema(closes, period)
    if len(series) == 0:
        return None
    return float(series[-1])


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> float | None:
    if len(close) < period + 1:
        return None
    trs = []
    for i in range(1, len(close)):
        tr = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )
        trs.append(tr)
    tr_arr = np.array(trs)
    if len(tr_arr) < period:
        return None
    return float(np.mean(tr_arr[-period:]))


def atr_expansion_ratio(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 14,
    lookback: int = 20,
) -> float | None:
    if len(close) < period + lookback:
        return None
    current = atr(high, low, close, period)
    if current is None:
        return None
    past_atrs = []
    for end in range(period + 1, len(close)):
        sl = close[:end]
        sh = high[:end]
        slw = low[:end]
        a = atr(sh, slw, sl, period)
        if a is not None:
            past_atrs.append(a)
    if not past_atrs:
        return None
    avg = float(np.mean(past_atrs[-lookback:]))
    if avg <= 0:
        return None
    return current / avg


def klines_to_arrays(klines: list[dict]) -> dict[str, np.ndarray]:
    if not klines:
        return {
            "open": np.array([]),
            "high": np.array([]),
            "low": np.array([]),
            "close": np.array([]),
            "volume": np.array([]),
            "value": np.array([]),
        }
    return {
        "open": np.array([float(k["open"]) for k in klines], dtype=float),
        "high": np.array([float(k["high"]) for k in klines], dtype=float),
        "low": np.array([float(k["low"]) for k in klines], dtype=float),
        "close": np.array([float(k["close"]) for k in klines], dtype=float),
        "volume": np.array([float(k["volume"]) for k in klines], dtype=float),
        "value": np.array([float(k.get("value", 0) or 0) for k in klines], dtype=float),
    }
