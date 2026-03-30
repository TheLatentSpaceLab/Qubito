from contextlib import contextmanager
from typing import Generator

import random
import shutil

from pathlib import Path

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import Completer, Completion, PathCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.history import InMemoryHistory
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.spinner import Spinner
from rich.text import Text
from rich.table import Table
from rich.align import Align

console = Console()

_COLS = shutil.get_terminal_size().columns

_COFFEE = r"""
              )  )   )
             (  (   (
            ________
           |        |]
           |        |]
           |________|]
            \______/
"""

_LOGO = r"""
  ██████╗ ███████╗ ███╗   ██╗ ████████╗ ██████╗   █████╗  ██╗
 ██╔════╝ ██╔════╝ ████╗  ██║ ╚══██╔══╝ ██╔══██╗ ██╔══██╗ ██║
 ██║      █████╗   ██╔██╗ ██║    ██║    ██████╔╝ ███████║ ██║
 ██║      ██╔══╝   ██║╚██╗██║    ██║    ██╔══██╗ ██╔══██╗ ██║
 ╚██████╗ ███████╗ ██║ ╚████║    ██║    ██║  ██║ ██║  ██║ ███████╗
  ╚═════╝ ╚══════╝ ╚═╝  ╚═══╝    ╚═╝    ╚═╝  ╚═╝ ╚═╝  ╚═╝ ╚══════╝
 ██████╗  ███████╗ ██████╗  ██╗  ██╗
 ██╔══██╗ ██╔════╝ ██╔══██╗ ██║ ██╔╝
 ██████╔╝ █████╗   ██████╔╝ █████╔╝
 ██╔═══╝  ██╔══╝   ██╔══██╗ ██╔═██╗
 ██║      ███████╗ ██║  ██║ ██║  ██╗
 ╚═╝      ╚══════╝ ╚═╝  ╚═╝ ╚═╝  ╚═╝"""

_DEFAULT_THINKING: list[str] = [
    "Thinking...",
    "Processing...",
    "Working on it...",
]


@contextmanager
def thinking_spinner(
    phrases: tuple[str, ...] = (), color: str = "dim",
) -> Generator[None, None, None]:
    """Show a spinner with a random thinking phrase.

    Uses character-specific *phrases* when provided, otherwise falls
    back to generic defaults.
    """
    pool = list(phrases) if phrases else _DEFAULT_THINKING
    label = Text(random.choice(pool), style=f"bold {color}")
    with console.status(
        Spinner("dots", text=label, style=color),
    ):
        yield


def print_welcome(
    name: str,
    emoji: str,
    color: str,
    greeting: str,
    mcp_tools: list[str] | None = None,
    model_lineup: str | None = None,
    hints: list[tuple[str, str]] | None = None,
) -> None:
    """Clear screen and render the full welcome screen."""
    console.clear()

    # Coffee + Logo
    coffee_text = Text(_COFFEE, style="dim white")
    console.print(coffee_text, end="")
    logo_text = Text(_LOGO, style="bold yellow")
    console.print(logo_text)
    console.print()

    # Character card
    card_content = Text()
    card_content.append(f"{emoji}  ", style="bold")
    card_content.append(name, style=f"bold {color}")
    card_content.append(" has entered the chat\n\n", style="dim")
    card_content.append(f'"{greeting}"', style="italic white")

    if model_lineup:
        card_content.append("\n\n")
        card_content.append("model ", style="dim")
        card_content.append(model_lineup, style="dim cyan")

    if mcp_tools:
        card_content.append("\n\n")
        card_content.append("tools ", style="dim")
        card_content.append(" · ".join(mcp_tools), style="dim cyan")

    card = Panel(
        card_content,
        border_style=color,
        padding=(1, 2),
        width=min(64, _COLS - 4),
    )
    console.print(card)
    console.print()

    # Hints
    if hints is None:
        hints = [
            ("/help", "commands"),
            ("/load", "documents"),
            ("/exit", "quit"),
        ]
    parts: list[tuple[str, str]] = []
    for i, (cmd, desc) in enumerate(hints):
        if i > 0:
            parts.append(("  ·  ", "dim"))
        parts.append((f"  {cmd}" if i == 0 else cmd, "green"))
        parts.append((f" {desc}", "dim"))
    hints_text = Text.assemble(*parts)
    console.print(hints_text)
    _print_bar()


def _print_bar() -> None:
    """Thin horizontal rule as a visual separator."""
    console.print(Rule(style="dim"))


def print_user_message(text: str) -> None:
    """Echo the user message in a right-aligned dim style."""
    user_text = Text()
    user_text.append("you  ", style="dim")
    user_text.append(text, style="white")
    console.print(Align.right(user_text))
    console.print()


def print_response(
    name: str, emoji: str, color: str, text: str, elapsed: float | None = None,
) -> None:
    """Print a character response in a styled panel with optional timing."""
    subtitle = f" {elapsed:.1f}s " if elapsed is not None else None
    panel = Panel(
        Text(text, style="white"),
        title=f" {emoji} [{color}]{name}[/{color}] ",
        title_align="left",
        subtitle=subtitle,
        subtitle_align="right",
        border_style=color,
        padding=(0, 1),
        width=min(80, _COLS - 2),
    )
    console.print(panel)


def print_info(text: str) -> None:
    """Print a subtle informational line."""
    console.print(f"  [dim]{text}[/dim]")


def print_error(text: str) -> None:
    """Print an error message."""
    console.print(f"  [red]{text}[/red]")


def print_warning(text: str) -> None:
    """Print a warning message."""
    console.print(f"  [yellow]{text}[/yellow]")


_LOAD_PREFIXES = ("/load ", "/load\t")

_AUTOJOB_SUBCOMMANDS = [
    ("do", "generate plan only"),
    ("run", "execute a plan"),
]


class _AppCompleter(Completer):
    """Slash-command completion + filesystem paths after /load."""

    def __init__(self, commands: list[tuple[str, str]]) -> None:
        self._commands = commands
        self._path_completer = PathCompleter(expanduser=True)
        self._agent_names: list[tuple[str, str, str]] = []  # (filename, display, emoji)

    def get_completions(
        self, document: Document, complete_event: object
    ) -> list[Completion]:
        text = document.text_before_cursor

        # After "/load " → complete file paths
        if any(text.startswith(p) for p in _LOAD_PREFIXES):
            parts = text.split(None, 1)
            path_text = parts[1] if len(parts) > 1 else ""
            sub_doc = Document(path_text, len(path_text))
            yield from self._path_completer.get_completions(sub_doc, complete_event)
            return

        # After "/autojob run " → complete existing job names
        if text.startswith("/autojob run "):
            typed_job = text[len("/autojob run "):]
            yield from self._complete_jobs(typed_job)
            return

        # After "/autojob " → complete subcommands
        if text.startswith("/autojob "):
            typed_sub = text[len("/autojob "):]
            for sub, desc in _AUTOJOB_SUBCOMMANDS:
                if sub.startswith(typed_sub):
                    yield Completion(
                        sub,
                        start_position=-len(typed_sub),
                        display=sub,
                        display_meta=desc,
                    )
            return

        # After "/agent " → complete character names
        if text.startswith("/agent "):
            typed_name = text[len("/agent "):]
            for filename, display, emoji in self._agent_names:
                if filename.startswith(typed_name):
                    yield Completion(
                        filename,
                        start_position=-len(typed_name),
                        display=f"{emoji} {filename}",
                        display_meta=display,
                    )
            return

        # After "!" → complete shell commands via path completer
        if text.startswith("!"):
            cmd_text = text[1:]
            sub_doc = Document(cmd_text, len(cmd_text))
            yield from self._path_completer.get_completions(sub_doc, complete_event)
            return

        # Leading "/" → complete slash commands
        if text.startswith("/"):
            typed = text[1:]
            for name, desc in self._commands:
                if name.startswith(typed):
                    yield Completion(
                        name,
                        start_position=-len(typed),
                        display=f"/{name}",
                        display_meta=desc,
                    )

    @staticmethod
    def _complete_jobs(typed: str) -> list[Completion]:
        """Yield completions for existing job directory names."""
        jobs_dir = Path.home() / ".qubito" / "jobs"
        if not jobs_dir.is_dir():
            return []
        for d in sorted(jobs_dir.iterdir()):
            if d.is_dir() and (d / "program.md").exists():
                if d.name.startswith(typed):
                    yield Completion(
                        d.name,
                        start_position=-len(typed),
                        display=d.name,
                    )


_completer: _AppCompleter | None = None
_history: InMemoryHistory = InMemoryHistory()


def set_commands(commands: list[tuple[str, str]]) -> None:
    """Register available slash commands for autocomplete."""
    global _completer
    all_cmds = list(commands) + [
        ("agent", "Switch agent"),
        ("exit", "Exit the program"),
    ]
    _completer = _AppCompleter(all_cmds)


def set_agent_names(agents: list[dict]) -> None:
    """Register agent names for /agent autocomplete."""
    if _completer:
        _completer._agent_names = [
            (a["filename"], a["name"], a["emoji"]) for a in agents
        ]


def prompt_input(emoji: str) -> str:
    """Show a styled prompt and return user input with slash-command completion."""
    console.print()
    return pt_prompt(
        ANSI(f" {emoji} \033[1;32m❯\033[0m "),
        completer=_completer,
        history=_history,
    ).strip()


def print_character_picker(characters: list[dict]) -> int | None:
    """Display a numbered list of characters and prompt the user to pick one.

    Returns
    -------
    int or None
        Zero-based index of the chosen character, or None if cancelled.
    """
    console.print()
    console.print("  [bold]Choose your agent:[/bold]")
    console.print()
    for i, ch in enumerate(characters, 1):
        emoji = ch.get("emoji", "")
        name = ch.get("name", "")
        color = ch.get("color", "white")
        console.print(f"  [dim]{i:>2}.[/dim]  {emoji}  [{color}]{name}[/{color}]")
    console.print()
    try:
        choice = pt_prompt(ANSI(" \033[1;32m#>\033[0m ")).strip()
    except (KeyboardInterrupt, EOFError):
        return None
    if not choice.isdigit():
        return None
    idx = int(choice) - 1
    if 0 <= idx < len(characters):
        return idx
    return None


def print_goodbye(name: str, emoji: str, bye_message: str = "has left the chat.") -> None:
    """Print a styled exit message."""
    console.print()
    _print_bar()
    goodbye = Text.assemble(
        (f"  {emoji} ", ""),
        (f"{name} ", "bold"),
        (bye_message, "italic dim"),
    )
    console.print(goodbye)
    console.print()
