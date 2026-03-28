"""Guardrail system for autonomous job execution."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from src.skills.security import SecurityGroup

logger = logging.getLogger(__name__)


def make_guardrail(
    policy: SecurityGroup,
    on_user_decision: Callable[[str, str, dict], bool],
) -> Callable[[str, dict], bool]:
    """Return an on_tool_call callback that enforces the security policy.

    Parameters
    ----------
    policy : SecurityGroup
        The security policy to enforce.
    on_user_decision : callable
        Called as ``(tool_name, description, arguments) -> bool`` when the
        tool requires user approval.
    """
    def _callback(tool_name: str, arguments: dict) -> bool:
        if tool_name in policy.always_deny:
            logger.warning("Guardrail DENIED (always_deny): %s", tool_name)
            return False

        if tool_name in policy.always_allow:
            return True

        if not _check_command_safe(tool_name, arguments, policy):
            logger.warning("Guardrail DENIED (command_denylist): %s", arguments)
            return False

        if not _check_path_allowed(tool_name, arguments, policy):
            logger.warning("Guardrail DENIED (path): %s", arguments)
            return False

        if tool_name in policy.ask_user:
            desc = format_action_description(tool_name, arguments)
            return on_user_decision(tool_name, desc, arguments)

        return True

    return _callback


def _check_command_safe(
    tool_name: str,
    arguments: dict,
    policy: SecurityGroup,
) -> bool:
    """Return False if a run_command call matches the denylist."""
    if tool_name != "run_command":
        return True
    command = arguments.get("command", "")
    return not any(pattern in command for pattern in policy.command_denylist)


def _check_path_allowed(
    tool_name: str,
    arguments: dict,
    policy: SecurityGroup,
) -> bool:
    """Return False if a file tool targets a path outside allowed prefixes."""
    path_str = arguments.get("path")
    if not path_str:
        return True

    file_tools = {"create_file", "edit_file", "delete_file", "read_file"}
    if tool_name not in file_tools:
        return True

    target = Path(path_str).expanduser().resolve()
    for allowed in policy.allowed_paths:
        allowed_abs = Path(allowed).expanduser().resolve()
        if target == allowed_abs or allowed_abs in target.parents:
            return True
    return False


def format_action_description(tool_name: str, arguments: dict) -> str:
    """Generate a human-readable description of a tool call."""
    if tool_name == "run_command":
        cmd = arguments.get("command", "?")
        cwd = arguments.get("cwd", ".")
        return f"Run shell command: `{cmd}` in `{cwd}`"

    if tool_name == "create_file":
        path = arguments.get("path", "?")
        content = arguments.get("content", "")
        lines = content.count("\n") + 1
        return f"Create file `{path}` ({lines} lines)"

    if tool_name == "edit_file":
        path = arguments.get("path", "?")
        old = arguments.get("old_text", "")[:50]
        return f"Edit file `{path}` (replace: `{old}...`)"

    if tool_name == "delete_file":
        return f"Delete file `{arguments.get('path', '?')}`"

    args_str = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
    return f"Call `{tool_name}({args_str})`"
