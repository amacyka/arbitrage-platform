from __future__ import annotations

from sqlalchemy import select

from app.bot.formatting import format_signal
from app.database.db import SessionLocal
from app.database.models import ArbitrageSignal, UserSettings
from app.engine.scanner import register_signal_callback


def setup_notifier(bot) -> None:
    """Wire the scanner's signal callback to actually push Telegram alerts
    to every chat whose thresholds the signal satisfies.

    The scanner already applies the *default* thresholds before creating a
    signal at all; here we additionally re-check each user's own
    (possibly stricter) thresholds before sending to them.
    """

    async def _on_signal(signal: ArbitrageSignal) -> None:
        async with SessionLocal() as session:
            result = await session.execute(select(UserSettings))
            users = list(result.scalars())

        text = format_signal(signal)

        for user in users:
            if float(signal.roi_pct) < float(user.min_roi_pct):
                continue
            if float(signal.estimated_net_profit) < float(user.min_profit_usdt):
                continue
            if not signal.volume_ok:
                continue

            try:
                await bot.send_message(user.chat_id, text)
            except Exception as exc:  # noqa: BLE001 - one bad chat shouldn't stop the rest
                print(f"[notifier] failed to send to chat {user.chat_id}: {exc}")

    register_signal_callback(_on_signal)
