"""Thin HTTP client for talking to the Qubito daemon API."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from src.constants import DAEMON_HOST, DAEMON_PORT


@dataclass
class SessionData:
    """Subset of session info returned by the daemon."""

    id: str
    character_name: str
    emoji: str
    color: str
    hi_message: str = ""


class DaemonClient:
    """Synchronous client wrapping the daemon HTTP API."""

    def __init__(self, host: str | None = None, port: int | None = None) -> None:
        base = f"http://{host or DAEMON_HOST}:{port or DAEMON_PORT}"
        self._http = httpx.Client(base_url=base, timeout=120)

    def is_daemon_running(self) -> bool:
        try:
            resp = self._http.get("/status")
            return resp.status_code == 200
        except httpx.ConnectError:
            return False

    def status(self) -> dict:
        return self._http.get("/status").json()

    def create_session(self, character: str | None = None) -> SessionData:
        body: dict = {}
        if character:
            body["character"] = character
        resp = self._http.post("/sessions", json=body)
        resp.raise_for_status()
        data = resp.json()
        return SessionData(**data)

    def list_sessions(self) -> list[dict]:
        return self._http.get("/sessions").json()

    def delete_session(self, session_id: str) -> None:
        self._http.delete(f"/sessions/{session_id}")

    def send_message(
        self,
        session_id: str,
        message: str,
        skill_instructions: str | None = None,
    ) -> tuple[str, float]:
        """Send a message and return (response_text, elapsed_seconds)."""
        body: dict = {"session_id": session_id, "message": message}
        if skill_instructions:
            body["skill_instructions"] = skill_instructions
        resp = self._http.post("/message", json=body)
        resp.raise_for_status()
        data = resp.json()
        return data["response"], data["elapsed"]

    def get_history(self, session_id: str) -> list[dict]:
        resp = self._http.get(f"/sessions/{session_id}/history")
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._http.close()
