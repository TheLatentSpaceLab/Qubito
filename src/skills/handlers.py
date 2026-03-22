"""Handler functions for built-in skills.

Every handler has the signature: (agent: Agent, user_input: str) -> None
"""

from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import TYPE_CHECKING

from src.display import console, print_response
from src.constants import (
    AI_CLIENT_MODEL,
    AI_CLIENT_PROVIDER,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
)

if TYPE_CHECKING:
    from src.agents.agent import Agent

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}


def handle_load(agent: Agent, user_input: str) -> None:
    """Parse and execute a document loading command."""
    try:
        parts = shlex.split(user_input)
    except ValueError:
        console.print("[red]Invalid command format. Use: /load <path-to-file>[/red]")
        return

    if len(parts) < 2:
        console.print("[yellow]Usage: /load <path-to-file>[/yellow]")
        return

    raw_path = " ".join(parts[1:]).strip().strip("'\"")
    # Handle file:// URIs from drag-and-drop
    if raw_path.startswith("file://"):
        from urllib.parse import unquote, urlparse
        raw_path = unquote(urlparse(raw_path).path)
    file_path = Path(raw_path).expanduser()
    if not file_path.is_absolute():
        file_path = Path.cwd() / file_path

    if not file_path.exists():
        console.print(f"[red]File not found:[/red] {file_path}")
        return

    if not file_path.is_file():
        console.print(f"[red]Path is not a file:[/red] {file_path}")
        return

    try:
        if file_path.suffix.lower() in _IMAGE_EXTENSIONS:
            from src.ocr.reader import Reader
            file_content = Reader().extract_image_information(str(file_path))
        elif file_path.suffix.lower() == ".pdf":
            raise NotImplementedError(
                "PDF extraction not yet implemented."
            )
        else:
            try:
                file_content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                console.print("[red]Could not read file as UTF-8 text.[/red]")
                return
    except NotImplementedError as err:
        console.print(f"[yellow]{err}[/yellow]")
        return
    except OSError as err:
        console.print(f"[red]Failed to read file:[/red] {err}")
        return

    _, chunks, stats = agent.index_document(str(file_path), file_content)
    print_response(
        agent.name,
        agent.emoji,
        agent.color,
        (
            f"Loaded {file_path.name} into memory. "
            f"Indexed {chunks} chunks "
            f"({stats['documents']} docs / {stats['chunks']} chunks total)."
        ),
    )


def handle_history(agent: Agent, user_input: str) -> None:
    """Print the conversation history."""
    console.print("[bold cyan]Conversation history:[/bold cyan]")
    console.print(json.dumps(agent.get_history(), indent=2, ensure_ascii=False))


def handle_context(agent: Agent, user_input: str) -> None:
    """Print loaded retrieval context."""
    context_view = agent.get_context()
    if not context_view:
        console.print("[yellow]No context loaded yet. Use /load <path> first.[/yellow]")
        return
    console.print("[bold cyan]Loaded context chunks:[/bold cyan]")
    console.print(json.dumps(context_view, indent=2, ensure_ascii=False))


def handle_lineup(agent: Agent, user_input: str) -> None:
    """Print current model configuration."""
    console.print("\n[bold]Current lineup is[/bold]")
    console.print(" [green]AI Client Provider[/green]: ", AI_CLIENT_PROVIDER)
    console.print(" [green]AI Client Model[/green]: ", AI_CLIENT_MODEL)
    console.print(" [blue]Embeddings Provider[/blue]: ", EMBEDDING_PROVIDER)
    console.print(" [blue]Embeddings Model[/blue]: ", EMBEDDING_MODEL)


def handle_stats(agent: Agent, user_input: str) -> None:
    """Display a bar chart of response times and average."""
    times = agent.response_times
    if not times:
        console.print("[yellow]No responses yet.[/yellow]")
        return

    avg = sum(times) / len(times)
    max_t = max(times)
    bar_max_width = 40

    console.print()
    console.print(f"  [bold]Response times[/bold]  ({len(times)} responses, avg [cyan]{avg:.1f}s[/cyan])")
    console.print()

    for i, t in enumerate(times, 1):
        bar_len = int((t / max_t) * bar_max_width) if max_t > 0 else 0
        bar = "█" * bar_len
        color = "green" if t <= avg else "yellow" if t <= avg * 1.5 else "red"
        console.print(f"  [dim]{i:>3}[/dim] [{color}]{bar}[/{color}] {t:.1f}s")

    console.print()
    console.print(f"  [dim]min[/dim] [cyan]{min(times):.1f}s[/cyan]  "
                  f"[dim]avg[/dim] [cyan]{avg:.1f}s[/cyan]  "
                  f"[dim]max[/dim] [cyan]{max_t:.1f}s[/cyan]")
    console.print()


def handle_help(agent: Agent, user_input: str) -> None:
    """List all available skills."""
    from src.skills import load_all_skills

    console.print("\n[bold]Available commands:[/bold]")
    for skill in load_all_skills():
        console.print(f"  [green]/{skill.name}[/green] — {skill.description}")
    console.print("  [green]/exit[/green] — Exit the program")
    console.print()
