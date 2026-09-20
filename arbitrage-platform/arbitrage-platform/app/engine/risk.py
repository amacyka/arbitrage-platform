from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskResult:
    gross_profit: float
    estimated_fees: float
    estimated_slippage: float
    estimated_net_profit: float
    roi_pct: float


def estimate_slippage(*, capital_usdt: float, available_volume: float | None) -> float:
    """Simple, explicitly-approximate slippage model.

    We don't have real order-book depth per price level from bookTicker /
    v5 tickers (those only give best bid/ask, not the full book), so this
    is a conservative linear placeholder: slippage grows as the trade size
    approaches the available 24h volume, capped at 1% of capital. This is
    deliberately crude and should be replaced with a real order-book-depth
    model (via the depth/orderbook endpoints) before this number is trusted
    for anything beyond paper trading.
    """
    if not available_volume or available_volume <= 0:
        return capital_usdt * 0.005  # unknown liquidity -> assume 0.5%

    ratio = min(capital_usdt / available_volume, 1.0)
    return capital_usdt * 0.001 * (1 + ratio * 4)  # 0.1% .. 0.5% of capital


def evaluate(
    *,
    buy_price: float,
    sell_price: float,
    capital_usdt: float,
    buy_fee: float,
    sell_fee: float,
    available_volume: float | None,
) -> RiskResult:
    """Core formulas from section 13 of the spec doc.

    gross_spread is expressed here directly in USDT terms (gross_profit),
    since capital_usdt is the amount of quote-asset capital being deployed.
    """
    gross_spread_pct = (sell_price - buy_price) / buy_price
    gross_profit = gross_spread_pct * capital_usdt

    fees = capital_usdt * buy_fee + capital_usdt * sell_fee
    slippage = estimate_slippage(capital_usdt=capital_usdt, available_volume=available_volume)

    net_profit = gross_profit - fees - slippage
    roi_pct = (net_profit / capital_usdt) * 100 if capital_usdt else 0.0

    return RiskResult(
        gross_profit=gross_profit,
        estimated_fees=fees,
        estimated_slippage=slippage,
        estimated_net_profit=net_profit,
        roi_pct=roi_pct,
    )
