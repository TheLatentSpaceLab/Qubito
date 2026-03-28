"""Qubito CLI entry point with subcommands."""

from __future__ import annotations

import argparse
import logging


def _logging_setup() -> None:
    """Configure application and dependency logging levels."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("mcp").setLevel(logging.CRITICAL)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qubito", description="Qubito — natural-language OS")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("chat", help="Interactive terminal chat")
    sub.add_parser("init", help="Set up ~/.qubito/")

    np = sub.add_parser("new-project", help="Create .qubito/ overrides in a project directory")
    np.add_argument("path", nargs="?", default=None, help="Project path (default: current directory)")

    sub.add_parser("telegram", help="Run the Telegram bot")

    dp = sub.add_parser("daemon", help="Manage the background daemon")
    dp.add_argument("action", choices=["start", "stop", "status"], help="Daemon action")
    dp.add_argument("--host", default=None, help="Bind host (default: 127.0.0.1)")
    dp.add_argument("--port", type=int, default=None, help="Bind port (default: 8741)")
    dp.add_argument("--foreground", action="store_true", help="Run in foreground (for systemd)")

    return parser


def main() -> None:
    """CLI entry point."""
    _logging_setup()

    parser = _build_parser()
    args = parser.parse_args()

    command = args.command or "chat"

    if command == "chat":
        from src.cli.cmd_chat import run_chat
        run_chat()
    elif command == "init":
        from src.cli.cmd_init import run_init
        run_init()
    elif command == "new-project":
        from src.cli.cmd_new_project import run_new_project
        run_new_project(path=args.path)
    elif command == "telegram":
        from src.cli.cmd_telegram import run_telegram
        run_telegram()
    elif command == "daemon":
        from src.cli.cmd_daemon import run_daemon
        run_daemon(args.action, host=args.host, port=args.port, foreground=args.foreground)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
