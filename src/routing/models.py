"""Routing rule data model with JSON persistence."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from logging import getLogger

logger = getLogger(__name__)

_DEFAULT_PATH = Path.home() / ".qubito" / "routing.json"


@dataclass
class RoutingRule:
    """Maps a channel pattern to a named agent."""

    id: str = ""
    pattern: str = ""
    agent_id: str = ""
    priority: int = 0
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.id:
            self.id = uuid.uuid4().hex[:12]


def load_routing_rules(path: Path = _DEFAULT_PATH) -> list[RoutingRule]:
    """Load routing rules from the JSON file."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return [RoutingRule(**r) for r in data]
    except Exception:
        logger.warning("Failed to load routing rules from %s", path, exc_info=True)
        return []


def save_routing_rules(rules: list[RoutingRule], path: Path = _DEFAULT_PATH) -> None:
    """Save routing rules to the JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(r) for r in rules], indent=2))
