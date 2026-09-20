from __future__ import annotations

import asyncio
import datetime as dt
import traceback

from sqlalchemy import desc, select

from app.config import settings
from app.database.db import SessionLocal
from app.database.models import ArbitrageSignal, MarketSnapshot
from app.engine.arbitrage import find_opportunities, passes_filters

SOURCES = ["BINANCE", "BYBIT"]

# In-memory cooldown tracker: (asset, buy_source, sell_source) -> last fired at.
# Simple and process-local, which is fine for the MVP's single-process
# deployment; would need to move to the DB or Redis for multi-instance.
_last_fired: dict[tuple[str, str, str], dt.datetime] = {}

# Callback registered by the bot to actually send Telegram messages.
# Kept decoupled so the scanner has no direct dependency on aiogram.
_on_signal_callbacks: list = []


def register_signal_callback(callback) -> None:
    _on_signal_callbacks.append(callback)


async def _latest_snapshots_by_asset() -> dict[str, dict[str, MarketSnapshot]]:
    """Return {asset: {source: latest MarketSnapshot}} across all sources."""
    grouped: dict[str, dict[str, MarketSnapshot]] = {}

    async with SessionLocal() as session:
        for source in SOURCES:
            result = await session.execute(
                select(MarketSnapshot)
                .where(MarketSnapshot.source == source)
                .order_by(desc(MarketSnapshot.timestamp))
            )
            seen_assets: set[str] = set()
            for row in result.scalars():
                if row.asset in seen_assets:
                    continue
                seen_assets.add(row.asset)
                grouped.setdefault(row.asset, {})[source] = row

    return grouped


async def _scan_once() -> None:
    by_asset = await _latest_snapshots_by_asset()

    async with SessionLocal() as session:
        for asset, by_source in by_asset.items():
            if len(by_source) < 2:
                continue  # need at least two sources to compare

            opportunities = find_opportunities(
                latest_by_source=by_source,
                default_capital_usdt=settings.default_capital_usdt,
                min_volume_usdt=settings.default_min_volume_usdt,
            )

            for opp in opportunities:
                if not passes_filters(
                    opp,
                    min_roi_pct=settings.default_min_roi_pct,
                    min_profit_usdt=settings.default_min_profit_usdt,
                    min_volume_usdt=settings.default_min_volume_usdt,
                ):
                    continue

                key = (opp.asset, opp.buy_source, opp.sell_source)
                now = dt.datetime.now(dt.timezone.utc)
                last = _last_fired.get(key)
                if last and (now - last).total_seconds() < settings.signal_cooldown_seconds:
                    continue
                _last_fired[key] = now

                signal = ArbitrageSignal(
                    asset=opp.asset,
                    quote_asset=opp.quote_asset,
                    buy_source=opp.buy_source,
                    sell_source=opp.sell_source,
                    buy_price=opp.buy_price,
                    sell_price=opp.sell_price,
                    capital_usdt=opp.capital_usdt,
                    gross_profit=opp.gross_profit,
                    estimated_fees=opp.estimated_fees,
                    estimated_slippage=opp.estimated_slippage,
                    estimated_net_profit=opp.estimated_net_profit,
                    roi_pct=opp.roi_pct,
                    volume_ok=opp.volume_ok,
                    data_age_seconds=opp.data_age_seconds,
                )
                session.add(signal)
                await session.flush()  # get signal.id before commit

                for callback in _on_signal_callbacks:
                    try:
                        await callback(signal)
                    except Exception:
                        print("[scanner] signal callback error:")
                        traceback.print_exc()

        await session.commit()


async def run_scanner() -> None:
    while True:
        try:
            await _scan_once()
        except Exception:
            print("[scanner] top-level error (continuing):")
            traceback.print_exc()

        await asyncio.sleep(settings.collect_interval_seconds)
