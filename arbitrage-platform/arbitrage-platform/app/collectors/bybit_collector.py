from __future__ import annotations

import asyncio
import traceback

from app.config import settings
from app.database.db import SessionLocal
from app.database.models import MarketSnapshot
from app.exchanges.bybit import BybitClient
from app.normalizer import normalize_bybit_ticker

_client = BybitClient(settings.bybit_api_base_url)


async def _resolve_tradable_symbols() -> dict[str, dict]:
    """Ask Bybit which of our tracked assets have a live spot <ASSET><QUOTE>
    symbol, and pull their lotSizeFilter. Never assumes a pair exists.
    """
    info = await _client.instruments_info()
    wanted = {a.strip().upper() for a in settings.tracked_assets.split(",") if a.strip()}
    quote = settings.quote_asset.upper()

    resolved: dict[str, dict] = {}
    for item in info.get("result", {}).get("list", []):
        if item.get("status") != "Trading":
            continue
        if item.get("quoteCoin") != quote:
            continue
        base = item.get("baseCoin")
        if base not in wanted:
            continue

        lot = item.get("lotSizeFilter", {})
        min_qty = float(lot["minOrderQty"]) if lot.get("minOrderQty") else None
        max_qty = float(lot["maxOrderQty"]) if lot.get("maxOrderQty") else None

        resolved[base] = {"symbol": item["symbol"], "min_qty": min_qty, "max_qty": max_qty}

    missing = wanted - resolved.keys()
    if missing:
        print(f"[bybit_collector] no {quote} spot symbol found for: {sorted(missing)} — skipping them")

    return resolved


async def _collect_once(symbols: dict[str, dict]) -> None:
    async with SessionLocal() as session:
        for asset, meta in symbols.items():
            try:
                data = await _client.tickers(meta["symbol"])
                tickers = data.get("result", {}).get("list", [])
                if not tickers:
                    continue
                ticker = tickers[0]

                quote = normalize_bybit_ticker(
                    ticker=ticker,
                    base_asset=asset,
                    quote_asset=settings.quote_asset,
                    taker_fee=settings.bybit_taker_fee,
                    min_qty=meta["min_qty"],
                    max_qty=meta["max_qty"],
                )

                session.add(
                    MarketSnapshot(
                        source=quote.source,
                        asset=quote.asset,
                        quote_asset=quote.quote_asset,
                        network=quote.network,
                        buy_price=quote.buy_price,
                        sell_price=quote.sell_price,
                        last_price=quote.last_price,
                        available_volume=quote.available_volume,
                        min_amount=quote.min_amount,
                        max_amount=quote.max_amount,
                        trading_fee=quote.trading_fee,
                        withdrawal_fee=quote.withdrawal_fee,
                        timestamp=quote.timestamp,
                    )
                )
            except Exception:
                print(f"[bybit_collector] error collecting {asset}:")
                traceback.print_exc()

        await session.commit()


async def run_collector() -> None:
    symbols: dict[str, dict] = {}
    refresh_every = 300
    cycles_since_refresh = refresh_every

    while True:
        try:
            if cycles_since_refresh >= refresh_every:
                symbols = await _resolve_tradable_symbols()
                cycles_since_refresh = 0

            if symbols:
                await _collect_once(symbols)

        except Exception:
            print("[bybit_collector] top-level error (continuing):")
            traceback.print_exc()

        cycles_since_refresh += settings.collect_interval_seconds
        await asyncio.sleep(settings.collect_interval_seconds)
