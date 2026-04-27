# 扩展阅读：工具系统设计 — 主流 Agent 项目实现对比

## 本章回顾

ch03 用装饰器工厂（`@tool()`）定义工具，用 `ToolRegistry` 注册和检索工具，用 `ToolParameter` 定义参数，并自动生成 OpenAI Function Calling 格式的 JSON Schema。核心思想：**工具是携带元数据的函数，而不仅仅是函数本身**。

## 为什么要看其他项目？

工具系统是 Agent 能力边界的决定者。mini_agent 展示了工具系统的骨架；生产级项目在此基础上解决了安全隔离（工具可能执行危险操作）、工具扩展（社区贡献）、工具并发（多工具同时执行）、以及工具协议标准化（MCP）等复杂问题。

## 项目简介

| 项目 | 语言 | 工具系统特色 |
|------|------|------------|
| mini_agent ch03 | Python | 装饰器工厂 + 注册表 + JSON Schema |
| nanobot (HKUDS) | Python | 类继承体系，工具类，MCP 协议，沙箱隔离 |
| hermes-agent (NousResearch) | Python | 40+ 内置工具，Toolset 分组，6 种终端后端 |
| openclaw | TypeScript | YAML 技能文件中声明工具，ClawHub 社区工具 |

## 核心设计对比

### 1. 函数装饰器 vs 类继承：两种工具定义方式

**mini_agent** 使用装饰器将普通函数包装为工具：

```python
@tool(
    name="calculator",
    description="安全计算数学表达式",
    parameters=[ToolParameter(name="expression", type="string", description="数学表达式")]
)
def calculator(expression: str) -> str:
    return str(_safe_eval(expression))
```

**优点**：代码最少，直觉上"函数就是工具"，非常适合定义简单工具。
**缺点**：工具本身无法携带状态（如数据库连接、配置项），复杂工具的测试也更难独立进行。

**nanobot** 使用类继承方式：

```python
class ExecTool(Tool):
    """Shell 命令执行工具"""
    
    name = "exec"
    description = "在工作目录中执行 shell 命令"
    
    def __init__(self, workspace: Path, sandbox_config: SandboxConfig):
        self.workspace = workspace
        self.sandbox = sandbox_config  # 工具持有状态
    
    async def __call__(self, command: str, timeout: int = 30) -> ToolResult:
        if self.sandbox.enabled:
            return await self._run_sandboxed(command, timeout)
        return await self._run_direct(command, timeout)
    
    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {...}
            }
        }
```

**优点**：工具可以持有状态（工作目录、沙箱配置、数据库连接）；可以在 `__init__` 中做初始化验证；测试时可以独立实例化；复杂工具（如 WebSearch 需要管理 HTTP 会话）更自然。

**工程选择**：简单无状态工具用装饰器；复杂有状态工具用类。nanobot 的 `ExecTool`、`ReadFileTool`、`WebSearchTool` 都需要状态，因此选择类继承。

---

### 2. MCP 协议：工具生态的标准化

**MCP（Model Context Protocol）** 是 Anthropic 提出的开放标准，定义了 AI 应用与外部工具/数据源之间的通信协议。可以把它理解为"工具的 USB 接口"——工具按标准实现，Agent 按标准调用，双方互不关心对方的实现细节。

**nanobot** 原生支持 MCP：

```python
# Agent 可以连接任意 MCP 服务器，自动发现并使用其工具
mcp_servers = {
    "filesystem": {"command": "npx", "args": ["@modelcontextprotocol/server-filesystem", "/home/user"]},
    "github": {"command": "npx", "args": ["@modelcontextprotocol/server-github"]},
    "postgres": {"command": "npx", "args": ["@modelcontextprotocol/server-postgres", "postgresql://..."]},
}

agent = AgentLoop(mcp_servers=mcp_servers)
# Agent 现在自动拥有了文件系统工具、GitHub 工具和 PostgreSQL 工具
```

这意味着任何遵循 MCP 协议的工具都可以直接接入 nanobot，无需修改 Agent 代码。MCP 生态已经有数百个社区贡献的服务器（GitHub、Slack、PostgreSQL、Figma 等）。

**对比 mini_agent**：每个新工具都需要修改 Agent 源代码才能使用。MCP 把工具的"安装"变成了配置而非编码。

---

### 3. 工具安全隔离：沙箱化

**mini_agent** 的工具在主进程中直接执行，对文件系统有完全访问权限（通过 `read_file`/`write_file`）。对于单用户本地工具，这是合理的。

**nanobot** 支持工具沙箱化，可以把工具执行隔离在 Docker 容器中：

```python
# 配置文件中设置
sandbox:
  mode: "non-main"  # 非主会话的工具在沙箱中运行
  backend: "docker"
  
# 沙箱中默认允许：bash, read, write, edit
# 沙箱中默认禁止：browser, canvas, cron（与外部系统交互的工具）
```

当 Agent 服务多个用户时（比如通过 Telegram），一个用户的工具调用不应该影响其他用户的文件系统。Docker 沙箱确保了这种隔离。

**hermes-agent** 提供了 6 种终端后端（terminal backends）用于工具执行：
- `local`：直接在本机执行
- `docker`：Docker 容器隔离
- `ssh`：在远程服务器执行
- `daytona`：云端无服务器环境（闲置时休眠，请求时唤醒）
- `singularity`：HPC 集群环境
- `modal`：函数即服务（FaaS）

这体现了一个重要设计：工具执行环境和工具定义分离，同一个工具可以在不同环境中运行。

---

### 4. 工具的异步执行与并发

**mini_agent** 串行执行工具：

```python
for tc in tool_calls:
    result = self._execute_tool(tc)  # 一个执行完才开始下一个
    history.append(f"TOOL_RESULT: {result}")
```

如果一次请求触发了 3 个工具调用（如：读取 3 个文件），需要顺序执行，总时间 = 工具1时间 + 工具2时间 + 工具3时间。

**nanobot** 并发执行工具：

```python
# asyncio.gather 让多个工具同时运行
results = await asyncio.gather(*[
    self._execute_tool(tc) for tc in tool_calls
])
# 总时间 ≈ max(工具1时间, 工具2时间, 工具3时间)
```

对于 I/O 密集型工具（网络请求、文件读写），并发执行可以大幅减少延迟。一个需要读取 5 个文件的请求，从 5×0.1s=0.5s 缩短到 ~0.1s。

---

### 5. 工具发现与注册策略

**mini_agent** 使用显式注册（装饰器在定义时注册，导入模块时触发）：

```python
# 只要导入这个模块，工具就会自动注册
import chapters.ch03_tools.example_tools
```

**hermes-agent** 支持动态工具发现：工具可以在 Agent 运行期间动态增减。当一个 Skill 被安装时，它携带的工具立即可用，无需重启 Agent。

**openclaw** 的工具定义在 YAML 技能文件中，由 ClawHub 社区维护：

```yaml
# ~/.openclaw/skills/weather/skill.yaml
name: weather
tools:
  - name: get_weather
    description: 获取指定城市的天气信息
    parameters:
      - name: city
        type: string
        required: true
```

这种配置驱动的方式让非程序员也能创建工具，大大降低了工具生态的门槛。

## 设计模式提炼

| 设计维度 | mini_agent | nanobot | hermes-agent | openclaw |
|---------|-----------|---------|-------------|---------|
| 工具定义方式 | 函数装饰器 | 类继承 | 类继承 + Toolset | YAML 配置 |
| 工具协议 | 内部格式 | MCP 原生支持 | MCP 部分支持 | 内部格式 |
| 执行隔离 | 无（主进程直接运行） | Docker 沙箱 | 6 种终端后端 | 无/可选 |
| 工具并发 | 串行 | asyncio.gather | 并发 | 并发 |
| 工具发现 | 导入触发 | 配置文件 + MCP | 动态注册 | YAML 扫描 |
| 社区生态 | 无 | MCP 服务器生态 | agentskills.io | ClawHub |

## 对初学者的启示

1. **装饰器模式是入门，类继承是深入**：先用装饰器理解"工具是什么"，当需要状态管理时自然会转向类。

2. **MCP 是工具生态的未来**：如果你要构建真实的 Agent，优先支持 MCP 协议，而不是只支持自己的格式。这让你能直接使用社区的数百个工具。

3. **安全不是事后想法**：工具有执行代码、访问文件、发出网络请求的能力。在构建多用户或面向互联网的 Agent 时，沙箱化是必须考虑的，不是可选的。

4. **工具并发是免费的性能提升**：对于 I/O 密集型工具，使用 `asyncio.gather` 并发执行几乎不需要额外工作，但能大幅减少延迟。

## 延伸学习资源

- [MCP 官方文档](https://modelcontextprotocol.io) — 了解 Model Context Protocol 标准
- [MCP 服务器列表](https://github.com/modelcontextprotocol/servers) — 数百个现成的 MCP 工具
- [nanobot/agent/tools/](https://github.com/HKUDS/nanobot/tree/main/nanobot/agent/tools) — 查看生产级工具类实现
- [hermes-agent 工具文档](https://hermes-agent.nousresearch.com/docs/user-guide/features/tools) — 40+ 内置工具说明
