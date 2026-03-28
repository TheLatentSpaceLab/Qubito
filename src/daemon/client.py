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
        """Initialize the client pointing at the daemon.

        Parameters
        ----------
        host : str or None
            Daemon hostname. Defaults to DAEMON_HOST from constants.
        port : int or None
            Daemon port. Defaults to DAEMON_PORT from constants.
        """
        base = f"http://{host or DAEMON_HOST}:{port or DAEMON_PORT}"
        self._http = httpx.Client(base_url=base, timeout=120)

    def is_daemon_running(self) -> bool:
        """Check if the daemon is reachable.

        Returns
        -------
        bool
            True if the daemon responds to ``/status``.
        """
        try:
            resp = self._http.get("/status")
            return resp.status_code == 200
        except httpx.ConnectError:
            return False

    def status(self) -> dict:
        """Fetch daemon status.

        Returns
        -------
        dict
            JSON payload from ``GET /status``.
        """
        return self._http.get("/status").json()

    def create_session(self, character: str | None = None) -> SessionData:
        """Create a new chat session on the daemon.

        Parameters
        ----------
        character : str or None
            Character filename to use. Uses the server default when None.

        Returns
        -------
        SessionData
            Session metadata including id, character info, and greeting.
        """
        body: dict = {}
        if character:
            body["character"] = character
        resp = self._http.post("/sessions", json=body)
        resp.raise_for_status()
        data = resp.json()
        return SessionData(**data)

    def list_sessions(self) -> list[dict]:
        """List all active sessions.

        Returns
        -------
        list of dict
            Session info dicts from ``GET /sessions``.
        """
        return self._http.get("/sessions").json()

    def delete_session(self, session_id: str) -> None:
        """Delete a session by id.

        Parameters
        ----------
        session_id : str
            The session to remove.
        """
        self._http.delete(f"/sessions/{session_id}")

    def send_message(
        self,
        session_id: str,
        message: str,
        skill_instructions: str | None = None,
    ) -> tuple[str, float]:
        """Send a message to a session and wait for the response.

        Parameters
        ----------
        session_id : str
            Target session id.
        message : str
            User message text.
        skill_instructions : str or None
            Optional skill-specific instructions injected into the prompt.

        Returns
        -------
        tuple of (str, float)
            The agent's response text and elapsed time in seconds.
        """
        body: dict = {"session_id": session_id, "message": message}
        if skill_instructions:
            body["skill_instructions"] = skill_instructions
        resp = self._http.post("/message", json=body)
        resp.raise_for_status()
        data = resp.json()
        return data["response"], data["elapsed"]

    def get_history(self, session_id: str) -> list[dict]:
        """Retrieve conversation history for a session.

        Parameters
        ----------
        session_id : str
            The session to query.

        Returns
        -------
        list of dict
            Message dicts with ``role`` and ``content`` keys.
        """
        resp = self._http.get(f"/sessions/{session_id}/history")
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._http.close()
