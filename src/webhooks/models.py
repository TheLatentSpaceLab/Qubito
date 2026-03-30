"""Webhook configuration model with JSON persistence."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from logging import getLogger

logger = getLogger(__name__)

_DEFAULT_PATH = Path.home() / ".qubito" / "webhooks.json"


@dataclass
class WebhookConfig:
    """A registered webhook that triggers agent actions on incoming HTTP POST."""

    id: str = ""
    name: str = ""
    secret: str = ""
    action_template: str = ""
    character: str | None = None
    channel_target: str | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.id:
            self.id = uuid.uuid4().hex[:12]


def load_webhooks(path: Path = _DEFAULT_PATH) -> list[WebhookConfig]:
    """Load webhook configs from the JSON file."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return [WebhookConfig(**w) for w in data]
    except Exception:
        logger.warning("Failed to load webhooks from %s", path, exc_info=True)
        return []


def save_webhooks(hooks: list[WebhookConfig], path: Path = _DEFAULT_PATH) -> None:
    """Save webhook configs to the JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(h) for h in hooks], indent=2))
