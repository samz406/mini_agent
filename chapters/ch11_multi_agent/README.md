# 第十一章：多智能体协作（Multi-Agent）

## 你将学到什么

本章介绍 **多智能体（Multi-Agent）架构**，这是构建处理复杂、并行、大规模任务的 Agent 系统的核心模式。你将：

- 理解单 Agent 架构的局限性及多 Agent 架构解决的问题
- 掌握 **Orchestrator-SubAgent 模式**（编排器-子智能体）
- 学习如何将一个复杂任务分解为独立子任务并并行执行
- 理解错误隔离：一个 SubAgent 的失败不影响整体系统
- 了解 hermes-agent 的子智能体委托机制

> 📖 学完本章后，可以阅读 `extended_reading.md`，了解 hermes-agent 的进程级隔离、OpenAI Swarm、LangGraph 多 Agent 图等进阶设计。

---

## 为什么需要多智能体？

### 单 Agent 架构的三个天花板

**天花板 1：上下文窗口限制**

```
单 Agent 处理长任务：
  [系统提示 + 工具描述 + 100 步历史 + 新任务] → 超出 128K context window！
```

**天花板 2：无法并行**

```
任务：翻译 + 搜索 + 代码执行 + 数据分析（各需 2 秒）

单 Agent：翻译(2s) → 搜索(2s) → 代码(2s) → 分析(2s) = 8 秒
多 Agent：翻译 ⟹ 并行 ⟸ 搜索 ⟹ 并行 ⟸ 代码 ⟹ 并行 ⟸ 分析 = 2 秒
```

**天花板 3：难以专业化**

一个通用 Agent 要同时处理代码、数据、法律、翻译……不如让不同 Agent 各司其职。

---

## 核心模式：Orchestrator-SubAgent

```
用户请求
   │
   ▼
┌─────────────────────────────────────────┐
│           OrchestratorAgent             │
│                                         │
│  ① 分解任务 → [subtask1, subtask2, ...]  │
│                                         │
│  ② 并行委托（Fan-out）                   │
│    ┌──────────┐ ┌──────────┐ ┌────────┐ │
│    │SubAgent 1│ │SubAgent 2│ │SubAgt 3│ │
│    │(搜索专家)│ │(代码专家)│ │(分析师)│ │
│    └────┬─────┘ └─────┬────┘ └───┬────┘ │
│         │             │          │      │
│  ③ 汇总结果（Fan-in）  │          │      │
│    └─────────────┬─────┘──────────┘     │
│               最终回答                  │
└─────────────────────────────────────────┘
```

### 三个关键角色

| 角色 | 职责 | 类比 |
|------|------|------|
| **OrchestratorAgent** | 接收任务、分解、委托、汇总 | 项目经理 |
| **SubAgent** | 独立处理一个专项子任务 | 专业工程师 |
| **TaskSpec** | 子任务的结构化描述（工具权限、超时） | 工作单 |

---

## 核心概念详解

### TaskSpec：结构化工作单

```python
@dataclass
class TaskSpec:
    description: str        # "搜索 RAG 技术的最新论文"
    context: str = ""       # 提供给 SubAgent 的背景材料
    tools: list[str] = ...  # ["web_search"]  ← 最小权限原则
    timeout: float = 10.0   # 超时保护
    task_id: str = ...      # 自动生成的唯一 ID
```

**最小权限原则**：每个 SubAgent 只能使用完成其子任务所需的工具，不能访问其他工具。这提高了安全性，也让每个 SubAgent 的行为更可预测。

### 并行执行（Fan-out / Fan-in）

```python
# Orchestrator 内部实现
with ThreadPoolExecutor(max_workers=4) as pool:
    futures = {
        pool.submit(run_subtask, spec): spec
        for spec in subtasks
    }
    for future in as_completed(futures):
        result = future.result()  # 每个 SubAgent 独立线程
```

**为什么用线程而不是协程（asyncio）？**

| | 线程（threading） | 协程（asyncio） |
|---|---|---|
| 本章选择 | ✅ | |
| 适用场景 | IO 密集型（等待 LLM/网络）| IO 密集型 |
| 实现复杂度 | 低（用 ThreadPoolExecutor） | 中（需要 async/await） |
| GIL 影响 | 有（CPU 密集型受限） | 有（同样） |
| hermes-agent | 使用 asyncio + 进程隔离 | |

### 错误隔离

```python
try:
    result = future.result(timeout=st.timeout)
except TimeoutError:
    result = TaskResult(status="timeout", ...)   # 超时不崩溃
except Exception as exc:
    result = TaskResult(status="error", error=str(exc), ...)  # 错误不传播
```

一个 SubAgent 崩溃或超时，编排器照常收集其他 SubAgent 的结果，最终回答仍然有效。

---

## 任务分解策略

本章使用简单的**关键词匹配**分解任务。在生产环境中，分解本身也由 LLM 完成：

```python
# 生产级分解（LLM 驱动）
decompose_prompt = f"""
将以下用户请求分解为可独立并行执行的子任务列表。
每个子任务需指定：描述、所需工具、上下文。

用户请求：{task}

以 JSON 格式输出：
[
  {{"description": "...", "tools": ["..."], "context": "..."}},
  ...
]
"""
subtasks = llm.complete(decompose_prompt)
```

---

## 结果聚合（Aggregation）

子任务完成后，编排器将结果聚合为统一回答：

```
任务「研究大语言模型 RAG 技术...」完成报告

子任务完成: 3/3 成功  并行总耗时: 0.08s

✅ [sub-a1b2c3d4] (0.05s)
   [web_search] (搜索结果) 'RAG 技术' 相关: 找到 12 篇高质量文章...

✅ [sub-e5f6g7h8] (0.03s)
   [code_execute] (代码执行) 输出: 执行成功，耗时 0.12s

✅ [sub-i9j0k1l2] (0.05s)
   [data_analysis] (数据分析) 数据集包含 45 字符，发现 3 个趋势...
```

---

## 如何运行

```bash
cd chapters/ch11_multi_agent
python multi_agent.py
```

### 运行输出解读

```
🎯 编排器收到任务: 研究大语言模型 RAG 技术，编写 Python 示例代码，并分析相关数据

📋 任务分解为 3 个子任务:
  1. [a1b2] 搜索关于「研究大语言模型 RAG 技术...」的最新资料
  2. [c3d4] 编写并执行「研究大语言模型 RAG 技术...」的示例代码
  3. [e5f6] 分析「研究大语言模型 RAG 技术...」相关数据

⚡ 并行执行（最大 4 个 SubAgent）...
  [sub-a1b2] 开始任务: 搜索...                 ← 三个 SubAgent 同时启动
  [sub-c3d4] 开始任务: 编写并执行...
  [sub-e5f6] 开始任务: 分析...
  [sub-a1b2] 使用工具: web_search
  [sub-c3d4] 使用工具: code_execute
  [sub-e5f6] 使用工具: data_analysis
  [sub-a1b2] 完成任务 → [web_search] ...
  [sub-c3d4] 完成任务 → [code_execute] ...
  [sub-e5f6] 完成任务 → [data_analysis] ...

🔗 汇总结果...
```

---

## 与前几章的对比

| 维度 | ch02 Agent 循环 | ch07 技能系统 | ch10 学习循环 | **ch11 多智能体** |
|------|--------------|------------|------------|------------|
| 执行模式 | 单 Agent 顺序 | 单 Agent + 技能 | 单 Agent + 学习 | **多 Agent 并行** |
| 并行能力 | ❌ | ❌ | ❌ | ✅ |
| 错误隔离 | ❌ | ❌ | ❌ | ✅（SubAgent 独立） |
| 上下文共享 | 全局历史 | 全局历史 | 全局历史 | **每个 SubAgent 独立历史** |
| 适合场景 | 简单对话 | 能力扩展 | 长期学习 | **复杂、并行、大规模** |

---

## 核心设计模式

| 模式 | 体现 |
|------|------|
| **编排器-工作者（Orchestrator-Worker）** | Orchestrator 分解任务，SubAgent 各自执行，结果统一汇总 |
| **Fan-out / Fan-in** | 一个任务扇出到 N 个 SubAgent，N 个结果扇入合并 |
| **最小权限（Least Privilege）** | 每个 SubAgent 只拿到完成其子任务所必需的工具 |
| **错误隔离（Fault Isolation）** | 子任务失败不传播到编排器，系统整体仍可返回部分结果 |
| **超时保护（Timeout Guard）** | 每个子任务有独立超时，避免一个慢 SubAgent 阻塞整个请求 |
