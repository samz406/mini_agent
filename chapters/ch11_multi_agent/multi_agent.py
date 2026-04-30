"""Chapter 11: Multi-Agent — Orchestrator & Subagent Delegation.

Teaches:
- Why single-agent architectures hit limits (context, parallelism, specialisation)
- The Orchestrator-Subagent pattern: one coordinator, many specialists
- How to spawn isolated subagents with their own context and tools
- Parallel execution with threading (no asyncio required for the demo)
- Result aggregation: merging partial answers into a coherent final response
- Error isolation: one failed subagent should not crash the whole system

Inspired by hermes-agent (NousResearch) which can "spawn isolated subagents for
parallel workstreams" and supports writing Python scripts that call tools via
RPC, collapsing multi-step pipelines into zero-context-cost turns.

Run:
    python multi_agent.py
"""

from __future__ import annotations

import concurrent.futures
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Common data structures
# ---------------------------------------------------------------------------

@dataclass
class AgentMessage:
    """A typed message exchanged between agents or with users."""

    role: str           # "user" | "assistant" | "system" | "subagent"
    content: str
    agent_id: str = ""  # which agent produced this message


@dataclass
class TaskSpec:
    """A unit of work handed off to a subagent.

    Attributes:
        task_id:     Unique identifier (auto-generated).
        description: Natural-language description of the work.
        context:     Additional context the subagent needs (e.g. raw data).
        tools:       Names of tools the subagent is allowed to use.
        timeout:     Maximum seconds to wait for a result.
    """

    description: str
    context: str = ""
    tools: list[str] = field(default_factory=list)
    timeout: float = 10.0
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])


@dataclass
class TaskResult:
    """The outcome of a subagent's work."""

    task_id: str
    agent_id: str
    status: str           # "success" | "error" | "timeout"
    result: str = ""
    error: str = ""
    elapsed: float = 0.0


# ---------------------------------------------------------------------------
# Abstract base: every agent (orchestrator or subagent) shares this interface
# ---------------------------------------------------------------------------

class BaseAgent(ABC):
    """Minimal agent interface."""

    def __init__(self, agent_id: str, tools: Optional[dict[str, Any]] = None) -> None:
        self.agent_id = agent_id
        self.tools: dict[str, Any] = tools or {}
        self.history: list[AgentMessage] = []

    @abstractmethod
    def run(self, task: str, context: str = "") -> str:
        """Execute *task* and return the result as a string."""
        ...

    def _log(self, msg: str) -> None:
        print(f"  [{self.agent_id}] {msg}")


# ---------------------------------------------------------------------------
# Built-in tool library (mock implementations — no API key needed)
# ---------------------------------------------------------------------------

def _tool_web_search(query: str) -> str:
    time.sleep(0.05)  # simulate network latency
    return f"(搜索结果) '{query}' 相关: 找到 12 篇高质量文章，首篇标题《{query}的深度解析》"


def _tool_code_execute(code: str) -> str:
    time.sleep(0.03)
    return f"(代码执行) 输出: {code[:30]}... → 执行成功，耗时 0.12s"


def _tool_summarize(text: str) -> str:
    time.sleep(0.02)
    words = text.split()
    short = " ".join(words[:15]) + ("..." if len(words) > 15 else "")
    return f"(摘要) {short}"


def _tool_translate(text: str, target_lang: str = "en") -> str:
    time.sleep(0.04)
    return f"(翻译 → {target_lang}) [{text[:40]}] translated."


def _tool_data_analysis(data: str) -> str:
    time.sleep(0.05)
    return f"(数据分析) 数据集包含约 {len(data)} 字符，发现 3 个趋势和 1 个异常值"


TOOL_REGISTRY: dict[str, Any] = {
    "web_search": _tool_web_search,
    "code_execute": _tool_code_execute,
    "summarize": _tool_summarize,
    "translate": _tool_translate,
    "data_analysis": _tool_data_analysis,
}


# ---------------------------------------------------------------------------
# SubAgent: a specialised, isolated agent for a single task
# ---------------------------------------------------------------------------

class SubAgent(BaseAgent):
    """An isolated agent spawned by the Orchestrator for a specific task.

    Design principles (mirroring hermes-agent):
    - Each SubAgent has its own history — no shared state with other subagents.
    - Only the tools listed in TaskSpec.tools are available (principle of least privilege).
    - The agent runs synchronously in its own thread, so failures are isolated.
    """

    def run(self, task: str, context: str = "") -> str:
        """Execute *task* using only the tools assigned to this subagent."""
        self._log(f"开始任务: {task[:50]}")

        self.history.append(AgentMessage(role="user", content=task, agent_id=self.agent_id))

        # Simulate a simple ReAct-style loop (mock LLM decision)
        result = self._mock_react(task, context)

        self.history.append(AgentMessage(role="assistant", content=result, agent_id=self.agent_id))
        self._log(f"完成任务 → {result[:60]}")
        return result

    def _mock_react(self, task: str, context: str) -> str:
        """Mock a two-step ReAct loop: pick a tool, execute, synthesise answer."""
        task_lower = task.lower()

        # Tool selection heuristic
        selected_tool = None
        if "搜索" in task_lower or "search" in task_lower or "查找" in task_lower:
            selected_tool = "web_search"
        elif "代码" in task_lower or "code" in task_lower or "执行" in task_lower:
            selected_tool = "code_execute"
        elif "分析" in task_lower or "analysis" in task_lower or "数据" in task_lower:
            selected_tool = "data_analysis"
        elif "翻译" in task_lower or "translate" in task_lower:
            selected_tool = "translate"
        elif "总结" in task_lower or "摘要" in task_lower or "summarize" in task_lower:
            selected_tool = "summarize"

        if selected_tool and selected_tool in self.tools:
            self._log(f"使用工具: {selected_tool}")
            fn = self.tools[selected_tool]
            tool_input = context if context else task
            observation = fn(tool_input[:100])
            return f"[{selected_tool}] {observation}"

        # No matching tool — answer directly
        self._log("直接作答（无工具）")
        return f"已分析任务「{task[:40]}」，结论：该任务在当前工具范围内可直接处理，结果正常。"


# ---------------------------------------------------------------------------
# Orchestrator: plans, delegates, and aggregates
# ---------------------------------------------------------------------------

class OrchestratorAgent(BaseAgent):
    """The top-level coordinator that decomposes a complex task into subtasks
    and delegates each to a specialised SubAgent running in parallel.

    Workflow:
      1. Decompose: break the user request into N independent subtasks.
      2. Delegate: spawn one SubAgent per subtask (run in parallel via ThreadPoolExecutor).
      3. Aggregate: collect results and synthesise a unified final answer.

    This pattern is called "Orchestrator-Worker" or "Fan-out/Fan-in".
    hermes-agent implements it with full process isolation and RPC tool calls.
    """

    def __init__(
        self,
        agent_id: str = "orchestrator",
        max_workers: int = 4,
    ) -> None:
        super().__init__(agent_id=agent_id)
        self.max_workers = max_workers

    def run(self, task: str, context: str = "") -> str:
        """Decompose *task*, run subagents in parallel, and return the merged result."""
        print(f"\n{'='*60}")
        print(f"🎯 编排器收到任务: {task}")
        print(f"{'='*60}")

        # Step 1: Decompose
        subtasks = self._decompose(task)
        print(f"\n📋 任务分解为 {len(subtasks)} 个子任务:")
        for i, st in enumerate(subtasks, 1):
            print(f"  {i}. [{st.task_id}] {st.description}")

        # Step 2: Delegate & execute in parallel
        print(f"\n⚡ 并行执行（最大 {self.max_workers} 个 SubAgent）...")
        results = self._fan_out(subtasks)

        # Step 3: Aggregate
        print(f"\n🔗 汇总结果...")
        final = self._aggregate(task, results)

        print(f"\n✅ 最终答案:")
        print(f"{'─'*60}")
        print(final)
        print(f"{'─'*60}")
        return final

    # --- Decompose ---

    def _decompose(self, task: str) -> list[TaskSpec]:
        """Break *task* into independent subtasks.

        In production (hermes-agent) this is done by the LLM.
        Here we use keyword heuristics to keep the demo self-contained.
        """
        task_lower = task.lower()
        subtasks: list[TaskSpec] = []

        # Pattern: "research + code + analysis" type tasks
        if any(w in task_lower for w in ["研究", "调研", "research"]):
            subtasks.append(TaskSpec(
                description=f"搜索关于「{task[:30]}」的最新资料",
                tools=["web_search"],
            ))
        if any(w in task_lower for w in ["代码", "实现", "编写", "implement", "code"]):
            subtasks.append(TaskSpec(
                description=f"编写并执行「{task[:30]}」的示例代码",
                tools=["code_execute"],
            ))
        if any(w in task_lower for w in ["分析", "数据", "analyze", "data"]):
            subtasks.append(TaskSpec(
                description=f"分析「{task[:30]}」相关数据",
                tools=["data_analysis"],
            ))
        if any(w in task_lower for w in ["翻译", "translate", "英文", "中文"]):
            subtasks.append(TaskSpec(
                description=f"将「{task[:30]}」翻译成目标语言",
                tools=["translate"],
            ))
        if any(w in task_lower for w in ["总结", "摘要", "summary", "report"]):
            subtasks.append(TaskSpec(
                description=f"对「{task[:30]}」生成摘要报告",
                tools=["summarize"],
            ))

        # Fallback: single subtask
        if not subtasks:
            subtasks.append(TaskSpec(
                description=task,
                tools=list(TOOL_REGISTRY.keys()),
            ))

        return subtasks

    # --- Fan-out (parallel execution) ---

    def _fan_out(self, subtasks: list[TaskSpec]) -> list[TaskResult]:
        """Spawn one SubAgent per subtask and run them in parallel."""
        results: list[TaskResult] = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            future_to_task = {
                pool.submit(self._run_subtask, st): st
                for st in subtasks
            }

            for future in concurrent.futures.as_completed(future_to_task):
                st = future_to_task[future]
                try:
                    result = future.result(timeout=st.timeout)
                    results.append(result)
                except concurrent.futures.TimeoutError:
                    results.append(TaskResult(
                        task_id=st.task_id,
                        agent_id="unknown",
                        status="timeout",
                        error=f"SubAgent 超时（>{st.timeout}s）",
                    ))
                except Exception as exc:
                    results.append(TaskResult(
                        task_id=st.task_id,
                        agent_id="unknown",
                        status="error",
                        error=str(exc),
                    ))

        # Restore original order (as_completed returns in completion order)
        task_order = {st.task_id: i for i, st in enumerate(subtasks)}
        results.sort(key=lambda r: task_order.get(r.task_id, 999))
        return results

    def _run_subtask(self, spec: TaskSpec) -> TaskResult:
        """Execute a single TaskSpec in a SubAgent. Called in a worker thread."""
        agent_id = f"sub-{spec.task_id}"
        tools = {name: fn for name, fn in TOOL_REGISTRY.items() if name in spec.tools}
        subagent = SubAgent(agent_id=agent_id, tools=tools)

        t0 = time.monotonic()
        try:
            result_str = subagent.run(spec.description, context=spec.context)
            elapsed = time.monotonic() - t0
            return TaskResult(
                task_id=spec.task_id,
                agent_id=agent_id,
                status="success",
                result=result_str,
                elapsed=elapsed,
            )
        except Exception as exc:
            elapsed = time.monotonic() - t0
            return TaskResult(
                task_id=spec.task_id,
                agent_id=agent_id,
                status="error",
                error=str(exc),
                elapsed=elapsed,
            )

    # --- Aggregate ---

    def _aggregate(self, original_task: str, results: list[TaskResult]) -> str:
        """Merge SubAgent results into a final coherent answer."""
        lines = [f"任务「{original_task[:50]}」完成报告", ""]

        success_count = sum(1 for r in results if r.status == "success")
        fail_count = len(results) - success_count
        total_time = max((r.elapsed for r in results), default=0)

        lines.append(f"子任务完成: {success_count}/{len(results)} 成功  "
                     f"({'并行总耗时' if len(results) > 1 else '耗时'}: {total_time:.2f}s)")
        lines.append("")

        for r in results:
            status_icon = "✅" if r.status == "success" else ("⏱" if r.status == "timeout" else "❌")
            lines.append(f"{status_icon} [{r.agent_id}] ({r.elapsed:.2f}s)")
            if r.status == "success":
                lines.append(f"   {r.result}")
            else:
                lines.append(f"   错误: {r.error}")

        if fail_count:
            lines.append(f"\n⚠ {fail_count} 个子任务失败，但其他子任务的结果仍然有效。")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    orchestrator = OrchestratorAgent(max_workers=4)

    print("=" * 60)
    print("Chapter 11: Multi-Agent Demo")
    print("=" * 60)

    # --- Task 1: multi-domain task that benefits from parallel specialisation ---
    orchestrator.run(
        "研究大语言模型 RAG 技术，编写一个 Python 示例代码，并对相关数据进行分析"
    )

    # --- Task 2: translation + summarization in parallel ---
    orchestrator.run(
        "将以下文章翻译为英文，并生成摘要报告：大模型 Agent 是下一代人机交互的核心技术"
    )

    # --- Task 3: single task (no parallelism, shows graceful fallback) ---
    orchestrator.run("回答一个普通问题")

    print("\n" + "=" * 60)
    print("Demo 完成！")
    print("=" * 60)
    print("""
关键收获：
  • 编排器把复杂任务分解为独立子任务（Decompose）
  • 每个 SubAgent 在独立线程中运行，互不影响（Isolate）
  • 所有 SubAgent 并行执行，总耗时 ≈ 最慢子任务（Fan-out）
  • 编排器汇总所有结果为统一回答（Aggregate）
  • 单个 SubAgent 失败不影响整体结果（Fault Isolation）
""")
