from __future__ import annotations

import asyncio

from fastapi import FastAPI
from sqlalchemy import desc, select

from app.config import settings
from app.database.db import SessionLocal, init_db
from app.database.models import ArbitrageSignal, MarketSnapshot

app = FastAPI(title="Crypto Arbitrage Intelligence Platform")


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()

    from app.collectors.binance_collector import run_collector as run_binance
    from app.collectors.bybit_collector import run_collector as run_bybit
    from app.engine.scanner import run_scanner

    app.state.binance_task = asyncio.create_task(run_binance())
    app.state.bybit_task = asyncio.create_task(run_bybit())
    app.state.scanner_task = asyncio.create_task(run_scanner())

    if settings.telegram_bot_token:
        from aiogram import Bot, Dispatcher

        from app.bot.handlers import router
        from app.bot.notifier import setup_notifier

        bot = Bot(settings.telegram_bot_token)
        dp = Dispatcher()
        dp.include_router(router)

        setup_notifier(bot)

        app.state.bot = bot
        app.state.bot_task = asyncio.create_task(dp.start_polling(bot))
        print("[web] Telegram bot polling started.")
    else:
        print("[web] TELEGRAM_BOT_TOKEN not set — running collectors and scanner only, no Telegram bot.")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    for attr in ("binance_task", "bybit_task", "scanner_task", "bot_task"):
        task = getattr(app.state, attr, None)
        if task is not None:
            task.cancel()

    bot = getattr(app.state, "bot", None)
    if bot is not None:
        await bot.session.close()


@app.get("/")
async def index() -> dict:
    return {
        "service": "Crypto Arbitrage Intelligence Platform",
        "stage": "MVP: Binance <-> Bybit",
        "status": "running",
    }


@app.get("/api/market")
async def market() -> dict:
    async with SessionLocal() as session:
        result = await session.execute(
            select(MarketSnapshot).order_by(desc(MarketSnapshot.timestamp)).limit(50)
        )
        rows = list(result.scalars())

    seen: set[tuple[str, str]] = set()
    unique_rows = []
    for row in rows:
        key = (row.source, row.asset)
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(row)

    return {
        "points": [
            {
                "source": r.source,
                "asset": r.asset,
                "quote_asset": r.quote_asset,
                "bid": float(r.sell_price),
                "ask": float(r.buy_price),
                "last_price": float(r.last_price) if r.last_price is not None else None,
                "volume_24h": float(r.available_volume) if r.available_volume is not None else None,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in unique_rows
        ]
    }


@app.get("/api/signals")
async def signals(limit: int = 20) -> dict:
    limit = max(1, min(limit, 200))
    async with SessionLocal() as session:
        result = await session.execute(
            select(ArbitrageSignal).order_by(desc(ArbitrageSignal.created_at)).limit(limit)
        )
        rows = list(result.scalars())

    return {
        "signals": [
            {
                "id": r.id,
                "asset": r.asset,
                "quote_asset": r.quote_asset,
                "buy_source": r.buy_source,
                "sell_source": r.sell_source,
                "buy_price": float(r.buy_price),
                "sell_price": float(r.sell_price),
                "capital_usdt": float(r.capital_usdt),
                "estimated_net_profit": float(r.estimated_net_profit),
                "roi_pct": float(r.roi_pct),
                "volume_ok": r.volume_ok,
                "data_age_seconds": float(r.data_age_seconds),
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    }
