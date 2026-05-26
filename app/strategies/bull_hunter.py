import asyncio
from typing import Optional

from app.strategies.base import BaseStrategy
from app.strategies.filters import run_all_filters, is_trade_allowed, FilterReport
from app.exchanges.coinex.kline import fetch_klines
from app.storage import signal_history
from app.core.settings import settings
from app.core.logger import setup_logger

logger = setup_logger()


class BullHunterStrategy(BaseStrategy):
    """
    Bull Hunter — تشخیص بازار گاوی: T0 (رشد ۲دقیقه) + T1–T8 روی Top N.
    """

    def __init__(self, notional_base: float | None = None):
        self.notional_base = notional_base or settings.INITIAL_BALANCE

    async def evaluate(self, market_data: dict) -> FilterReport | None:
        market = market_data.get("market", "")
        if not market:
            return None

        micro_task = fetch_klines(
            market, settings.T0_MICRO_PERIOD, settings.KLINE_MICRO_LIMIT
        )
        hourly_task = fetch_klines(market, "1hour", settings.KLINE_HOURLY_LIMIT)
        daily_task = fetch_klines(market, "1day", settings.KLINE_DAILY_LIMIT)
        micro_klines, hourly_klines, daily_klines = await asyncio.gather(
            micro_task, hourly_task, daily_task
        )

        if len(micro_klines) < settings.T0_MICRO_CANDLES + 2:
            return None
        if len(hourly_klines) < 30 or len(daily_klines) < 10:
            return None

        recent = signal_history.has_recent_signal(market)
        return run_all_filters(
            market, market_data, hourly_klines, daily_klines, recent, micro_klines
        )

    async def analyze(self, market_data: dict) -> Optional[dict]:
        try:
            report = await self.evaluate(market_data)
            if report is None:
                return None

            if not is_trade_allowed(report):
                return None

            last_price = float(market_data.get("last", 0) or 0)
            if last_price <= 0:
                return None

            risk_per_trade = settings.RISK_PER_TRADE
            amount = round((self.notional_base * risk_per_trade) / last_price, 8)
            if amount <= 0:
                return None

            report_dict = report.to_dict()
            signal_history.record_signal(report.market, report_dict)

            return {
                "symbol": report.market,
                "price": last_price,
                "amount": amount,
                "side": "buy",
                "reason": f"Bull Hunter {report.passed_count}/{settings.TOTAL_FILTERS} (min {settings.MIN_FILTERS_PASS})",
                "filters": report_dict,
            }
        except Exception as e:
            logger.error("bull hunter analyze error [%s]: %s", market_data.get("market"), e)
            return None
