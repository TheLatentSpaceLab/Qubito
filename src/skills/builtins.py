"""Built-in skill handlers mapped by command name.

These are skills that execute Python functions directly rather than
passing instructions to the LLM.  The mapping lives here so that
``api.py`` can dispatch without relying on frontmatter fields.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from src.agents.agent import Agent

# command name → dotted path to handler function
BUILTIN_HANDLERS: dict[str, str] = {
    "context": "src.skills.handlers.handle_context",
    "context-usage": "src.skills.handlers.handle_context_usage",
    "cron": "src.skills.cron_handler.handle_cron",
    "help": "src.skills.handlers.handle_help",
    "history": "src.skills.handlers.handle_history",
    "letcook": "src.skills.letcook.handle_letcook",
    "lineup": "src.skills.handlers.handle_lineup",
    "load": "src.skills.handlers.handle_load",
    "model": "src.skills.handlers.handle_model",
    "new-agent": "src.skills.generators.handle_new_agent",
    "new-rule": "src.skills.generators.handle_new_rule",
    "new-skill": "src.skills.generators.handle_new_skill",
    "stats": "src.skills.handlers.handle_stats",
}


def is_builtin(name: str) -> bool:
    """Return True if *name* is a built-in handler skill."""
    return name in BUILTIN_HANDLERS


def resolve_handler(name: str) -> Callable[[Agent, str], None]:
    """Import and return the handler callable for a built-in skill.

    Raises
    ------
    KeyError
        If *name* is not a registered built-in.
    """
    dotted = BUILTIN_HANDLERS[name]
    module_path, _, func_name = dotted.rpartition(".")
    module = importlib.import_module(module_path)
    return getattr(module, func_name)
