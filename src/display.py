from contextlib import contextmanager
from typing import Generator

import random
import shutil

from pathlib import Path

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import Completer, Completion, PathCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import ANSI
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

_THINKING_SCENES: list[tuple[str, str]] = [
    ("Pivoting...", "orange1"),
    ("Central Perk brew in progress...", "sea_green3"),
    ("Unagi mode: engaged", "green3"),
    ("Smelly Cat analysis...", "deep_pink2"),
    ("Could it BE any more thoughts?", "yellow3"),
    ("On a break... then back to it", "turquoise2"),
    ("Checking the Geller Cup...", "dodger_blue2"),
    ("Monica-clean focus activated", "bright_cyan"),
    ("Ross-level overthinking...", "slate_blue3"),
]


def _random_thinking_label() -> tuple[Text, str]:
    phrase, color = random.choice(_THINKING_SCENES)
    return Text(phrase, style=f"bold {color}"), color


@contextmanager
def thinking_spinner() -> Generator[None, None, None]:
    label, color = _random_thinking_label()
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
    hints = Text.assemble(
        ("  /help", "green"),
        (" commands", "dim"),
        ("  ·  ", "dim"),
        ("/load", "green"),
        (" documents", "dim"),
        ("  ·  ", "dim"),
        ("/exit", "green"),
        (" quit", "dim"),
    )
    console.print(hints)
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


class _AppCompleter(Completer):
    """Slash-command completion + filesystem paths after /load."""

    def __init__(self, commands: list[tuple[str, str]]) -> None:
        self._commands = commands
        self._path_completer = PathCompleter(expanduser=True)

    def get_completions(
        self, document: Document, complete_event: object
    ) -> list[Completion]:
        text = document.text_before_cursor

        # After "/load " → complete file paths
        if any(text.startswith(p) for p in _LOAD_PREFIXES):
            path_text = text.split(None, 1)[1] if " " in text else ""
            sub_doc = Document(path_text, len(path_text))
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


_completer: _AppCompleter | None = None


def set_commands(commands: list[tuple[str, str]]) -> None:
    """Register available slash commands for autocomplete."""
    global _completer
    all_cmds = list(commands) + [("exit", "Exit the program")]
    _completer = _AppCompleter(all_cmds)


def prompt_input(emoji: str) -> str:
    """Show a styled prompt and return user input with slash-command completion."""
    console.print()
    return pt_prompt(
        ANSI(f" {emoji} \033[1;32m❯\033[0m "),
        completer=_completer,
    ).strip()


def print_goodbye(name: str, emoji: str) -> None:
    """Print a styled exit message."""
    console.print()
    _print_bar()
    goodbye = Text.assemble(
        (f"  {emoji} ", ""),
        (f"{name}", "bold"),
        (" has left the chat. ", "dim"),
        ("See you at Central Perk!", "italic dim"),
    )
    console.print(goodbye)
    console.print()
