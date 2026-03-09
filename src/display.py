from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


def print_response(name: str, emoji: str, color: str, text: str) -> None:
    """
    Prints a character response with emoji + colored name in the title.
    """

    panel = Panel(
        Text(text, style="white"),
        title=f" {emoji} [{color}]{name}[/{color}] ",
        title_align="left",
        border_style="dim",
        padding=(0, 1),
    )
    console.print(panel)
