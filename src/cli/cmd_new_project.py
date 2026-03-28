"""Handler for the ``qubito new-project`` subcommand."""

from __future__ import annotations

from pathlib import Path

from src.config.scaffold import scaffold_project
from src.display import console


def run_new_project(path: str | None = None) -> None:
    """Scaffold .qubito/ in a project directory for local overrides."""
    target = Path(path) if path else Path.cwd()
    ppath = scaffold_project(target)
    console.print(f"[green]Project config:[/green] {ppath}")
