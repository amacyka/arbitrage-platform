"""Standalone entrypoint that runs collectors + scanner + Telegram bot
without the FastAPI web layer. Useful for local development or a
deployment target that supports a real background-worker process type.

For Render's free tier (no worker service type), app/web.py bundles all
of this into the single web process instead — see render.yaml.
"""
from __future__ import annotations

import asyncio

from app.config import settings
from app.database.db import init_db


async def main() -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    await init_db()

    from aiogram import Bot, Dispatcher

    from app.bot.handlers import router
    from app.bot.notifier import setup_notifier
    from app.collectors.binance_collector import run_collector as run_binance
    from app.collectors.bybit_collector import run_collector as run_bybit
    from app.engine.scanner import run_scanner

    bot = Bot(settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    setup_notifier(bot)

    await asyncio.gather(
        run_binance(),
        run_bybit(),
        run_scanner(),
        dp.start_polling(bot),
    )


if __name__ == "__main__":
    asyncio.run(main())
