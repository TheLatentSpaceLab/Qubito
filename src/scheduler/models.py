"""Cron job data model with JSON persistence."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from logging import getLogger

logger = getLogger(__name__)

_DEFAULT_PATH = Path.home() / ".qubito" / "cron.json"


@dataclass
class CronJob:
    """A scheduled task that the daemon executes on a cron schedule."""

    id: str = ""
    name: str = ""
    cron_expression: str = ""
    action: str = ""
    character: str | None = None
    channel_target: str | None = None
    enabled: bool = True
    created_at: str = ""
    last_run: str | None = None

    def __post_init__(self) -> None:
        if not self.id:
            self.id = uuid.uuid4().hex[:12]
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


def load_cron_jobs(path: Path = _DEFAULT_PATH) -> list[CronJob]:
    """Load cron jobs from the JSON file."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return [CronJob(**j) for j in data]
    except Exception:
        logger.warning("Failed to load cron jobs from %s", path, exc_info=True)
        return []


def save_cron_jobs(jobs: list[CronJob], path: Path = _DEFAULT_PATH) -> None:
    """Save cron jobs to the JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(j) for j in jobs], indent=2))
