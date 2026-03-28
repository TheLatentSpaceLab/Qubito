"""Abstract base class for messaging channels."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.daemon.client import DaemonClient


class Channel(ABC):
    """A messaging frontend that connects a user interface to the daemon."""

    def __init__(self, client: DaemonClient | None = None) -> None:
        self._client = client or DaemonClient()

    @property
    def client(self) -> DaemonClient:
        """The daemon client used by this channel."""
        return self._client

    @abstractmethod
    def start(self) -> None:
        """Start the channel's main loop (blocking)."""

    @abstractmethod
    def stop(self) -> None:
        """Gracefully shut down the channel."""

    def ensure_daemon(self) -> None:
        """Raise if the daemon is not reachable."""
        if not self._client.is_daemon_running():
            raise RuntimeError(
                "Daemon is not running. Start it first with: qubito daemon start"
            )
