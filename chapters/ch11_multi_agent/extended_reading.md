# 扩展阅读：多智能体架构在主流项目中的实现

## 本章回顾

ch11 展示了 Orchestrator-SubAgent 模式：编排器将复杂任务分解为独立子任务，每个 SubAgent 在隔离的线程中并行执行，结果汇总为统一回答。核心价值：**并行提速、专业分工、故障隔离**。

---

## hermes-agent 的子智能体实现

hermes-agent（NousResearch）的多智能体能力是其最具特色的工程创新之一。

### 进程级隔离（Process Isolation）

本章使用线程实现 SubAgent 隔离。hermes-agent 更进一步，使用**独立进程**：

```python
# hermes-agent 子智能体架构（简化示意）
class SubAgent:
    def __init__(self, backend: TerminalBackend):
        # 每个 SubAgent 在独立的 Docker 容器或 SSH 会话中运行
        self.backend = backend  # local / docker / ssh / daytona / modal
        self.tool_server = RPCToolServer()  # 工具通过 RPC 调用
    
    async def run(self, task: str) -> str:
        # SubAgent 在隔离进程中运行，通过 RPC 调用主进程的工具
        script = self._generate_python_script(task)
        result = await self.backend.execute(script)
        return result
```

进程隔离的好处：
- **内存隔离**：SubAgent 崩溃不影响主进程
- **安全边界**：危险代码在容器中执行
- **资源控制**：可为每个 SubAgent 设置 CPU/内存限制

### RPC 工具调用

hermes-agent 的 SubAgent 不直接调用工具，而是通过 RPC（远程过程调用）：

```python
# 在 SubAgent 的 Python 脚本中（运行在隔离进程）
from hermes.rpc import tools  # RPC 客户端

# 调用主进程的工具，结果通过 socket 传回
results = tools.web_search("LLM RAG 最新论文")
code_output = tools.bash("python my_analysis.py")
```

这使得 SubAgent 即使在远程服务器（SSH）或容器（Docker）中运行，也能访问主 Agent 的全部工具。

### 六种终端后端（Terminal Backend）

hermes-agent 的 SubAgent 可以运行在六种不同环境：

| 后端 | 说明 | 适用场景 |
|------|------|------|
| `local` | 本机 subprocess | 开发调试 |
| `docker` | Docker 容器 | 安全隔离 |
| `ssh` | 远程 SSH | 云服务器 |
| `daytona` | Daytona 无服务器 | 按需计算，空闲时休眠 |
| `modal` | Modal 无服务器 | 高并发任务，GPU 支持 |
| `singularity` | HPC 容器 | 科研集群 |

```python
# hermes-agent 切换后端（简化示意）
subagent = SubAgent(backend=ModalBackend(gpu="A100"))
result = await subagent.run("训练一个小型语言模型")
```

---

## OpenAI Swarm：最简多智能体框架

[OpenAI Swarm](https://github.com/openai/swarm) 是 OpenAI 发布的轻量多智能体框架，核心概念只有两个：

### Agent（代理）

```python
from swarm import Agent

# 每个 Agent 有自己的身份和工具
researcher = Agent(
    name="研究员",
    instructions="你是一位学术研究专家，专注于检索和总结最新论文。",
    functions=[search_papers, summarize_paper],
)

coder = Agent(
    name="程序员",
    instructions="你是一位 Python 专家，负责实现算法和分析数据。",
    functions=[write_code, run_code],
)
```

### Handoff（移交）

```python
# 当研究员完成后，将工作移交给程序员
def transfer_to_coder():
    """当需要代码实现时，移交给程序员。"""
    return coder

researcher = Agent(
    name="研究员",
    functions=[search_papers, transfer_to_coder],  # 可以移交
)
```

**与本章 Orchestrator-SubAgent 的对比**：

| 维度 | 本章（Orchestrator-Worker） | Swarm（Handoff） |
|------|--------------------------|----------------|
| 并行性 | ✅ SubAgent 并行运行 | ❌ 顺序移交 |
| 控制流 | 中心化（编排器决策） | 去中心化（Agent 自决策） |
| 适合场景 | 已知可并行的任务 | 未知流程，Agent 自主决策 |
| 复杂度 | 中 | 低（入门友好） |

---

## LangGraph：状态机驱动的多智能体

[LangGraph](https://github.com/langchain-ai/langgraph) 将多智能体工作流建模为**有向图**：

```python
from langgraph.graph import StateGraph

# 定义多智能体工作流图
graph = StateGraph(AgentState)

graph.add_node("researcher", researcher_agent)
graph.add_node("coder", coder_agent)
graph.add_node("reviewer", reviewer_agent)

# 定义执行顺序和条件跳转
graph.add_edge("researcher", "coder")
graph.add_conditional_edges(
    "coder",
    should_review,  # 条件函数：是否需要代码审查
    {"yes": "reviewer", "no": END},
)

workflow = graph.compile()
result = workflow.invoke({"task": "构建 RAG 系统"})
```

**适用场景**：复杂的、有条件分支的工作流（如"如果代码有 bug，跳回调试循环"）。

---

## 多智能体模式分类

### 模式一：Orchestrator-Worker（本章）

```
Orchestrator → [SubAgent A] → 结果
             → [SubAgent B] → 结果  → 汇总
             → [SubAgent C] → 结果
```

**特点**：中心化调度、并行、Fan-out/in。

### 模式二：Pipeline（流水线）

```
Agent A → 结果 → Agent B → 结果 → Agent C → 最终结果
```

**特点**：顺序处理，上一步的输出是下一步的输入。适合数据清洗 → 分析 → 报告生成等线性流程。

### 模式三：Reflection（反思）

```
Agent 草稿 → Critic Agent 评价 → Agent 修改 → Critic 评价 → ... → 最终版本
```

**特点**：一个 Agent 生成，另一个 Agent 批评，迭代改进质量。hermes-agent 的技能改进循环类似这种模式。

### 模式四：Hierarchical（层级）

```
高层 Agent（战略决策）
      │
 ┌────┴────┐
中层 Agent A  中层 Agent B
      │             │
子 Agent 1  子 Agent 2  子 Agent 3
```

**特点**：多层级的委托，适合超大规模任务（如"设计并实现整个电商系统"）。

---

## 多智能体的挑战

| 挑战 | 描述 | 常见解决方案 |
|------|------|------|
| **结果一致性** | 多个 SubAgent 的输出可能相互矛盾 | 增加 Reviewer Agent 检查一致性 |
| **重复工作** | 多个 SubAgent 做了相同的事 | 任务分解前去重，共享工具调用缓存 |
| **上下文传递** | 子任务需要的背景信息如何传递 | TaskSpec.context 字段显式传递 |
| **成本控制** | N 个 SubAgent 意味着 N 倍的 LLM 调用费用 | 只对真正可并行的任务使用多 Agent |
| **调试难度** | 并行执行导致日志交叉，难以追踪 | 每个 SubAgent 有唯一 ID，结构化日志 |

---

## 延伸学习资源

- [hermes-agent 多智能体文档](https://hermes-agent.nousresearch.com/docs) — SubAgent 和并行工作流
- [OpenAI Swarm](https://github.com/openai/swarm) — 轻量级多智能体框架（入门友好）
- [LangGraph](https://github.com/langchain-ai/langgraph) — 状态机驱动的多智能体工作流
- [AutoGen](https://github.com/microsoft/autogen) — Microsoft 的多智能体对话框架
- [CrewAI](https://github.com/crewAIInc/crewAI) — 角色化的多智能体协作框架
- [Multi-Agent Systems论文](https://arxiv.org/abs/2402.01680) — "More Agents Is All You Need"
