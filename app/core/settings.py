from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    COINEX_ACCESS_ID: str = "YOUR_ACCESS_ID"
    COINEX_SECRET_KEY: str = "YOUR_SECRET_KEY"
    COINEX_BASE_URL: str = "https://api.coinex.com"
    DATABASE_URL: str = "sqlite:///trading.db"

    # Risk
    RISK_PER_TRADE: float = 0.01
    MAX_DAILY_LOSS: float = 0.03
    MAX_OPEN_TRADES: int = 5
    INITIAL_BALANCE: float = 10_000.0

    # Trading mode
    PAPER_TRADING: bool = True
    AUTO_TRADING: bool = True
    SYMBOL_MODE: str = "top300"
    TOP_MARKETS_COUNT: int = 300
    TOP_MARKETS_REFRESH_HOURS: int = 6
    TRADING_SYMBOLS: str = "BTCUSDT,ETHUSDT"
    SCAN_INTERVAL_SECONDS: int = 180
    KLINE_CONCURRENCY: int = 12
    KLINE_HOURLY_LIMIT: int = 100
    KLINE_DAILY_LIMIT: int = 60

    # T1 — حجم نسبی
    T1_MIN_VOLUME_RATIO: float = 5.0

    # T2 — RSI
    T2_RSI_PERIOD: int = 7
    T2_RSI_MIN: float = 45.0
    T2_RSI_MAX: float = 70.0

    # T3 — MACD
    T3_MACD_FAST: int = 12
    T3_MACD_SLOW: int = 26
    T3_MACD_SIGNAL: int = 9

    # T4 — Bollinger
    T4_BB_PERIOD: int = 20
    T4_BB_STD: float = 2.0

    # T6 — cooldown
    T6_COOLDOWN_DAYS: int = 5

    # T7 — EMA trend (daily)
    T7_EMA_FAST: int = 20
    T7_EMA_SLOW: int = 50

    # T8 — squeeze release
    T8_ATR_PERIOD: int = 14
    T8_BB_WIDTH_EXPAND_RATIO: float = 1.2
    T8_ATR_EXPAND_RATIO: float = 1.1

    HOST: str = "127.0.0.1"
    PORT: int = 7000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def use_top_markets(self) -> bool:
        return self.SYMBOL_MODE.strip().lower() in ("top300", "top", "auto")

    @property
    def symbol_list(self) -> list[str]:
        if self.use_top_markets:
            return []
        return [s.strip().upper() for s in self.TRADING_SYMBOLS.split(",") if s.strip()]


settings = Settings()
