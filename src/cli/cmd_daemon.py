"""Handler for the ``qubito daemon`` subcommand."""

from __future__ import annotations


def run_daemon(action: str, host: str | None = None, port: int | None = None, foreground: bool = False) -> None:
    """Dispatch daemon start/stop/status actions."""
    from src.daemon.lifecycle import start_daemon, stop_daemon, daemon_status

    if action == "start":
        start_daemon(host=host, port=port, foreground=foreground)
    elif action == "stop":
        stop_daemon()
    elif action == "status":
        info = daemon_status()
        if info is None:
            print("Daemon is not running")
        else:
            print(f"PID: {info.get('pid', '?')}")
            print(f"Status: {info.get('status', '?')}")
            print(f"Sessions: {info.get('sessions_count', '?')}")
            uptime = info.get("uptime_seconds")
            if uptime is not None:
                print(f"Uptime: {uptime:.0f}s")
    else:
        print(f"Unknown action: {action}. Use start, stop, or status.")
