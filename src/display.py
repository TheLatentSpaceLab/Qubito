from contextlib import contextmanager

import random

from rich.console import Console
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text

console = Console()


_THINKING_SCENES: list[tuple[str, str]] = [
    ("Pivoting...", "orange1"),
    ("Central Perk brew in progress...", "sea_green3"),
    ("Unagi mode: engaged", "green3"),
    ("Smelly Cat analysis...", "deep_pink2"),
    ("Could it BE any more thoughts?", "yellow3"),
    ("On a break... then back to it", "turquoise2"),
    ("Checking the Geller Cup...", "dodger_blue2"),
    ("Monica-clean focus activated", "bright_cyan"),
    ("Joey: how you doin... processing", "hot_pink3"),
    ("Ross-level overthinking...", "slate_blue3"),
]


def _random_thinking_label() -> tuple[Text, str]:
    phrase, color = random.choice(_THINKING_SCENES)
    return Text(phrase, style=f"bold {color}"), color


@contextmanager
def thinking_spinner():
    label, color = _random_thinking_label()
    with console.status(
        Spinner("dots", text=label, style=color),
    ):
        yield


def print_response(name: str, emoji: str, color: str, text: str) -> None:
    """
    Print a character response panel in the terminal.

    Parameters
    ----------
    name : str
        Display name of the character.
    emoji : str
        Emoji rendered in the panel title.
    color : str
        Rich color style used for the character name in the title.
    text : str
        Message body rendered inside the panel.

    Returns
    -------
    None
        The function writes a formatted panel to the console.
    """

    panel = Panel(
        Text(text, style="white"),
        title=f" {emoji} [{color}]{name}[/{color}] ",
        title_align="left",
        border_style="dim",
        padding=(0, 1),
    )
    console.print(panel)
