from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.config import settings
from app.database.db import SessionLocal
from app.database.models import ArbitrageSignal, PaperTrade, UserSettings


async def get_or_create_user_settings(chat_id: int) -> UserSettings:
    async with SessionLocal() as session:
        row = await session.get(UserSettings, chat_id)
        if row is None:
            row = UserSettings(
                chat_id=chat_id,
                min_roi_pct=settings.default_min_roi_pct,
                min_profit_usdt=settings.default_min_profit_usdt,
                min_volume_usdt=settings.default_min_volume_usdt,
                paper_balance_usdt=settings.paper_trading_start_balance,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return row


async def open_paper_trade(chat_id: int, signal_id: int) -> PaperTrade | None:
    """Simulate opening a trade against a past signal.

    Deducts the signal's capital_usdt from the user's virtual balance and
    records entry price / fees, per section 13 ("Paper Trading") of the
    spec doc. No real money or real exchange account is touched anywhere
    in this function.
    """
    async with SessionLocal() as session:
        signal = await session.get(ArbitrageSignal, signal_id)
        if signal is None:
            return None

        user = await session.get(UserSettings, chat_id)
        if user is None:
            user = UserSettings(
                chat_id=chat_id,
                min_roi_pct=settings.default_min_roi_pct,
                min_profit_usdt=settings.default_min_profit_usdt,
                min_volume_usdt=settings.default_min_volume_usdt,
                paper_balance_usdt=settings.paper_trading_start_balance,
            )
            session.add(user)

        capital = float(signal.capital_usdt)
        if float(user.paper_balance_usdt) < capital:
            return None  # not enough virtual balance

        user.paper_balance_usdt = float(user.paper_balance_usdt) - capital

        trade = PaperTrade(
            chat_id=chat_id,
            signal_id=signal.id,
            entry_price=float(signal.buy_price),
            volume_usdt=capital,
            fees_paid=float(signal.estimated_fees),
            result="OPEN",
        )
        session.add(trade)
        await session.commit()
        await session.refresh(trade)
        return trade


async def close_paper_trade(trade_id: int, exit_price: float) -> PaperTrade | None:
    """Close a simulated trade at a given exit price and settle P&L back
    into the user's virtual balance."""
    async with SessionLocal() as session:
        trade = await session.get(PaperTrade, trade_id)
        if trade is None or trade.result != "OPEN":
            return None

        signal = await session.get(ArbitrageSignal, trade.signal_id)
        user = await session.get(UserSettings, trade.chat_id)

        entry_price = float(trade.entry_price)
        price_change_pct = ((exit_price - entry_price) / entry_price) * 100 if entry_price else 0.0

        volume_usdt = float(trade.volume_usdt)
        qty = volume_usdt / entry_price if entry_price else 0.0
        gross_pnl = qty * (exit_price - entry_price)
        estimated_profit = gross_pnl - float(trade.fees_paid)

        trade.exit_price = exit_price
        trade.estimated_profit = estimated_profit
        trade.price_change_pct = price_change_pct
        trade.result = "WIN" if estimated_profit > 0 else "LOSS"
        trade.closed_at = dt.datetime.now(dt.timezone.utc)
        if trade.opened_at:
            trade.signal_lifetime_seconds = (trade.closed_at - trade.opened_at).total_seconds()

        if user is not None:
            user.paper_balance_usdt = float(user.paper_balance_usdt) + volume_usdt + estimated_profit

        await session.commit()
        await session.refresh(trade)
        return trade


async def get_open_trades(chat_id: int) -> list[PaperTrade]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(PaperTrade).where(PaperTrade.chat_id == chat_id, PaperTrade.result == "OPEN")
        )
        return list(result.scalars())


async def get_trade_history(chat_id: int, limit: int = 20) -> list[PaperTrade]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(PaperTrade)
            .where(PaperTrade.chat_id == chat_id, PaperTrade.result != "OPEN")
            .order_by(PaperTrade.closed_at.desc())
            .limit(limit)
        )
        return list(result.scalars())
