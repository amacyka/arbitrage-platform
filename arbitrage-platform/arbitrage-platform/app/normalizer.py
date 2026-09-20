from __future__ import annotations

import datetime as dt
from dataclasses import dataclass


@dataclass
class NormalizedQuote:
    """The unified quote format from section 9 of the spec doc.

    Every collector (Binance, Bybit, and later xRocket / CryptoBot) must
    produce this shape so the arbitrage engine never needs to know which
    source a quote came from.
    """

    source: str  # "BINANCE", "BYBIT", ...
    asset: str  # base asset, e.g. "BTC"
    quote_asset: str  # e.g. "USDT"
    network: str | None
    buy_price: float  # price a buyer pays on this source (best ask)
    sell_price: float  # price a seller receives on this source (best bid)
    last_price: float | None
    available_volume: float | None  # 24h quote-asset volume, best-effort
    min_amount: float | None
    max_amount: float | None
    trading_fee: float  # fraction, e.g. 0.001 for 0.1%
    withdrawal_fee: float | None
    timestamp: dt.datetime


def normalize_binance_book_ticker(
    *,
    book_ticker: dict,
    base_asset: str,
    quote_asset: str,
    taker_fee: float,
    min_qty: float | None = None,
    max_qty: float | None = None,
    volume_24h_quote: float | None = None,
    last_price: float | None = None,
) -> NormalizedQuote:
    return NormalizedQuote(
        source="BINANCE",
        asset=base_asset,
        quote_asset=quote_asset,
        network=None,  # Binance spot quotes aren't network-specific
        buy_price=float(book_ticker["askPrice"]),
        sell_price=float(book_ticker["bidPrice"]),
        last_price=last_price,
        available_volume=volume_24h_quote,
        min_amount=min_qty,
        max_amount=max_qty,
        trading_fee=taker_fee,
        withdrawal_fee=None,  # withdrawal fees are per-network and per-asset;
        # not fetched in the MVP (would need /sapi/v1/capital/config/getall,
        # which is a signed endpoint) — left as None rather than guessed.
        timestamp=dt.datetime.now(dt.timezone.utc),
    )


def normalize_bybit_ticker(
    *,
    ticker: dict,
    base_asset: str,
    quote_asset: str,
    taker_fee: float,
    min_qty: float | None = None,
    max_qty: float | None = None,
) -> NormalizedQuote:
    return NormalizedQuote(
        source="BYBIT",
        asset=base_asset,
        quote_asset=quote_asset,
        network=None,
        buy_price=float(ticker["ask1Price"]),
        sell_price=float(ticker["bid1Price"]),
        last_price=float(ticker["lastPrice"]) if ticker.get("lastPrice") else None,
        available_volume=float(ticker["volume24h"]) if ticker.get("volume24h") else None,
        min_amount=min_qty,
        max_amount=max_qty,
        trading_fee=taker_fee,
        withdrawal_fee=None,  # same caveat as Binance above
        timestamp=dt.datetime.now(dt.timezone.utc),
    )
