"""mini_agent.tools.mcp_client — MCP (Model Context Protocol) server integration.

Connects to one or more MCP servers via stdio transport, discovers their tools,
and registers them into the agent's ToolRegistry so the LLM can call them just
like any built-in tool.

Typical usage::

    from mini_agent.tools.mcp_client import MCPToolLoader
    from mini_agent.tools.base import GLOBAL_REGISTRY

    loader = MCPToolLoader(GLOBAL_REGISTRY)
    loader.load_server("filesystem", command="npx", args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"])
    # GLOBAL_REGISTRY now contains all tools exposed by the filesystem MCP server.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import AsyncExitStack
from typing import Any, Optional

from mini_agent.tools.base import Tool, ToolParameter, ToolRegistry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports: mcp is an optional dependency.
# ---------------------------------------------------------------------------

def _require_mcp() -> None:
    """Raise ImportError with a helpful message if mcp is not installed."""
    try:
        import mcp  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "The 'mcp' package is required for MCP server support. "
            "Install it with: pip install mcp>=1.23.0"
        ) from exc


# ---------------------------------------------------------------------------
# Async MCP session manager (internal)
# ---------------------------------------------------------------------------

class _MCPSession:
    """Manages an async MCP client session for a single server.

    This class wraps the mcp SDK's ``stdio_client`` and ``ClientSession``
    to provide a simple sync-compatible interface via ``asyncio.run``.
    """

    def __init__(self, server_name: str, command: str, args: list[str], env: Optional[dict] = None) -> None:
        self.server_name = server_name
        self.command = command
        self.args = args
        self.env = env

    async def list_tools(self) -> list[dict]:
        """Connect to the MCP server, list available tools, then disconnect."""
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server_params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=self.env,
        )
        async with AsyncExitStack() as stack:
            read, write = await stack.enter_async_context(stdio_client(server_params))
            session: ClientSession = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            result = await session.list_tools()
            return [t.model_dump() for t in result.tools]

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Connect to the MCP server, call a tool, then disconnect."""
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server_params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=self.env,
        )
        async with AsyncExitStack() as stack:
            read, write = await stack.enter_async_context(stdio_client(server_params))
            session: ClientSession = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            # Concatenate all text content blocks
            parts: list[str] = []
            for item in result.content:
                if hasattr(item, "text"):
                    parts.append(item.text)
                else:
                    parts.append(str(item))
            return "\n".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class MCPToolLoader:
    """Discovers tools from MCP servers and registers them in a ToolRegistry.

    Each registered MCP tool is wrapped as a standard ``Tool`` instance.  When
    the agent calls the tool, MCPToolLoader opens a fresh connection to the MCP
    server, invokes the tool, and returns the result — the connection is closed
    immediately afterwards to keep things stateless and simple.

    Parameters
    ----------
    registry:
        The ``ToolRegistry`` to register discovered tools into (usually
        ``GLOBAL_REGISTRY``).
    prefix_server_name:
        When ``True`` (default), tool names are prefixed with the server name,
        e.g. ``filesystem__read_file`` instead of ``read_file``.  This prevents
        collisions when multiple servers expose tools with the same name.
    """

    def __init__(self, registry: ToolRegistry, *, prefix_server_name: bool = True) -> None:
        _require_mcp()
        self._registry = registry
        self._prefix = prefix_server_name
        # server_name → _MCPSession
        self._sessions: dict[str, _MCPSession] = {}

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def load_server(
        self,
        server_name: str,
        *,
        command: str,
        args: Optional[list[str]] = None,
        env: Optional[dict] = None,
    ) -> list[str]:
        """Connect to an MCP server, discover its tools, and register them.

        Parameters
        ----------
        server_name:
            Logical name for this server (used as tool prefix when
            ``prefix_server_name=True``).
        command:
            Executable to launch the MCP server process (e.g. ``"npx"``).
        args:
            Command-line arguments for the server process.
        env:
            Optional environment variables for the server process.

        Returns
        -------
        list[str]
            Names of all registered tool names (after any prefix).
        """
        args = args or []
        session = _MCPSession(server_name, command, args, env)
        self._sessions[server_name] = session

        try:
            raw_tools: list[dict] = asyncio.run(session.list_tools())
        except Exception as exc:
            logger.error("Failed to list tools from MCP server '%s': %s", server_name, exc)
            raise

        registered: list[str] = []
        for raw in raw_tools:
            tool_name = raw.get("name", "")
            if not tool_name:
                continue
            registered_name = f"{server_name}__{tool_name}" if self._prefix else tool_name
            tool_instance = self._build_tool(registered_name, tool_name, server_name, raw)
            self._registry.register(tool_instance)
            registered.append(registered_name)
            logger.debug("Registered MCP tool: %s", registered_name)

        logger.info("Loaded %d tools from MCP server '%s'", len(registered), server_name)
        return registered

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_tool(
        self,
        registered_name: str,
        original_name: str,
        server_name: str,
        raw: dict,
    ) -> Tool:
        """Create a ``Tool`` instance that delegates execution to the MCP server."""
        description = raw.get("description") or f"MCP tool '{original_name}' from server '{server_name}'."
        parameters = self._extract_parameters(raw)
        session = self._sessions[server_name]

        def _execute(**kwargs: Any) -> str:
            return asyncio.run(session.call_tool(original_name, kwargs))

        return Tool(
            name=registered_name,
            description=description,
            parameters=parameters,
            function=_execute,
            returns_description="Result returned by the MCP server tool.",
        )

    @staticmethod
    def _extract_parameters(raw: dict) -> list[ToolParameter]:
        """Parse MCP tool JSON-Schema into a list of ToolParameter."""
        schema: dict = raw.get("inputSchema") or {}
        props: dict = schema.get("properties") or {}
        required_fields: list = schema.get("required") or []
        params: list[ToolParameter] = []
        for param_name, prop in props.items():
            params.append(
                ToolParameter(
                    name=param_name,
                    type=prop.get("type", "string"),
                    description=prop.get("description", ""),
                    required=param_name in required_fields,
                )
            )
        return params
