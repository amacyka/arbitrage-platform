from __future__ import annotations

from app.database.models import ArbitrageSignal

SOURCE_LABELS = {
    "BINANCE": "Binance",
    "BYBIT": "Bybit",
    "XROCKET": "Хрокет",
    "CRYPTOBOT": "Крипто Бот",
}


def format_signal(signal: ArbitrageSignal) -> str:
    """Alert text following the exact layout from section 12 of the spec doc."""
    buy_label = SOURCE_LABELS.get(signal.buy_source, signal.buy_source)
    sell_label = SOURCE_LABELS.get(signal.sell_source, signal.sell_source)

    status = "🟢 ACTIVE" if signal.data_age_seconds < 5 else "🟡 STALE"
    volume_status = "OK" if signal.volume_ok else "LOW"

    return (
        f"🔥 ARBITRAGE\n"
        f"{signal.asset}/{signal.quote_asset}\n\n"
        f"BUY {buy_label} {float(signal.buy_price):,.4f} {signal.quote_asset}\n"
        f"SELL {sell_label} {float(signal.sell_price):,.4f} {signal.quote_asset}\n\n"
        f"Capital: {float(signal.capital_usdt):,.2f} {signal.quote_asset}\n"
        f"Gross Profit: {float(signal.gross_profit):,.2f} {signal.quote_asset}\n"
        f"Estimated Fees: {float(signal.estimated_fees):,.2f} {signal.quote_asset}\n"
        f"Estimated Slippage: {float(signal.estimated_slippage):,.2f} {signal.quote_asset}\n"
        f"Estimated Net Profit: {float(signal.estimated_net_profit):,.2f} {signal.quote_asset}\n"
        f"ROI: {float(signal.roi_pct):.2f}%\n"
        f"Volume: {volume_status}\n"
        f"Data Age: {signal.data_age_seconds:.1f} sec\n"
        f"Status: {status}\n\n"
        f"⚠️ Это аналитический сигнал, а не гарантия получения указанной прибыли."
    )
