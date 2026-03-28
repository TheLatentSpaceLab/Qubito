"""Messaging channel abstractions."""

from src.channels.base import Channel
from src.channels.cli import CLIChannel
from src.channels.telegram import TelegramChannel

__all__ = ["Channel", "CLIChannel", "TelegramChannel"]
