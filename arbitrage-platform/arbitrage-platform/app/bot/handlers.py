from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

from app.bot.formatting import format_signal
from app.database.db import SessionLocal
from app.database.models import ArbitrageSignal, UserSettings
from app.paper_trading import (
    get_open_trades,
    get_or_create_user_settings,
    get_trade_history,
    open_paper_trade,
)

router = Router()

MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔎 Найти возможности"), KeyboardButton(text="📈 Рынок")],
        [KeyboardButton(text="⚡ Активные сигналы"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="💰 Paper Trading"), KeyboardButton(text="⚙️ Настройки")],
    ],
    resize_keyboard=True,
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user = await get_or_create_user_settings(message.chat.id)
    await message.answer(
        "📊 Crypto Arbitrage Intelligence Platform\n\n"
        "Этап MVP: Binance ↔ Bybit, без реальных сделок.\n"
        f"Виртуальный баланс (Paper Trading): {float(user.paper_balance_usdt):,.2f} USDT\n\n"
        "Выберите действие:",
        reply_markup=MAIN_MENU,
    )


@router.message(Command("settings"))
@router.message(F.text == "⚙️ Настройки")
async def cmd_settings(message: Message) -> None:
    user = await get_or_create_user_settings(message.chat.id)
    await message.answer(
        "⚙️ Текущие настройки:\n\n"
        f"Минимальный ROI: {float(user.min_roi_pct):.2f}%\n"
        f"Минимальная прибыль: {float(user.min_profit_usdt):,.2f} USDT\n"
        f"Минимальный объём: {float(user.min_volume_usdt):,.2f} USDT\n"
        f"Источники: {user.sources_enabled}\n\n"
        "Изменение настроек через команды (в этой MVP-версии):\n"
        "/set_roi 0.5\n"
        "/set_profit 20\n"
        "/set_volume 500"
    )


def _parse_float_arg(message: Message) -> float | None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        return None
    try:
        return float(parts[1].replace(",", "."))
    except ValueError:
        return None


@router.message(Command("set_roi"))
async def cmd_set_roi(message: Message) -> None:
    value = _parse_float_arg(message)
    if value is None:
        await message.answer("Использование: /set_roi 0.5")
        return
    await get_or_create_user_settings(message.chat.id)
    async with SessionLocal() as session:
        db_user = await session.get(UserSettings, message.chat.id)
        db_user.min_roi_pct = value
        await session.commit()
    await message.answer(f"Минимальный ROI установлен: {value}%")


@router.message(Command("set_profit"))
async def cmd_set_profit(message: Message) -> None:
    value = _parse_float_arg(message)
    if value is None:
        await message.answer("Использование: /set_profit 20")
        return
    await get_or_create_user_settings(message.chat.id)
    async with SessionLocal() as session:
        db_user = await session.get(UserSettings, message.chat.id)
        db_user.min_profit_usdt = value
        await session.commit()
    await message.answer(f"Минимальная прибыль установлена: {value} USDT")


@router.message(Command("set_volume"))
async def cmd_set_volume(message: Message) -> None:
    value = _parse_float_arg(message)
    if value is None:
        await message.answer("Использование: /set_volume 500")
        return
    await get_or_create_user_settings(message.chat.id)
    async with SessionLocal() as session:
        db_user = await session.get(UserSettings, message.chat.id)
        db_user.min_volume_usdt = value
        await session.commit()
    await message.answer(f"Минимальный объём установлен: {value} USDT")


@router.message(F.text.in_({"🔎 Найти возможности", "⚡ Активные сигналы"}))
async def show_recent_signals(message: Message) -> None:
    async with SessionLocal() as session:
        from sqlalchemy import desc, select

        result = await session.execute(
            select(ArbitrageSignal).order_by(desc(ArbitrageSignal.created_at)).limit(5)
        )
        signals = list(result.scalars())

    if not signals:
        await message.answer(
            "Пока нет ни одного сигнала, прошедшего фильтры. "
            "Система продолжает сканировать Binance ↔ Bybit."
        )
        return

    for signal in signals:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💰 Paper Trade", callback_data=f"paper_trade:{signal.id}")]
            ]
        )
        await message.answer(format_signal(signal), reply_markup=keyboard)


@router.callback_query(F.data.startswith("paper_trade:"))
async def handle_paper_trade(callback: CallbackQuery) -> None:
    signal_id = int(callback.data.split(":", 1)[1])
    trade = await open_paper_trade(callback.message.chat.id, signal_id)

    if trade is None:
        await callback.answer("Недостаточно виртуального баланса или сигнал не найден", show_alert=True)
        return

    await callback.answer("Виртуальная сделка открыта ✅")
    await callback.message.answer(
        f"💰 Paper Trade открыт (#{trade.id})\n"
        f"Вход: {float(trade.entry_price):,.4f}\n"
        f"Объём: {float(trade.volume_usdt):,.2f} USDT\n"
        f"Комиссии: {float(trade.fees_paid):,.2f} USDT"
    )


@router.message(F.text == "💰 Paper Trading")
async def show_paper_trading(message: Message) -> None:
    user = await get_or_create_user_settings(message.chat.id)
    open_trades = await get_open_trades(message.chat.id)
    history = await get_trade_history(message.chat.id, limit=5)

    lines = [f"💰 Виртуальный баланс: {float(user.paper_balance_usdt):,.2f} USDT\n"]

    if open_trades:
        lines.append("Открытые сделки:")
        for t in open_trades:
            lines.append(f"  #{t.id}: вход {float(t.entry_price):,.4f}, объём {float(t.volume_usdt):,.2f} USDT")
    else:
        lines.append("Открытых сделок нет.")

    if history:
        lines.append("\nПоследние закрытые сделки:")
        for t in history:
            lines.append(
                f"  #{t.id}: {t.result}, P&L {float(t.estimated_profit or 0):,.2f} USDT"
            )

    await message.answer("\n".join(lines))


@router.message(Command("stats"))
@router.message(F.text == "📊 Статистика")
async def show_stats(message: Message) -> None:
    history = await get_trade_history(message.chat.id, limit=100)
    if not history:
        await message.answer("Пока нет завершённых paper-сделок для статистики.")
        return

    wins = sum(1 for t in history if t.result == "WIN")
    losses = sum(1 for t in history if t.result == "LOSS")
    total_pnl = sum(float(t.estimated_profit or 0) for t in history)

    await message.answer(
        f"📊 Статистика Paper Trading\n\n"
        f"Всего сделок: {len(history)}\n"
        f"WIN: {wins} / LOSS: {losses}\n"
        f"Суммарный P&L: {total_pnl:,.2f} USDT"
    )


@router.message(F.text == "📈 Рынок")
async def show_market(message: Message) -> None:
    async with SessionLocal() as session:
        from sqlalchemy import desc, select

        from app.database.models import MarketSnapshot

        result = await session.execute(
            select(MarketSnapshot).order_by(desc(MarketSnapshot.timestamp)).limit(20)
        )
        rows = list(result.scalars())

    if not rows:
        await message.answer("Данные ещё собираются, попробуйте через несколько секунд.")
        return

    seen: set[tuple[str, str]] = set()
    lines = ["📈 Последние котировки:\n"]
    for row in rows:
        key = (row.source, row.asset)
        if key in seen:
            continue
        seen.add(key)
        lines.append(
            f"{row.source} {row.asset}/{row.quote_asset}: "
            f"bid {float(row.sell_price):,.4f} / ask {float(row.buy_price):,.4f}"
        )

    await message.answer("\n".join(lines))
