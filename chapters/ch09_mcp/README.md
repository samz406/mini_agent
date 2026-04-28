# 第九章：MCP（Model Context Protocol）

## 你将学到什么

本章介绍 **MCP（Model Context Protocol，模型上下文协议）**，这是 Anthropic 提出的开放标准，定义了 AI Agent 与外部工具、数据源之间通信的统一协议。你将：

- 理解 MCP 是什么、解决了什么问题
- 掌握 MCP 的核心概念：Server、Client、Tools、Resources、Prompts
- 学会用 Python `mcp` SDK 编写一个简单的 MCP Server
- 学会在 Agent 中接入 MCP Server，动态获取并调用它提供的工具

> 📖 学完本章后，可以阅读 `extended_reading.md`，了解 MCP 与主流 Agent 框架的整合方式。

---

## 为什么需要 MCP？

### 工具集成的困境

在没有 MCP 之前，每个 Agent 框架都有自己的工具定义格式：

```
OpenAI Function Calling:  {"type": "function", "function": {"name": ..., "parameters": ...}}
LangChain Tool:           class MyTool(BaseTool): ...
mini_agent Tool:          @tool(name=..., description=..., parameters=[...])
```

这意味着：
- 同一个工具（比如"搜索 GitHub Issues"）要为每个框架写一遍适配代码
- 社区写的工具库无法在不同 Agent 框架间复用
- 工具的安全、权限、生命周期管理各自为政

### MCP 的解决方案

MCP 就像工具领域的 **USB 接口**：

```
           ┌─────────────────────────────────────┐
           │           MCP 生态                   │
           │                                     │
           │  MCP Server        MCP Server        │
           │  (filesystem)      (github)          │
           │       │                 │            │
           │       └────────┬────────┘            │
           │            MCP 协议                   │
           │                │                     │
           │       ┌────────┴────────┐            │
           │       │                 │            │
           │   mini_agent         Claude           │
           │   LangChain          Cursor           │
           │   (任何 Agent)       (任何 IDE)       │
           └─────────────────────────────────────┘
```

任何遵循 MCP 协议的工具，都可以被任何支持 MCP 的 Agent 使用，无需任何额外适配代码。

---

## MCP 核心概念

### Server（服务端）

MCP Server 是一个独立进程，它：
- 对外暴露工具（Tools）、资源（Resources）、提示词模板（Prompts）
- 通过标准输入/输出（stdio）或 HTTP（SSE/Streamable HTTP）与 Client 通信
- 一个 Server 可以提供多个工具

### Client（客户端）

MCP Client 嵌入在 Agent 或 IDE 中，它：
- 启动 MCP Server 进程
- 调用 Server 的 `list_tools` 接口获取工具列表
- 按需调用 `call_tool` 执行工具

### 三类核心能力

| 能力 | 说明 | 例子 |
|------|------|------|
| **Tools** | 可执行的函数，Agent 调用后得到结果 | 读文件、查数据库、发送消息 |
| **Resources** | 可读取的数据，类似"只读文件" | 当前用户信息、系统配置、日志文件 |
| **Prompts** | 可复用的提示词模板 | "代码审查专家"提示词 |

本章重点关注 **Tools**，这也是 Agent 最常用的 MCP 能力。

---

## 通信协议

MCP 基于 JSON-RPC 2.0 协议，支持两种传输方式：

```
stdio 传输（最常用，适合本地工具）：
  Agent →  子进程 stdin  → MCP Server
  Agent ← 子进程 stdout ← MCP Server

HTTP 传输（适合远程工具）：
  Agent → HTTP POST → MCP Server（SSE 或 Streamable HTTP）
```

典型的消息交换流程：

```
Client                          Server
  │                               │
  │── initialize() ──────────────>│  建立会话，协商协议版本
  │<── initialized ───────────────│
  │                               │
  │── tools/list ────────────────>│  获取工具列表
  │<── [{name, description, ...}] │
  │                               │
  │── tools/call {name, args} ───>│  调用工具
  │<── {content: [{type, text}]} ─│  返回结果
  │                               │
```

---

## 如何运行

```bash
cd chapters/ch09_mcp
pip install mcp>=1.23.0

# 运行演示（内置模拟 MCP Server，无需额外依赖）
python mcp_demo.py
```

### 使用 mini-agent 接入真实 MCP Server

```bash
# 安装 Node.js 版 filesystem MCP Server
npm install -g @modelcontextprotocol/server-filesystem

# 启动 mini-agent 并挂载 MCP Server
mini-agent --mcp-server "fs:npx:-y:@modelcontextprotocol/server-filesystem:/tmp"

# 挂载多个 MCP Server
mini-agent \
  --mcp-server "fs:npx:-y:@modelcontextprotocol/server-filesystem:/tmp" \
  --mcp-server "git:uvx:mcp-server-git:--repository:."
```

---

## 动手写一个 MCP Server

下面是本章示例 `mcp_demo.py` 中的核心代码，展示如何用 `mcp` SDK 定义一个 Server：

```python
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

app = Server("my-tools")

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="greet",
            description="向某人打招呼",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "名字"},
                },
                "required": ["name"],
            },
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "greet":
        return [types.TextContent(type="text", text=f"你好，{arguments['name']}！")]
    raise ValueError(f"未知工具: {name}")

# 启动 Server（监听 stdin/stdout）
async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())
```

然后在 Agent 中使用这个 Server：

```python
from mini_agent.tools.mcp_client import MCPToolLoader
from mini_agent.tools.base import GLOBAL_REGISTRY

loader = MCPToolLoader(GLOBAL_REGISTRY)
loader.load_server("my-tools", command="python", args=["my_server.py"])
# GLOBAL_REGISTRY 中现在有了 "my-tools__greet" 工具
```

---

## 核心设计模式

| 模式 | 体现 |
|------|------|
| **协议抽象（Protocol Abstraction）** | JSON-RPC 协议解耦了 Client 和 Server 的实现语言和框架 |
| **进程隔离（Process Isolation）** | Server 运行在独立进程中，崩溃不影响 Agent 主进程 |
| **发现模式（Discovery）** | Client 通过 `list_tools` 动态发现 Server 提供的工具，无需硬编码 |
| **适配器模式（Adapter）** | MCPToolLoader 将 MCP 工具适配为 mini_agent 的 Tool 格式 |

---

## 与前几章的对比

| 维度 | ch03 工具系统 | ch07 技能系统 | ch08 插件系统 | **ch09 MCP** |
|------|------------|------------|------------|------------|
| 工具定义位置 | Agent 源码内 | Agent 源码内 | 本地插件目录 | **独立进程** |
| 跨语言支持 | ❌ Python only | ❌ Python only | ❌ Python only | ✅ 任何语言 |
| 跨框架复用 | ❌ 仅 mini_agent | ❌ 仅 mini_agent | ❌ 仅 mini_agent | ✅ 所有 MCP 客户端 |
| 工具来源 | 自己写 | 自己写 | 自己写 | ✅ 社区生态（数百个） |
| 进程隔离 | ❌ 主进程直接运行 | ❌ 主进程直接运行 | ❌ 主进程直接运行 | ✅ 独立子进程 |
