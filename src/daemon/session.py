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
    from src.persistence.conversation_db import ConversationDB
    from src.agents.registry import AgentRegistry

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
    last_active: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def message_count(self) -> int:
        return len([m for m in self.agent.get_history() if m.get("role") == "user"])

    def touch(self) -> None:
        """Update the last_active timestamp."""
        self.last_active = datetime.now(timezone.utc)


class SessionManager:
    """In-memory store for active sessions, optionally backed by SQLite."""

    def __init__(self, db: ConversationDB | None = None, registry: AgentRegistry | None = None) -> None:
        self._sessions: dict[str, Session] = {}
        self.db: ConversationDB | None = db
        self.registry: AgentRegistry | None = registry

    def create(
        self,
        config: QConfig,
        character: str | None = None,
        agent_id: str | None = None,
    ) -> Session:
        """Create a new session with a fresh Agent.

        Parameters
        ----------
        config : QConfig
            Resolved configuration providing agent, rules, and MCP paths.
        character : str or None
            Character filename to load. Falls back to DEFAULT_CHARACTER.

        Returns
        -------
        Session
            The newly created session with an initialised Agent.
        """
        session_id = uuid.uuid4().hex[:12]

        if agent_id and self.registry:
            agent = self.registry.get_or_create(
                agent_id, config, session_id=session_id, db=self.db,
            )
        else:
            agent_dirs = config.agents_dirs
            rules_dirs = config.rules_dirs
            mcp_paths = config.mcp_config_paths()

            char_name = character or DEFAULT_CHARACTER
            if char_name:
                char_data = load_character_by_filename(char_name, dirs=agent_dirs)
            else:
                char_data = load_random_character(dirs=agent_dirs)

            rules = load_all_rules(dirs=rules_dirs)
            agent = Agent(
                char_data,
                rules=rules,
                mcp_config_paths=mcp_paths,
                session_id=session_id,
                db=self.db,
            )
        agent.on_tool_call = _auto_approve_tool_call

        session = Session(
            id=session_id,
            agent=agent,
            character_name=agent.name,
            emoji=agent.emoji,
            color=agent.color,
        )
        self._sessions[session_id] = session

        if self.db:
            self.db.save_session(session_id, agent.name, agent.emoji, agent.color)

        logger.info("Created session %s (%s)", session_id, char_data.name)
        return session

    def get(self, session_id: str) -> Session | None:
        """Look up a session by id.

        Parameters
        ----------
        session_id : str
            The session identifier.

        Returns
        -------
        Session or None
            The session if found, otherwise None.
        """
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        """Remove a session and close its agent.

        Parameters
        ----------
        session_id : str
            The session to delete.

        Returns
        -------
        bool
            True if the session existed and was removed.
        """
        session = self._sessions.pop(session_id, None)
        if session:
            session.agent.close()
            if self.db:
                self.db.delete_session(session_id)
            logger.info("Deleted session %s", session_id)
            return True
        return False

    def list_all(self) -> list[Session]:
        """Return all active sessions.

        Returns
        -------
        list of Session
            Snapshot of current sessions.
        """
        return list(self._sessions.values())

    def evict_idle(self, timeout_minutes: int) -> list[str]:
        """Remove sessions idle longer than *timeout_minutes*.

        Returns
        -------
        list of str
            IDs of evicted sessions.
        """
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
        to_evict = [sid for sid, s in self._sessions.items() if s.last_active < cutoff]
        for sid in to_evict:
            self.delete(sid)
        return to_evict

    def close_all(self) -> None:
        for session in self._sessions.values():
            session.agent.close()
        self._sessions.clear()
        logger.info("All sessions closed")


def _auto_approve_tool_call(tool_name: str, arguments: dict) -> bool:
    """Non-interactive tool approval for daemon mode.

    Parameters
    ----------
    tool_name : str
        Name of the MCP tool being invoked.
    arguments : dict
        Arguments passed to the tool.

    Returns
    -------
    bool
        Always True (auto-approve in daemon context).
    """
    args_summary = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
    logger.info("tool call: %s(%s)", tool_name, args_summary)
    return True
