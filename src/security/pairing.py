"""DM pairing — approve/deny unknown senders before responding."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from logging import getLogger
from pathlib import Path

logger = getLogger(__name__)

_DEFAULT_PATH = Path.home() / ".qubito" / "approved_senders.json"


@dataclass
class PairingRequest:
    """A pending sender approval request."""

    id: str
    channel_type: str
    sender_id: str
    display_name: str
    requested_at: str = ""

    def __post_init__(self) -> None:
        if not self.requested_at:
            self.requested_at = datetime.now(timezone.utc).isoformat()


class PairingManager:
    """Manages sender approval for DM-style channels."""

    def __init__(self, path: Path = _DEFAULT_PATH) -> None:
        self._path = path
        self._approved: set[str] = set()
        self._pending: dict[str, PairingRequest] = {}
        self._load()

    def _key(self, channel_type: str, sender_id: str) -> str:
        return f"{channel_type}:{sender_id}"

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            self._approved = set(data.get("approved", []))
        except Exception:
            logger.warning("Failed to load pairing data from %s", self._path, exc_info=True)

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps({"approved": sorted(self._approved)}, indent=2))

    def is_approved(self, channel_type: str, sender_id: str) -> bool:
        """Check if a sender is approved."""
        return self._key(channel_type, sender_id) in self._approved

    def request_approval(
        self, channel_type: str, sender_id: str, display_name: str = "",
    ) -> PairingRequest:
        """Queue a sender for approval. Returns the request."""
        key = self._key(channel_type, sender_id)
        if key not in self._pending:
            import uuid
            req = PairingRequest(
                id=uuid.uuid4().hex[:12],
                channel_type=channel_type,
                sender_id=sender_id,
                display_name=display_name or sender_id,
            )
            self._pending[key] = req
            logger.info("Pairing request from %s (%s)", display_name, key)
        return self._pending[key]

    def approve(self, channel_type: str, sender_id: str) -> bool:
        """Approve a sender. Returns True if they were pending."""
        key = self._key(channel_type, sender_id)
        self._approved.add(key)
        self._pending.pop(key, None)
        self._save()
        return True

    def deny(self, channel_type: str, sender_id: str) -> bool:
        """Deny a pending sender. Returns True if they were pending."""
        key = self._key(channel_type, sender_id)
        req = self._pending.pop(key, None)
        return req is not None

    def list_pending(self) -> list[dict]:
        """Return all pending pairing requests."""
        return [asdict(r) for r in self._pending.values()]

    def list_approved(self) -> list[str]:
        """Return all approved sender keys."""
        return sorted(self._approved)
