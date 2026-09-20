from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, Boolean, DateTime, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class MarketSnapshot(Base):
    """One normalized quote for one asset on one source at one point in time.

    Matches the unified format from section 9 of the spec doc:
    Source, Asset, Network, Buy Price, Sell Price, Available Volume,
    Min Amount, Max Amount, Trading Fee, Withdrawal Fee, Timestamp.
    """

    __tablename__ = "market_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32), index=True)  # BINANCE / BYBIT / ...
    asset: Mapped[str] = mapped_column(String(32), index=True)  # e.g. BTC
    quote_asset: Mapped[str] = mapped_column(String(16))  # e.g. USDT
    network: Mapped[str | None] = mapped_column(String(32), nullable=True)

    buy_price: Mapped[float] = mapped_column(Numeric(24, 8))  # ask (what a buyer pays)
    sell_price: Mapped[float] = mapped_column(Numeric(24, 8))  # bid (what a seller gets)
    last_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)

    available_volume: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    min_amount: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    max_amount: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)

    trading_fee: Mapped[float] = mapped_column(Numeric(10, 6))  # fraction, e.g. 0.001
    withdrawal_fee: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)

    timestamp: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


class ArbitrageSignal(Base):
    __tablename__ = "arbitrage_signals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    asset: Mapped[str] = mapped_column(String(32), index=True)
    quote_asset: Mapped[str] = mapped_column(String(16))

    buy_source: Mapped[str] = mapped_column(String(32))
    sell_source: Mapped[str] = mapped_column(String(32))
    buy_price: Mapped[float] = mapped_column(Numeric(24, 8))
    sell_price: Mapped[float] = mapped_column(Numeric(24, 8))

    capital_usdt: Mapped[float] = mapped_column(Numeric(24, 8))
    gross_profit: Mapped[float] = mapped_column(Numeric(24, 8))
    estimated_fees: Mapped[float] = mapped_column(Numeric(24, 8))
    estimated_slippage: Mapped[float] = mapped_column(Numeric(24, 8))
    estimated_net_profit: Mapped[float] = mapped_column(Numeric(24, 8))
    roi_pct: Mapped[float] = mapped_column(Numeric(10, 4))

    volume_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    data_age_seconds: Mapped[float] = mapped_column(Numeric(10, 3))

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    signal_id: Mapped[int] = mapped_column(BigInteger, index=True)

    entry_price: Mapped[float] = mapped_column(Numeric(24, 8))
    exit_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    volume_usdt: Mapped[float] = mapped_column(Numeric(24, 8))
    fees_paid: Mapped[float] = mapped_column(Numeric(24, 8))
    estimated_profit: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    price_change_pct: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    signal_lifetime_seconds: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    result: Mapped[str] = mapped_column(String(16), default="OPEN")  # OPEN / WIN / LOSS

    opened_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    closed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserSettings(Base):
    __tablename__ = "user_settings"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    min_roi_pct: Mapped[float] = mapped_column(Numeric(10, 4), default=0.5)
    min_profit_usdt: Mapped[float] = mapped_column(Numeric(24, 8), default=20.0)
    min_volume_usdt: Mapped[float] = mapped_column(Numeric(24, 8), default=500.0)
    paper_balance_usdt: Mapped[float] = mapped_column(Numeric(24, 8), default=10000.0)
    sources_enabled: Mapped[str] = mapped_column(String(128), default="BINANCE,BYBIT")
