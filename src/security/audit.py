"""Append-only audit log with hash chain for tamper evidence."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from logging import getLogger
from pathlib import Path

logger = getLogger(__name__)

_DEFAULT_PATH = Path.home() / ".qubito" / "audit.db"

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    target TEXT NOT NULL DEFAULT '',
    details TEXT NOT NULL DEFAULT '',
    checksum TEXT NOT NULL
);
"""


class AuditLog:
    """Append-only audit log backed by SQLite with hash chain integrity."""

    def __init__(self, db_path: Path | str = _DEFAULT_PATH) -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._last_checksum = self._get_last_checksum()

    def _get_last_checksum(self) -> str:
        row = self._conn.execute(
            "SELECT checksum FROM audit_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return row["checksum"] if row else "0" * 64

    def record(
        self,
        action: str,
        actor: str = "",
        target: str = "",
        details: str = "",
    ) -> None:
        """Append an entry to the audit log.

        Parameters
        ----------
        action : str
            What happened (e.g. "tool_call", "session_create", "skill_execute").
        actor : str
            Who performed the action (session ID, user ID, etc.).
        target : str
            What was affected (tool name, session ID, etc.).
        details : str
            Additional context (JSON-serializable string preferred).
        """
        now = datetime.now(timezone.utc).isoformat()
        row_data = f"{now}|{actor}|{action}|{target}|{details}"
        checksum = hashlib.sha256(
            (self._last_checksum + row_data).encode()
        ).hexdigest()

        self._conn.execute(
            "INSERT INTO audit_log (timestamp, actor, action, target, details, checksum) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (now, actor, action, target, details, checksum),
        )
        self._conn.commit()
        self._last_checksum = checksum

    def query(
        self,
        since: str | None = None,
        until: str | None = None,
        actor: str | None = None,
        action: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query audit log entries with optional filters."""
        conditions: list[str] = []
        params: list[str | int] = []

        if since:
            conditions.append("timestamp >= ?")
            params.append(since)
        if until:
            conditions.append("timestamp <= ?")
            params.append(until)
        if actor:
            conditions.append("actor = ?")
            params.append(actor)
        if action:
            conditions.append("action = ?")
            params.append(action)

        where = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)

        rows = self._conn.execute(
            f"SELECT * FROM audit_log WHERE {where} ORDER BY id DESC LIMIT ?",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def verify(self) -> bool:
        """Validate the hash chain. Returns True if integrity is intact."""
        rows = self._conn.execute(
            "SELECT timestamp, actor, action, target, details, checksum "
            "FROM audit_log ORDER BY id"
        ).fetchall()

        prev = "0" * 64
        for row in rows:
            row_data = f"{row['timestamp']}|{row['actor']}|{row['action']}|{row['target']}|{row['details']}"
            expected = hashlib.sha256((prev + row_data).encode()).hexdigest()
            if expected != row["checksum"]:
                logger.warning("Audit chain broken at timestamp %s", row["timestamp"])
                return False
            prev = row["checksum"]
        return True

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
