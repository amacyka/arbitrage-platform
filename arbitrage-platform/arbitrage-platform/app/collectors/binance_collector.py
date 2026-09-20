from __future__ import annotations

import asyncio
import traceback

from sqlalchemy import select

from app.config import settings
from app.database.db import SessionLocal
from app.database.models import MarketSnapshot
from app.exchanges.binance import BinanceClient
from app.normalizer import normalize_binance_book_ticker

_client = BinanceClient(settings.binance_api_base_url)


async def _resolve_tradable_symbols() -> dict[str, dict]:
    """Ask Binance which of our tracked assets actually have a live
    <ASSET><QUOTE> spot symbol, and pull their LOT_SIZE filter.

    Returns {asset: {"symbol": str, "min_qty": float, "max_qty": float}}.
    Never assumes a symbol exists — only exchangeInfo's own answer counts.
    """
    info = await _client.exchange_info()
    wanted = {a.strip().upper() for a in settings.tracked_assets.split(",") if a.strip()}
    quote = settings.quote_asset.upper()

    resolved: dict[str, dict] = {}
    for sym in info.get("symbols", []):
        if sym.get("status") != "TRADING":
            continue
        if sym.get("quoteAsset") != quote:
            continue
        base = sym.get("baseAsset")
        if base not in wanted:
            continue

        min_qty = max_qty = None
        for f in sym.get("filters", []):
            if f.get("filterType") == "LOT_SIZE":
                min_qty = float(f["minQty"])
                max_qty = float(f["maxQty"])

        resolved[base] = {"symbol": sym["symbol"], "min_qty": min_qty, "max_qty": max_qty}

    missing = wanted - resolved.keys()
    if missing:
        print(f"[binance_collector] no {quote} spot symbol found for: {sorted(missing)} — skipping them")

    return resolved


async def _collect_once(symbols: dict[str, dict]) -> None:
    async with SessionLocal() as session:
        for asset, meta in symbols.items():
            try:
                book = await _client.book_ticker(meta["symbol"])
                ticker24h = await _client.ticker_24h(meta["symbol"])

                quote = normalize_binance_book_ticker(
                    book_ticker=book,
                    base_asset=asset,
                    quote_asset=settings.quote_asset,
                    taker_fee=settings.binance_taker_fee,
                    min_qty=meta["min_qty"],
                    max_qty=meta["max_qty"],
                    volume_24h_quote=float(ticker24h["quoteVolume"]) if ticker24h.get("quoteVolume") else None,
                    last_price=float(ticker24h["lastPrice"]) if ticker24h.get("lastPrice") else None,
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
                # One symbol failing must never take down the whole collector.
                print(f"[binance_collector] error collecting {asset}:")
                traceback.print_exc()

        await session.commit()


async def run_collector() -> None:
    symbols: dict[str, dict] = {}
    refresh_every = 300  # re-check exchangeInfo every 5 minutes, not every cycle
    cycles_since_refresh = refresh_every

    while True:
        try:
            if cycles_since_refresh >= refresh_every:
                symbols = await _resolve_tradable_symbols()
                cycles_since_refresh = 0

            if symbols:
                await _collect_once(symbols)

        except Exception:
            print("[binance_collector] top-level error (continuing):")
            traceback.print_exc()

        cycles_since_refresh += settings.collect_interval_seconds
        await asyncio.sleep(settings.collect_interval_seconds)
