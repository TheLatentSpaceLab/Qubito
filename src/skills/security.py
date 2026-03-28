"""Security group policies for autonomous job execution."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SecurityGroup:
    """Policy that controls which tool calls are allowed during a job."""

    name: str
    always_allow: frozenset[str] = frozenset()
    always_deny: frozenset[str] = frozenset()
    ask_user: frozenset[str] = frozenset()
    allowed_paths: tuple[str, ...] = (".",)
    max_tool_rounds: int = 15
    command_denylist: tuple[str, ...] = ()


DEFAULT_SECURITY_GROUP = SecurityGroup(
    name="default",
    always_allow=frozenset({"read_file", "list_directory"}),
    always_deny=frozenset(),
    ask_user=frozenset({"create_file", "edit_file", "delete_file", "run_command"}),
    allowed_paths=(".",),
    max_tool_rounds=15,
    command_denylist=(
        "rm -rf /",
        "rm -rf /*",
        "mkfs",
        ":(){:|:&};:",
        "dd if=",
        "> /dev/sd",
        "chmod -R 777 /",
    ),
)
