"""Agent-to-agent delegation via virtual tools."""

from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from src.agents.registry import AgentRegistry
    from src.config.resolver import QConfig

logger = getLogger(__name__)

MAX_DELEGATION_DEPTH = 3

DELEGATE_TOOL_DEF = {
    "name": "delegate_to_agent",
    "description": "Send a task to another specialized agent and get their response.",
    "input_schema": {
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "string",
                "description": "The ID of the target agent to delegate to.",
            },
            "message": {
                "type": "string",
                "description": "The task or question for the target agent.",
            },
        },
        "required": ["agent_id", "message"],
    },
}


def make_delegation_handler(
    registry: AgentRegistry,
    config: QConfig,
    depth: int = 0,
) -> dict:
    """Create a virtual tool handler for agent delegation.

    Parameters
    ----------
    registry : AgentRegistry
        The agent registry to look up target agents.
    config : QConfig
        Configuration for creating agent instances.
    depth : int
        Current delegation depth (to prevent infinite recursion).

    Returns
    -------
    callable
        A function ``(arguments: dict) -> str`` that delegates to another agent.
    """
    def handler(arguments: dict) -> str:
        agent_id = arguments.get("agent_id", "")
        message = arguments.get("message", "")

        if depth >= MAX_DELEGATION_DEPTH:
            return f"Error: maximum delegation depth ({MAX_DELEGATION_DEPTH}) reached."

        try:
            target = registry.get_or_create(agent_id, config)
        except KeyError:
            available = [a.id for a in registry.list_agents()]
            return f"Error: agent '{agent_id}' not found. Available: {', '.join(available)}"

        logger.info("Delegating to agent '%s' (depth %d): %s", agent_id, depth + 1, message[:100])
        response = target.message(message)
        target.close()
        return response

    return {"handler": handler, "definition": DELEGATE_TOOL_DEF}
