# 扩展阅读：MCP 在主流 Agent 项目中的应用

## 本章回顾

ch09 展示了 MCP（Model Context Protocol）的核心机制：Server 暴露工具，Client 动态发现并调用工具，MCPToolLoader 将 MCP 工具适配到 mini_agent 的 ToolRegistry 中。核心价值：**工具的定义与 Agent 解耦，一次实现处处可用**。

---

## MCP 协议演进背景

MCP 由 Anthropic 于 2024 年 11 月开源，解决的核心问题是 **M×N 工具集成爆炸**：

```
没有 MCP 时：
  M 个 Agent × N 种工具 = M×N 个适配器（每对都要单独写）

有了 MCP 后：
  M 个 Agent + N 个 MCP Server = M+N 个实现（各写一次即可）
```

2025 年初，OpenAI、Google、Microsoft 相继宣布支持 MCP，使其成为事实上的行业标准。

---

## 各主流项目的 MCP 集成方式

### 1. nanobot（HKUDS）：配置文件驱动的 MCP 集成

nanobot 把 MCP 服务器配置写在 TOML 配置文件中，Agent 启动时自动连接：

```toml
# nanobot.toml
[mcp_servers]

[mcp_servers.filesystem]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "/home/user"]

[mcp_servers.github]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_PERSONAL_ACCESS_TOKEN = "${GITHUB_TOKEN}" }

[mcp_servers.postgres]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-postgres", "postgresql://localhost/mydb"]
```

启动 nanobot 时，它会自动：
1. 并发启动所有配置的 MCP Server 进程
2. 调用每个 Server 的 `list_tools` 获取工具列表
3. 将所有工具合并到 Agent 的工具注册表
4. 在 Agent 结束时，优雅关闭所有 Server 进程

**优势**：一行配置即可使用社区工具；支持环境变量注入（`${GITHUB_TOKEN}`）；Server 并发初始化节省启动时间。

**与 mini_agent 的对比**：mini_agent 的 `--mcp-server` CLI 参数实现了类似功能，但更轻量，适合教学场景。

---

### 2. hermes-agent（NousResearch）：工具集（Toolset）+ MCP 混合架构

hermes-agent 有 40+ 内置工具，同时支持通过 MCP 扩展。其 Toolset 概念把相关工具组织成一个逻辑单元：

```python
# hermes-agent 的工具集概念（简化示意）
class BashToolset(Toolset):
    """命令行工具集：包含 bash 执行、文件操作等"""
    
    def get_tools(self) -> list[Tool]:
        return [BashTool(), ReadFileTool(), WriteFileTool(), ...]
    
    def get_mcp_servers(self) -> list[MCPServerConfig]:
        # 工具集可以声明它依赖的 MCP Server
        return [
            MCPServerConfig(name="git", command="uvx", args=["mcp-server-git"]),
        ]
```

当一个 Toolset 被激活时，它提供的内置工具和它依赖的 MCP Server 工具都会一起注册到 Agent 中。这种"工具集捆绑 MCP Server"的设计让工具的组合更加内聚。

---

### 3. Claude Desktop / Cursor：客户端级 MCP 配置

MCP 不仅用于 Agent 框架，也广泛用于 IDE 和桌面应用。Claude Desktop 和 Cursor 的 MCP 配置格式：

```json
// ~/.claude/claude_desktop_config.json  或  .cursor/mcp.json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/alice"],
      "env": {}
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_your_token"
      }
    },
    "custom-db": {
      "command": "python",
      "args": ["/path/to/my_db_server.py"]
    }
  }
}
```

这说明 MCP 协议足够简单，不同产品都能用同一套配置格式——一个 MCP Server 写好之后，可以同时被 Claude Desktop、Cursor、mini_agent、nanobot 使用。

---

## MCP 服务器的实现语言生态

MCP 的一大优势是**语言无关**：Server 可以用任何语言实现，只要能通过 stdio 或 HTTP 通信即可。

| 语言 | SDK | 代表性 Server |
|------|-----|-------------|
| TypeScript/Node.js | `@modelcontextprotocol/sdk` | 大多数官方 Server（filesystem、github、postgres） |
| Python | `mcp`（官方） | mcp-server-git、mcp-server-sqlite |
| Rust | `rmcp` | 高性能场景 |
| Go | `mcp-go` | 云原生场景 |
| Java/Kotlin | `mcp4j` | 企业场景 |

mini_agent 的 `MCPToolLoader` 使用 Python `mcp` SDK，可以连接任何语言实现的 MCP Server。

---

## 常用社区 MCP Server 推荐

| Server | 安装命令 | 功能 |
|--------|---------|------|
| `@modelcontextprotocol/server-filesystem` | `npx -y @modelcontextprotocol/server-filesystem /path` | 读写本地文件 |
| `@modelcontextprotocol/server-github` | `npx -y @modelcontextprotocol/server-github` | GitHub API（Issues、PR、仓库） |
| `@modelcontextprotocol/server-postgres` | `npx -y @modelcontextprotocol/server-postgres postgresql://...` | PostgreSQL 查询 |
| `@modelcontextprotocol/server-brave-search` | `npx -y @modelcontextprotocol/server-brave-search` | Brave 搜索引擎 |
| `mcp-server-git` | `uvx mcp-server-git --repository .` | Git 操作（log、diff、commit） |
| `mcp-server-sqlite` | `uvx mcp-server-sqlite --db-path ./data.db` | SQLite 数据库查询 |
| `mcp-server-fetch` | `uvx mcp-server-fetch` | 抓取网页内容 |

---

## 设计模式提炼

| 模式 | MCP 中的体现 |
|------|------------|
| **协议优先（Protocol First）** | 先定义通信协议，再实现 Client 和 Server，双方独立演进 |
| **能力发现（Capability Discovery）** | Client 不预设 Server 有哪些工具，通过 `list_tools` 动态获取 |
| **进程边界隔离（Process Isolation）** | Server 崩溃不影响 Agent 主进程，天然的故障隔离 |
| **适配器模式（Adapter）** | MCPToolLoader 将 MCP 工具描述转换为 mini_agent 的 Tool 格式 |
| **惰性连接（Lazy Connection）** | 每次工具调用时建立连接，调用完毕立即关闭，保持无状态 |

---

## mini_agent MCP 集成的局限性与改进方向

本章的 `MCPToolLoader` 采用了最简单的实现：每次工具调用都新建一个进程连接。这在教学场景下足够清晰，但在生产环境中有性能问题：

| 问题 | 生产级改进思路 |
|------|------------|
| 每次调用启动新进程 | 保持长连接，复用进程（参考 nanobot 的会话池） |
| 串行调用 | 多工具并发调用（`asyncio.gather`） |
| stdio only | 同时支持 HTTP/SSE 传输（远程 MCP Server） |
| 无重连机制 | Server 崩溃后自动重启 |
| 无超时控制 | 为每个工具调用设置超时 |

---

## 延伸学习资源

- [MCP 官方网站](https://modelcontextprotocol.io) — 协议规范、快速入门、最佳实践
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) — 官方 Python Client/Server SDK
- [MCP 服务器目录](https://github.com/modelcontextprotocol/servers) — 官方维护的社区 Server 列表
- [awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) — 社区整理的 MCP Server 合集（数百个）
- [nanobot MCP 实现](https://github.com/HKUDS/nanobot) — 参考生产级 MCP 集成方式
