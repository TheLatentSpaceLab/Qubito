"""Interactive terminal chat loop."""

from __future__ import annotations

from src.channels.cli import CLIChannel


def run_chat(character: str | None = None, pick: bool = False) -> None:
    """Run the interactive assistant terminal chat via the daemon."""
    channel = CLIChannel(character=character, pick=pick)
    channel.start()
