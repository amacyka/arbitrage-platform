from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from itertools import permutations

from app.database.models import MarketSnapshot
from app.engine.risk import evaluate


@dataclass
class Opportunity:
    asset: str
    quote_asset: str
    buy_source: str
    sell_source: str
    buy_price: float
    sell_price: float
    capital_usdt: float
    gross_profit: float
    estimated_fees: float
    estimated_slippage: float
    estimated_net_profit: float
    roi_pct: float
    volume_ok: bool
    data_age_seconds: float


def find_opportunities(
    *,
    latest_by_source: dict[str, MarketSnapshot],
    default_capital_usdt: float,
    min_volume_usdt: float,
    now: dt.datetime | None = None,
) -> list[Opportunity]:
    """Compare every ordered pair of sources for one asset.

    latest_by_source: {"BINANCE": MarketSnapshot, "BYBIT": MarketSnapshot, ...}
    for a single asset — direction matters, so (BINANCE, BYBIT) and
    (BYBIT, BINANCE) are evaluated as two distinct opportunities, per
    section 4 of the spec doc.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    results: list[Opportunity] = []

    for buy_source, sell_source in permutations(latest_by_source.keys(), 2):
        buy_snap = latest_by_source[buy_source]
        sell_snap = latest_by_source[sell_source]

        buy_price = float(buy_snap.buy_price)
        sell_price = float(sell_snap.sell_price)

        if buy_price <= 0 or sell_price <= buy_price:
            continue  # only consider directions with a positive raw spread

        available_volume = min(
            float(buy_snap.available_volume or 0),
            float(sell_snap.available_volume or 0),
        ) or None

        risk = evaluate(
            buy_price=buy_price,
            sell_price=sell_price,
            capital_usdt=default_capital_usdt,
            buy_fee=float(buy_snap.trading_fee),
            sell_fee=float(sell_snap.trading_fee),
            available_volume=available_volume,
        )

        data_age = max(
            (now - buy_snap.timestamp).total_seconds(),
            (now - sell_snap.timestamp).total_seconds(),
        )

        results.append(
            Opportunity(
                asset=buy_snap.asset,
                quote_asset=buy_snap.quote_asset,
                buy_source=buy_source,
                sell_source=sell_source,
                buy_price=buy_price,
                sell_price=sell_price,
                capital_usdt=default_capital_usdt,
                gross_profit=risk.gross_profit,
                estimated_fees=risk.estimated_fees,
                estimated_slippage=risk.estimated_slippage,
                estimated_net_profit=risk.estimated_net_profit,
                roi_pct=risk.roi_pct,
                volume_ok=bool(available_volume and available_volume >= min_volume_usdt),
                data_age_seconds=data_age,
            )
        )

    return results


def passes_filters(
    opp: Opportunity,
    *,
    min_roi_pct: float,
    min_profit_usdt: float,
    min_volume_usdt: float,
) -> bool:
    """A signal only fires when ALL three thresholds are met (section 13)."""
    return (
        opp.roi_pct >= min_roi_pct
        and opp.estimated_net_profit >= min_profit_usdt
        and opp.volume_ok
    )
