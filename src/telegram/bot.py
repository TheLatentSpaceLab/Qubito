"""Telegram bot interface — delegates to TelegramChannel."""

from __future__ import annotations

from src.channels.telegram import TelegramChannel
from src.constants import TELEGRAM_BOT_TOKEN


def run_bot() -> None:
    """Start the Telegram bot (blocking). Requires the daemon to be running."""
    channel = TelegramChannel(token=TELEGRAM_BOT_TOKEN)
    channel.start()
