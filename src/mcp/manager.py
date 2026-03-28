"""MCP client manager — connects to MCP servers and exposes their tools."""

from __future__ import annotations

import asyncio
import json
import os
import threading
from contextlib import AsyncExitStack
from functools import lru_cache
from logging import getLogger
from pathlib import Path

logger = getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "mcp_servers.json"


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
        self._lazy_configs: dict[str, dict] = {}
        self._lazy_connected: set[str] = set()

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

    def _run_sync(self, coro):
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
            is_lazy = server_cfg.get("lazy", False)
            try:
                if is_lazy:
                    await self._discover_lazy(
                        server_name, server_cfg, ClientSession, StdioServerParameters, stdio_client,
                    )
                else:
                    await self._connect_one(
                        server_name, server_cfg, ClientSession, StdioServerParameters, stdio_client,
                    )
            except Exception as exc:
                logger.warning("MCP server '%s' failed to connect: %s", server_name, exc)

    async def _discover_lazy(
        self, name: str, cfg: dict, ClientSession: type, StdioServerParameters: type, stdio_client: object,
    ) -> None:
        """Connect to a lazy server to discover its tools, then disconnect."""
        temp_stack = AsyncExitStack()
        await temp_stack.__aenter__()

        resolved_env = self._resolve_env(cfg)
        params = StdioServerParameters(
            command=cfg["command"],
            args=cfg.get("args", []),
            env={**os.environ, **resolved_env},
        )

        devnull = open(os.devnull, "w")
        read_stream, write_stream = await temp_stack.enter_async_context(
            stdio_client(params, errlog=devnull)
        )
        session = await temp_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await session.initialize()

        tools_result = await session.list_tools()
        for tool in tools_result.tools:
            self._tools.append({
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.inputSchema,
            })
            self._tool_server_map[tool.name] = name

        await temp_stack.aclose()

        self._lazy_configs[name] = cfg
        logger.info(
            "MCP server '%s' (lazy): %d tool(s) discovered", name, len(tools_result.tools),
        )

    async def _ensure_lazy_connected(self, server_name: str) -> None:
        """Connect a lazy server on-demand if not already connected."""
        if server_name in self._lazy_connected:
            return

        from mcp import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        cfg = self._lazy_configs[server_name]
        await self._connect_one(
            server_name, cfg, ClientSession, StdioServerParameters, stdio_client,
        )
        self._lazy_connected.add(server_name)
        logger.info("MCP server '%s' (lazy): connected on demand", server_name)

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

    async def _connect_one(self, name, cfg, ClientSession, StdioServerParameters, stdio_client):
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

        # Skip tool registration if already discovered (lazy reconnect)
        if name not in self._lazy_configs:
            tools_result = await session.list_tools()
            for tool in tools_result.tools:
                self._tools.append({
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.inputSchema,
                })
                self._tool_server_map[tool.name] = name

        logger.info(
            "MCP server '%s': connected", name,
        )

    async def _call_tool_async(self, name: str, arguments: dict) -> str:
        server_name = self._tool_server_map.get(name)
        if not server_name:
            return f"Error: tool '{name}' not available"

        # Lazy server: connect on first tool call
        if server_name in self._lazy_configs and server_name not in self._lazy_connected:
            await self._ensure_lazy_connected(server_name)

        if server_name not in self._sessions:
            return f"Error: tool '{name}' not available"

        try:
            return await self._execute_tool_call(server_name, name, arguments)
        except Exception:
            # Session may be stale — reconnect and retry once
            if server_name in self._lazy_configs:
                logger.info("MCP server '%s': session broken, reconnecting", server_name)
                self._lazy_connected.discard(server_name)
                self._sessions.pop(server_name, None)
                try:
                    await self._ensure_lazy_connected(server_name)
                    return await self._execute_tool_call(server_name, name, arguments)
                except Exception as exc:
                    return f"Error: tool '{name}' failed after reconnect: {exc}"
            return f"Error: tool '{name}' call failed"

    async def _execute_tool_call(self, server_name: str, name: str, arguments: dict) -> str:
        session = self._sessions[server_name]
        result = await session.call_tool(name, arguments)

        texts: list[str] = []
        for block in result.content:
            if hasattr(block, "text"):
                texts.append(block.text)
        return "\n".join(texts) if texts else str(result.content)


@lru_cache(maxsize=1)
def get_mcp_manager() -> MCPManager | None:
    """Return the cached MCPManager singleton.

    Returns
    -------
    MCPManager or None
        The instance set by :func:`init_mcp_manager`, or None if not
        initialised or no tools were discovered.
    """
    return _singleton


_singleton: MCPManager | None = None


def init_mcp_manager(config_paths: list[Path] | None = None) -> MCPManager | None:
    """Initialise the MCPManager singleton and cache it.

    Connects to all MCP servers found in the provided paths. Safe to call
    multiple times — subsequent calls are no-ops.

    Parameters
    ----------
    config_paths : list of Path or None
        JSON config files to load. Falls back to the project-root
        ``mcp_servers.json`` when empty or None.

    Returns
    -------
    MCPManager or None
        The shared manager instance, or None if no configs were found or
        no tools were discovered.
    """
    global _singleton

    if get_mcp_manager.cache_info().currsize:
        return get_mcp_manager()

    paths = config_paths if config_paths is not None else []
    if not paths and _DEFAULT_CONFIG_PATH.exists():
        paths = [_DEFAULT_CONFIG_PATH]

    if not paths:
        get_mcp_manager.cache_clear()
        get_mcp_manager()
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

    get_mcp_manager.cache_clear()
    return get_mcp_manager()
