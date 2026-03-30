"""Named agent registry with JSON persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

from src.agents.agent import Agent
from src.agents.character_loader import load_character_by_filename
from src.rules import load_all_rules

if TYPE_CHECKING:
    from src.config.resolver import QConfig
    from src.persistence.conversation_db import ConversationDB

logger = getLogger(__name__)

_DEFAULT_PATH = Path.home() / ".qubito" / "agents.json"


@dataclass
class AgentConfig:
    """Configuration for a named agent."""

    id: str = ""
    character: str = ""
    description: str = ""
    mcp_servers: list[str] | None = None
    rag_namespace: str | None = None
    rules: list[str] | None = None


class AgentRegistry:
    """Manages named agent configurations with optional persistence."""

    def __init__(self, path: Path = _DEFAULT_PATH) -> None:
        self._path = path
        self._configs: dict[str, AgentConfig] = {}
        self._instances: dict[str, Agent] = {}
        self._load()

    def _load(self) -> None:
        """Load agent configs from the JSON file."""
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            for entry in data:
                cfg = AgentConfig(**entry)
                if cfg.id:
                    self._configs[cfg.id] = cfg
        except Exception:
            logger.warning("Failed to load agent registry from %s", self._path, exc_info=True)

    def _save(self) -> None:
        """Persist agent configs to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(
            [asdict(c) for c in self._configs.values()], indent=2,
        ))

    def list_agents(self) -> list[AgentConfig]:
        """Return all registered agent configurations."""
        return list(self._configs.values())

    def get_config(self, agent_id: str) -> AgentConfig | None:
        """Look up an agent configuration by ID."""
        return self._configs.get(agent_id)

    def register(self, config: AgentConfig) -> None:
        """Add or update an agent configuration and persist."""
        self._configs[config.id] = config
        self._instances.pop(config.id, None)
        self._save()

    def unregister(self, agent_id: str) -> bool:
        """Remove an agent configuration. Returns True if found."""
        if agent_id in self._configs:
            del self._configs[agent_id]
            self._instances.pop(agent_id, None)
            self._save()
            return True
        return False

    def get_or_create(
        self,
        agent_id: str,
        config: QConfig,
        session_id: str | None = None,
        db: ConversationDB | None = None,
    ) -> Agent:
        """Get a cached Agent instance or create one from the registered config.

        Parameters
        ----------
        agent_id : str
            Registered agent ID.
        config : QConfig
            Resolved configuration for directories.
        session_id : str or None
            Session ID for conversation persistence.
        db : ConversationDB or None
            Database for persistence.

        Returns
        -------
        Agent
            The agent instance.

        Raises
        ------
        KeyError
            If *agent_id* is not registered.
        """
        agent_cfg = self._configs.get(agent_id)
        if not agent_cfg:
            raise KeyError(f"Agent '{agent_id}' not registered")

        char_data = load_character_by_filename(agent_cfg.character, dirs=config.agents_dirs)

        if agent_cfg.rules:
            rules = "\n\n".join(agent_cfg.rules)
        else:
            rules = load_all_rules(dirs=config.rules_dirs)

        mcp_paths = config.mcp_config_paths()
        if agent_cfg.mcp_servers is not None:
            mcp_paths = [Path(p) for p in agent_cfg.mcp_servers if Path(p).exists()]

        agent = Agent(
            char_data,
            rules=rules,
            mcp_config_paths=mcp_paths,
            session_id=session_id,
            db=db,
            rag_namespace=agent_cfg.rag_namespace,
        )
        return agent
