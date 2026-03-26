"""Session model and in-memory session manager."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from logging import getLogger
from typing import TYPE_CHECKING

from src.agents.agent import Agent
from src.agents.character_loader import (
    load_character_by_filename,
    load_random_character,
)
from src.constants import DEFAULT_CHARACTER
from src.rules import load_all_rules

if TYPE_CHECKING:
    from src.config.resolver import QConfig

logger = getLogger(__name__)


@dataclass
class Session:
    """A single user session wrapping an Agent."""

    id: str
    agent: Agent
    character_name: str
    emoji: str
    color: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def message_count(self) -> int:
        return len([m for m in self.agent.get_history() if m.get("role") == "user"])


class SessionManager:
    """In-memory store for active sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(
        self, config: QConfig, character: str | None = None
    ) -> Session:
        """Create a new session with a fresh Agent."""
        agent_dirs = config.agents_dirs
        rules_dirs = config.rules_dirs
        mcp_paths = config.mcp_config_paths()

        char_name = character or DEFAULT_CHARACTER
        if char_name:
            char_data = load_character_by_filename(char_name, dirs=agent_dirs)
        else:
            char_data = load_random_character(dirs=agent_dirs)

        rules = load_all_rules(dirs=rules_dirs)
        agent = Agent(char_data, rules=rules, mcp_config_paths=mcp_paths)
        agent.on_tool_call = _auto_approve_tool_call

        session_id = uuid.uuid4().hex[:12]
        session = Session(
            id=session_id,
            agent=agent,
            character_name=char_data.name,
            emoji=char_data.emoji,
            color=char_data.color,
        )
        self._sessions[session_id] = session
        logger.info("Created session %s (%s)", session_id, char_data.name)
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        session = self._sessions.pop(session_id, None)
        if session:
            session.agent.close()
            logger.info("Deleted session %s", session_id)
            return True
        return False

    def list_all(self) -> list[Session]:
        return list(self._sessions.values())

    def close_all(self) -> None:
        for session in self._sessions.values():
            session.agent.close()
        self._sessions.clear()
        logger.info("All sessions closed")


def _auto_approve_tool_call(tool_name: str, arguments: dict) -> bool:
    """Non-interactive tool approval for daemon mode."""
    args_summary = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
    logger.info("tool call: %s(%s)", tool_name, args_summary)
    return True
