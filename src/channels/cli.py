"""CLI terminal channel implementation."""

from __future__ import annotations

from src.channels.base import Channel
from src.daemon.client import DaemonClient, SessionData
from src.display import (
    print_goodbye,
    print_response,
    print_user_message,
    print_welcome,
    prompt_input,
    set_commands,
    thinking_spinner,
)

_EXIT_COMMANDS = {"q", "/exit", "/quit"}


class CLIChannel(Channel):
    """Interactive terminal chat that talks to the daemon."""

    def __init__(self, client: DaemonClient | None = None) -> None:
        super().__init__(client)
        self._session: SessionData | None = None

    def start(self) -> None:
        """Connect to daemon and run the interactive prompt loop."""
        self.ensure_daemon()
        self._session = self.client.create_session()
        try:
            set_commands([])
            print_welcome(
                self._session.character_name,
                self._session.emoji,
                self._session.color,
                self._session.hi_message,
            )
            self._run_loop()
        finally:
            self.stop()

    def stop(self) -> None:
        """Delete the session and close the HTTP client."""
        if self._session:
            self.client.delete_session(self._session.id)
            self._session = None
        self.client.close()

    def _run_loop(self) -> None:
        """Read-eval-print loop over the daemon API."""
        session = self._session
        while True:
            user_input = prompt_input(session.emoji)
            if not user_input:
                continue
            if user_input in _EXIT_COMMANDS:
                print_goodbye(session.character_name, session.emoji, "has left the chat.")
                break

            print_user_message(user_input)

            with thinking_spinner():
                response, elapsed = self.client.send_message(session.id, user_input)
            print_response(
                session.character_name, session.emoji, session.color, response, elapsed,
            )
