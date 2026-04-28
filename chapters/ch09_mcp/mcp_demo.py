"""Chapter 9: MCP (Model Context Protocol) — Client & Server demo.

Teaches:
- How to define an MCP Server with tools using the mcp SDK
- How to build an MCP Client that connects to a Server, lists tools, and calls them
- How MCPToolLoader wraps MCP tools into mini_agent's Tool format

The demo is self-contained: it spins up an in-process MCP Server (via subprocess),
then uses an MCP Client to discover and call its tools.

Run:
    pip install mcp>=1.23.0
    python mcp_demo.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import textwrap
from contextlib import AsyncExitStack

# ---------------------------------------------------------------------------
# Part 1: A minimal standalone MCP Server (runs as __main__ via subprocess)
# ---------------------------------------------------------------------------

SERVER_SCRIPT = textwrap.dedent("""\
    import asyncio
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp import types

    app = Server("demo-tools")

    @app.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="greet",
                description="向某人打招呼，返回问候语",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "要问候的名字"},
                    },
                    "required": ["name"],
                },
            ),
            types.Tool(
                name="add",
                description="将两个整数相加",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "a": {"type": "integer", "description": "第一个整数"},
                        "b": {"type": "integer", "description": "第二个整数"},
                    },
                    "required": ["a", "b"],
                },
            ),
        ]

    @app.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        if name == "greet":
            return [types.TextContent(type="text", text=f"你好，{arguments['name']}！欢迎使用 MCP 工具！")]
        if name == "add":
            result = int(arguments["a"]) + int(arguments["b"])
            return [types.TextContent(type="text", text=str(result))]
        raise ValueError(f"未知工具: {name}")

    async def main() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())

    asyncio.run(main())
""")


# ---------------------------------------------------------------------------
# Part 2: MCP Client — connects to a Server and calls its tools
# ---------------------------------------------------------------------------

class MCPDemoClient:
    """A minimal MCP client for demonstration purposes.

    In production, see ``mini_agent.tools.mcp_client.MCPToolLoader`` which
    automatically wraps MCP tools into the agent's ToolRegistry.
    """

    def __init__(self) -> None:
        self._session = None
        self._exit_stack = AsyncExitStack()

    async def connect(self, command: str, args: list[str]) -> None:
        """Start the MCP server process and initialise the session."""
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server_params = StdioServerParameters(command=command, args=args)
        read, write = await self._exit_stack.enter_async_context(stdio_client(server_params))
        self._session = await self._exit_stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()

    async def list_tools(self) -> list[dict]:
        """Return metadata for all tools exposed by the server."""
        result = await self._session.list_tools()
        return [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.inputSchema,
            }
            for t in result.tools
        ]

    async def call_tool(self, name: str, arguments: dict) -> str:
        """Call a tool by name and return its text output."""
        result = await self._session.call_tool(name, arguments)
        return "\n".join(
            item.text if hasattr(item, "text") else str(item)
            for item in result.content
        )

    async def disconnect(self) -> None:
        """Close the session and terminate the server process."""
        await self._exit_stack.aclose()


# ---------------------------------------------------------------------------
# Part 3: Standalone mini_agent ToolRegistry integration (without running Agent)
# ---------------------------------------------------------------------------

def _demo_tool_registry_integration(server_command: str, server_args: list[str]) -> None:
    """Show how MCPToolLoader registers MCP tools into a ToolRegistry."""
    # Local lightweight registry (not the global one, to keep this demo self-contained)
    from dataclasses import dataclass, field
    from typing import Callable, Any, Optional

    # Re-use mini_agent's ToolRegistry if available, otherwise use a stub
    try:
        from mini_agent.tools.base import ToolRegistry
        from mini_agent.tools.mcp_client import MCPToolLoader
        registry = ToolRegistry()
        loader = MCPToolLoader(registry, prefix_server_name=True)
        registered = loader.load_server("demo", command=server_command, args=server_args)
        print("\n--- mini_agent ToolRegistry integration ---")
        print(f"Registered tools: {registered}")
        for t in registry.list_tools():
            result = t.execute(name="mini_agent") if t.name == "demo__greet" else t.execute(a=3, b=7)
            print(f"  {t.name}() → {result.result}")
    except ImportError:
        print("\n[mini_agent not installed — skipping ToolRegistry integration demo]")


# ---------------------------------------------------------------------------
# Main async demo
# ---------------------------------------------------------------------------

async def _async_main() -> tuple[str, str, list[str]]:
    """Run the full MCP client-server demo, returning server info for sync follow-up."""
    # Write server script to a temp file
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as fh:
        fh.write(SERVER_SCRIPT)
        server_file = fh.name

    print("=" * 60)
    print("Chapter 9: MCP Demo")
    print("=" * 60)

    # --- Step 1: Connect to MCP Server ---
    print("\n[1] 启动 MCP Server 并建立连接 …")
    client = MCPDemoClient()
    await client.connect(sys.executable, [server_file])
    print("    ✓ 连接成功")

    # --- Step 2: List tools ---
    print("\n[2] 发现 Server 暴露的工具 (tools/list) …")
    tools = await client.list_tools()
    for t in tools:
        print(f"    • {t['name']}: {t['description']}")
        schema = t.get("inputSchema", {})
        for param, info in schema.get("properties", {}).items():
            req = "必填" if param in schema.get("required", []) else "可选"
            print(f"        - {param} ({info.get('type', '?')}, {req}): {info.get('description', '')}")

    # --- Step 3: Call tools ---
    print("\n[3] 调用工具 (tools/call) …")
    result_greet = await client.call_tool("greet", {"name": "世界"})
    print(f"    greet(name='世界') → {result_greet}")

    result_add = await client.call_tool("add", {"a": 40, "b": 2})
    print(f"    add(a=40, b=2) → {result_add}")

    # --- Step 4: Disconnect ---
    print("\n[4] 断开连接，MCP Server 进程退出")
    await client.disconnect()
    print("    ✓ 连接已关闭")

    return sys.executable, server_file, [server_file]


def main() -> None:
    """Entry point: check mcp is installed, then run the demo."""
    import os

    try:
        import mcp  # noqa: F401
    except ImportError:
        print("请先安装 mcp 包：pip install mcp>=1.23.0")
        sys.exit(1)

    python_exe, server_file, server_args = asyncio.run(_async_main())

    try:
        # --- Step 5: ToolRegistry integration (must be outside async context) ---
        _demo_tool_registry_integration(python_exe, server_args)

        print("\n" + "=" * 60)
        print("Demo 完成！")
        print("=" * 60)
        print("""
下一步：
  • 运行真实 MCP Server（需要 Node.js）：
      npx -y @modelcontextprotocol/server-filesystem /tmp
  • 在 mini-agent 中挂载：
      mini-agent --mcp-server "fs:npx:-y:@modelcontextprotocol/server-filesystem:/tmp"
  • 查看 MCP 服务器列表：
      https://github.com/modelcontextprotocol/servers
""")
    finally:
        os.unlink(server_file)


if __name__ == "__main__":
    main()
