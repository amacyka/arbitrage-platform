from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Empty by default so the web process can start without a bot token;
    # the bot simply doesn't start if this is unset.
    telegram_bot_token: str = ""

    # --- Binance public REST API ---
    # Verified against https://developers.binance.com/docs/binance-spot-api-docs
    # on 2026-09-20. All endpoints used here are unauthenticated market data.
    binance_api_base_url: str = "https://api.binance.com"
    # PLACEHOLDER default (Binance's published "regular account" spot taker
    # fee as of 2026-09-20, see https://www.binance.com/en/fee/schedule).
    # Real fees depend on the user's account tier/BNB discount and are NOT
    # fetched automatically in the MVP (that requires signed/authenticated
    # requests, which are intentionally out of scope for stage 1).
    binance_taker_fee: float = 0.001

    # --- Bybit public REST API (v5) ---
    # Verified against https://bybit-exchange.github.io/docs/v5/intro
    # on 2026-09-20. All endpoints used here are unauthenticated (category=spot).
    bybit_api_base_url: str = "https://api.bybit.com"
    # PLACEHOLDER default, same caveat as binance_taker_fee above. See
    # https://www.bybit.com/en/rates/spot (checked 2026-09-20).
    bybit_taker_fee: float = 0.001

    collect_interval_seconds: int = 5

    # Comma-separated base assets to track against USDT on both Binance and
    # Bybit. This is a starting default, not a verified "these definitely
    # exist on both" claim — the collectors check each symbol's tradability
    # at runtime (via exchangeInfo / instruments-info) and simply skip any
    # symbol that isn't actually listed, rather than assuming it exists.
    tracked_assets: str = "BTC,ETH,SOL,BNB,XRP,TON,DOGE"
    quote_asset: str = "USDT"

    default_min_roi_pct: float = 0.5
    default_min_profit_usdt: float = 20.0
    default_min_volume_usdt: float = 500.0
    default_capital_usdt: float = 1000.0
    signal_cooldown_seconds: int = 120

    paper_trading_start_balance: float = 10000.0

    database_url: str = (
        "postgresql+asyncpg://arbitrage:arbitrage@postgres:5432/arbitrage"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        # Managed hosts (Render, Railway, Heroku-style) hand out plain
        # postgres:// or postgresql:// URLs. SQLAlchemy's async engine
        # needs the asyncpg driver spelled out.
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://") :]
        if v.startswith("postgresql://") and "+asyncpg" not in v:
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v


settings = Settings()
