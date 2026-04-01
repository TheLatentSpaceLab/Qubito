"""MCP client manager — connects to MCP servers and exposes their tools."""

from __future__ import annotations

import asyncio
import json
import os
import threading
from contextlib import AsyncExitStack
from logging import getLogger
from pathlib import Path

logger = getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / ".mcp.json"


class MCPManager:
    """Sync wrapper around async MCP client sessions.

    Runs an asyncio event loop in a background thread so the rest of the
    (synchronous) application can call :meth:`get_tools` and :meth:`call_tool`
    without ``await``.
    """

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._exit_stack: AsyncExitStack | None = None
        self._sessions: dict[str, object] = {}
        self._tools: list[dict] = []
        self._tool_server_map: dict[str, str] = {}
        self._all_configs: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Public (sync) API
    # ------------------------------------------------------------------

    def connect(self, config_path: str) -> None:
        """Read a config file and connect to every MCP server listed there.

        Parameters
        ----------
        config_path : str
            Path to a JSON file mapping server names to their configurations.
        """
        self._run_sync(self._connect_all(config_path))

    def get_tools(self) -> list[dict]:
        """Return tool definitions from all connected servers.

        Each dict has keys ``name``, ``description``, and ``input_schema``.
        """
        return self._tools

    def call_tool(self, name: str, arguments: dict) -> str:
        """Execute a tool by name and return the textual result.

        Parameters
        ----------
        name : str
            Tool name as registered by one of the connected servers.
        arguments : dict
            Keyword arguments forwarded to the MCP tool.

        Returns
        -------
        str
            Concatenated text blocks from the tool result.
        """
        return self._run_sync(self._call_tool_async(name, arguments))

    def close(self) -> None:
        """Shut down every server connection and stop the event loop."""
        if self._exit_stack:
            try:
                self._run_sync(self._exit_stack.aclose())
            except Exception:
                pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _run_sync(self, coro):  # type: ignore[type-arg]
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=60)

    async def _connect_all(self, config_path: str) -> None:
        from mcp import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()

        with open(config_path) as fh:
            config: dict = json.load(fh)

        for server_name, server_cfg in config.items():
            self._all_configs[server_name] = server_cfg
            try:
                await self._connect_one(
                    server_name, server_cfg, ClientSession, StdioServerParameters, stdio_client,
                )
            except Exception as exc:
                logger.warning("MCP server '%s' failed to connect: %s", server_name, exc)

    @staticmethod
    def _resolve_env(cfg: dict) -> dict[str, str]:
        """Resolve environment variable references in server config.

        Parameters
        ----------
        cfg : dict
            Server config block potentially containing ``env`` with
            ``${VAR}`` references.

        Returns
        -------
        dict of str to str
            Resolved environment variable mappings.
        """
        resolved: dict[str, str] = {}
        for k, v in cfg.get("env", {}).items():
            if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                resolved[k] = os.environ.get(v[2:-1], "")
            else:
                resolved[k] = str(v)
        return resolved

    async def _connect_one(
        self, name: str, cfg: dict, ClientSession: type, StdioServerParameters: type, stdio_client: object,
    ) -> None:
        resolved_env = self._resolve_env(cfg)
        params = StdioServerParameters(
            command=cfg["command"],
            args=cfg.get("args", []),
            env={**os.environ, **resolved_env},
        )

        devnull = open(os.devnull, "w")
        read_stream, write_stream = await self._exit_stack.enter_async_context(
            stdio_client(params, errlog=devnull)
        )
        session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await session.initialize()

        self._sessions[name] = session

        tools_result = await session.list_tools()
        for tool in tools_result.tools:
            self._tools.append({
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.inputSchema,
            })
            self._tool_server_map[tool.name] = name

        logger.info("MCP server '%s': connected", name)

    async def _call_tool_async(self, name: str, arguments: dict) -> str:
        server_name = self._tool_server_map.get(name)
        if not server_name:
            return f"Error: tool '{name}' not available"

        if server_name not in self._sessions:
            return f"Error: tool '{name}' not available"

        try:
            return await self._execute_tool_call(server_name, name, arguments)
        except Exception as exc:
            logger.warning("MCP tool '%s' failed: %s. Attempting reconnect.", name, exc)
            self._sessions.pop(server_name, None)

            if server_name in self._all_configs:
                try:
                    from mcp import ClientSession
                    from mcp.client.stdio import StdioServerParameters, stdio_client
                    await self._connect_one(
                        server_name, self._all_configs[server_name],
                        ClientSession, StdioServerParameters, stdio_client,
                    )
                    return await self._execute_tool_call(server_name, name, arguments)
                except Exception as retry_exc:
                    return f"Error: tool '{name}' failed after reconnect: {retry_exc}"
            return f"Error: tool '{name}' call failed: {exc}"

    async def _execute_tool_call(self, server_name: str, name: str, arguments: dict) -> str:
        session = self._sessions[server_name]
        try:
            result = await asyncio.wait_for(
                session.call_tool(name, arguments),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            logger.warning("MCP tool '%s' timed out after 30s", name)
            raise

        texts: list[str] = []
        for block in result.content:
            if hasattr(block, "text"):
                texts.append(block.text)
        return "\n".join(texts) if texts else str(result.content)


_singleton: MCPManager | None = None
_initialized: bool = False


def get_mcp_manager() -> MCPManager | None:
    """Return the MCPManager singleton, or None if not yet initialised."""
    return _singleton


def init_mcp_manager(config_paths: list[Path] | None = None) -> MCPManager | None:
    """Initialise the MCPManager singleton. Safe to call multiple times.

    Parameters
    ----------
    config_paths : list of Path or None
        JSON config files to load. Falls back to the project-root
        ``.mcp.json`` when empty or None.
    """
    global _singleton, _initialized

    if _initialized:
        return _singleton

    _initialized = True
    paths = config_paths if config_paths is not None else []
    if not paths and _DEFAULT_CONFIG_PATH.exists():
        paths = [_DEFAULT_CONFIG_PATH]

    if not paths:
        return None

    try:
        manager = MCPManager()
        for p in paths:
            manager.connect(str(p))

        if manager.get_tools():
            tool_names = [t["name"] for t in manager.get_tools()]
            logger.info("MCP tools available: %s", ", ".join(tool_names))
            _singleton = manager
        else:
            manager.close()
    except Exception as exc:
        logger.warning("MCP initialization failed: %s", exc)

    return _singleton
