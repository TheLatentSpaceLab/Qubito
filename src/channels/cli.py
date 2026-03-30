"""CLI terminal channel implementation."""

from __future__ import annotations

import subprocess

from src.channels.base import Channel
from src.config.resolver import QConfig
from src.daemon.client import DaemonClient, SessionData
from src.skills import load_all_skills
from src.display import (
    console,
    print_character_picker,
    print_goodbye,
    print_response,
    print_user_message,
    print_welcome,
    prompt_input,
    set_agent_names,
    set_commands,
    thinking_spinner,
)

_EXIT_COMMANDS = {"q", "/exit", "/quit"}


def _format_lineup(status: dict) -> str | None:
    """Build a short model lineup string from daemon status."""
    model = status.get("model", "")
    fallback = status.get("fallback_model", "")
    if not model:
        return None
    # show just the model name without provider prefix for brevity
    short = model.rsplit("/", 1)[-1]
    line = short
    if fallback:
        short_fb = fallback.rsplit("/", 1)[-1]
        line += f" → {short_fb}"
    return line


class CLIChannel(Channel):
    """Interactive terminal chat that talks to the daemon."""

    def __init__(
        self,
        client: DaemonClient | None = None,
        character: str | None = None,
        pick: bool = False,
    ) -> None:
        super().__init__(client)
        self._character = character
        self._pick = pick
        self._session: SessionData | None = None

    def _resolve_character(self) -> str | None:
        """Determine which character to use for the session."""
        if self._character:
            return self._character
        if self._pick:
            characters = self.client.list_characters()
            idx = print_character_picker(characters)
            if idx is None:
                return None
            return characters[idx]["filename"]
        return None

    def start(self) -> None:
        """Connect to daemon and run the interactive prompt loop."""
        self.ensure_daemon()
        character = self._resolve_character()
        if self._pick and character is None:
            return
        self._session = self.client.create_session(character=character)
        try:
            skills = load_all_skills(dirs=QConfig().skills_dirs)
            set_commands([(s.name, s.description) for s in skills])
            set_agent_names(self.client.list_characters())
            status = self.client.status()
            model_lineup = _format_lineup(status)
            print_welcome(
                self._session.character_name,
                self._session.emoji,
                self._session.color,
                self._session.hi_message,
                model_lineup=model_lineup,
                hints=[
                    ("/help", "commands"),
                    ("/load", "documents"),
                    ("/agent", "switch agent"),
                    ("/autojob do", "<task>"),
                    ("/exit", "quit"),
                ],
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

    def _switch_agent(self, name: str | None) -> bool:
        """Switch to a different agent, creating a new session.

        Returns True if the switch succeeded.
        """
        if name:
            character = name
        else:
            characters = self.client.list_characters()
            idx = print_character_picker(characters)
            if idx is None:
                return False
            character = characters[idx]["filename"]

        try:
            new_session = self.client.create_session(character=character)
        except Exception as e:
            from src.display import print_error
            print_error(f"Could not switch agent: {e}")
            return False

        self.client.delete_session(self._session.id)
        self._session = new_session
        print_welcome(
            new_session.character_name,
            new_session.emoji,
            new_session.color,
            new_session.hi_message,
            hints=[
                ("/help", "commands"),
                ("/load", "documents"),
                ("/agent", "switch agent"),
                ("/exit", "quit"),
            ],
        )
        return True

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

            if user_input.startswith("!"):
                self._run_shell(user_input[1:].strip())
                continue

            if user_input == "/agent" or user_input.startswith("/agent "):
                parts = user_input.split(None, 1)
                name = parts[1] if len(parts) > 1 else None
                if self._switch_agent(name):
                    session = self._session
                continue

            print_user_message(user_input)

            data = self._send_with_progress(session, user_input)
            if data.get("is_handler"):
                if data["response"]:
                    console.print(data["response"])
            else:
                print_response(
                    session.character_name, session.emoji, session.color,
                    data["response"], data["elapsed"],
                )

    @staticmethod
    def _run_shell(cmd: str) -> None:
        """Execute a shell command and print its output."""
        if not cmd:
            console.print("[dim]Usage: !<command>[/dim]")
            return
        try:
            subprocess.run(cmd, shell=True)
        except Exception as exc:
            from src.display import print_error
            print_error(str(exc))

    def _send_with_progress(self, session: SessionData, message: str) -> dict:
        """Send a message using SSE streaming, showing tool call progress."""
        step = 0
        data: dict = {}
        try:
            for event in self.client.send_message_stream(session.id, message):
                if event["type"] == "progress":
                    step += 1
                    console.print(f"  [dim]{step}. {event['message']}[/dim]")
                elif event["type"] == "done":
                    data = event
        except Exception as exc:
            from src.display import print_error
            print_error(f"Connection error: {exc}")
        return data or {"response": "", "elapsed": 0, "is_handler": False}
