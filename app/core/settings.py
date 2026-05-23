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
    TRADING_SYMBOLS: str = "BTCUSDT,ETHUSDT"
    SCAN_INTERVAL_SECONDS: int = 15

    # BullHunter strategy (momentum % above open)
    BULL_HUNTER_MOMENTUM_PCT: float = 0.5

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def symbol_list(self) -> list[str]:
        return [s.strip().upper() for s in self.TRADING_SYMBOLS.split(",") if s.strip()]


settings = Settings()
