"""Background task data model."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class BackgroundTask:
    """A long-running task executed asynchronously by the daemon."""

    id: str = ""
    description: str = ""
    status: str = "queued"
    session_id: str = ""
    character: str | None = None
    progress: str = ""
    result: str | None = None
    created_at: str = ""
    completed_at: str | None = None

    def __post_init__(self) -> None:
        if not self.id:
            self.id = uuid.uuid4().hex[:12]
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
