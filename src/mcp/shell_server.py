"""MCP server that exposes shell command execution for the LLM."""

from __future__ import annotations

import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("shell")

DEFAULT_TIMEOUT = 60


@mcp.tool()
def run_command(command: str, cwd: str = ".", timeout: int = DEFAULT_TIMEOUT) -> str:
    """Execute a shell command and return its output.

    Runs the command via bash with the given working directory.
    Internet access is available. Output is truncated to 50000 chars.

    Args:
        command: The shell command to execute.
        cwd: Working directory for the command. Defaults to current directory.
        timeout: Maximum seconds to wait. Defaults to 60.
    """
    work_dir = Path(cwd).expanduser().resolve()
    if not work_dir.is_dir():
        return f"Error: working directory '{cwd}' does not exist."

    try:
        result = subprocess.run(
            ["bash", "-c", command],
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout}s."
    except Exception as e:
        return f"Error executing command: {e}"

    parts: list[str] = []
    if result.stdout:
        parts.append(result.stdout)
    if result.stderr:
        parts.append(f"[stderr]\n{result.stderr}")
    parts.append(f"[exit code: {result.returncode}]")

    output = "\n".join(parts)
    if len(output) > 50_000:
        output = output[:50_000] + "\n...(truncated)"
    return output


if __name__ == "__main__":
    mcp.run()
