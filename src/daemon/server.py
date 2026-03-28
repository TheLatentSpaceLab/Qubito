"""Uvicorn server runner for the Qubito daemon."""

from __future__ import annotations

import logging

import uvicorn

from src.constants import DAEMON_HOST, DAEMON_PORT


def run_server(host: str | None = None, port: int | None = None) -> None:
    """Start the daemon HTTP server (blocks until shutdown).

    Parameters
    ----------
    host : str or None
        Bind address. Defaults to DAEMON_HOST.
    port : int or None
        Bind port. Defaults to DAEMON_PORT.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("mcp").setLevel(logging.CRITICAL)

    uvicorn.run(
        "src.daemon.api:create_app",
        factory=True,
        host=host or DAEMON_HOST,
        port=port or DAEMON_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    run_server()
