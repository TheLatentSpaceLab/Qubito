"""Handler for the ``qubito init`` subcommand."""

from __future__ import annotations

from src.config.scaffold import scaffold_global
from src.display import console


def run_init() -> None:
    """Scaffold ~/.qubito/ with all subdirectories."""
    gpath = scaffold_global()
    console.print(f"[green]Initialized:[/green] {gpath}")
