"""Test helper functions used as skill handlers in tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.agents.agent import Agent


_last_ping_input: str | None = None


def handle_ping(agent: Agent, user_input: str) -> None:
    global _last_ping_input
    _last_ping_input = user_input
    print("pong")
