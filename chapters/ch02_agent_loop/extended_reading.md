# 扩展阅读：Agent 循环核心实现 — 主流 Agent 项目对比分析

## 本章回顾

ch02 实现了经典的 ReAct（Reasoning + Acting）循环：Agent 接收用户输入 → LLM 推理 → 文本解析识别 `TOOL_CALL:` 标记 → 执行工具 → 把结果加入历史 → 再次推理，直到 LLM 不再调用工具或达到最大迭代次数。这个同步循环清晰展示了 Agent 的本质：思考→行动→观察的反复迭代。

## 为什么要看其他项目？

mini_agent 的 ReAct 循环是"教科书答案"——展示了 Agent 的骨架。但真实项目需要这个骨架承受并发用户、网络中断、上下文溢出、用户中途打断等各种压力。比较不同项目如何扩展这个骨架，能让你理解每个复杂性是如何被引入的，以及为什么。

## 项目简介

| 项目 | 语言 | 定位 | Agent Loop 特色 |
|------|------|------|----------------|
| mini_agent ch02 | Python | 教学项目 | 同步 ReAct，文本解析工具调用 |
| nanobot (HKUDS) | Python | 轻量生产级 | 异步事件总线，Hook 系统，自动压缩，子代理 |
| hermes-agent (NousResearch) | Python | 自进化代理 | 自改进循环，用户中断，RL 轨迹收集 |
| openclaw | TypeScript | 个人助手 | Gateway 驱动循环，多会话路由 |

## 核心设计对比

### 1. 同步 vs 异步循环：不只是性能问题

**mini_agent** 的循环是完全同步的：

```python
def run(self, user_input: str) -> str:
    messages = self.memory.get_messages()
    for iteration in range(self.max_iterations):
        response = self.llm_client.complete(messages)  # 阻塞等待
        if not tool_calls:
            return response.content
        tool_result = self.execute_tool(response)      # 阻塞等待
        messages.append(...)
    return "达到最大迭代次数"
```

单用户场景完全够用。但两个用户同时发请求时，第二个必须等第一个完全结束——哪怕第一个正在等待一个 3 秒的网络请求。

**nanobot** 的 `AgentLoop` 完全基于 `async/await`：

```python
class AgentLoop:
    async def _iterate(self) -> None:
        await self.hook.before_iteration(self.context)
        
        # 流式输出同时发布到事件总线
        async for chunk in self.provider.stream(self.context.messages):
            await self.bus.publish(OutboundChunk(chunk))
        
        if self.context.has_tool_calls():
            await self.hook.before_execute_tools(self.context)
            # 多个工具并发执行！
            results = await asyncio.gather(*[
                self._execute_tool(tc) for tc in self.context.tool_calls
            ])
```

注意 `asyncio.gather(*)` 这一行：多个工具可以**并发执行**。Agent 同时读取 3 个文件，发出 3 个并发 I/O 请求，而不是串行等待，整体速度大幅提升。

**异步的代价**：代码更难调试（堆栈跟踪更复杂），错误处理更繁琐（需要处理 `asyncio.CancelledError`），且所有调用链都必须是异步的——一个同步函数阻塞事件循环会卡死整个系统。这正是为什么教学项目选择同步：在理解 Agent 逻辑之前，不应该被异步复杂性分散注意力。

---

### 2. 工具调用解析：文本解析 vs 原生 Function Calling API

这是 mini_agent 和生产级项目之间最显著的架构差异。

**mini_agent** 使用文本解析：

```python
# LLM 被提示输出固定格式：
# TOOL_CALL: {"name": "calculator", "args": {"expression": "2+2"}}

if "TOOL_CALL:" in response:
    tool_name = parse_tool_name(response)
    args = parse_args(response)  # 如果 LLM 输出了错误的 JSON，这里会崩溃
    result = self.tool_registry.execute(tool_name, args)
```

**优点**：适用于任何 LLM（包括不支持 Function Calling 的模型），逻辑透明，便于教学。
**缺点**：LLM 有时输出格式不正确（多余空格、JSON 语法错误），解析失败导致工具无法执行，Agent 陷入困惑。

**nanobot** 使用 OpenAI 原生 Function Calling API：

```python
response = await openai.chat.completions.create(
    messages=messages,
    tools=[tool.to_openai_schema() for tool in self.tools],
    tool_choice="auto"
)

# API 返回结构化工具调用，无需文本解析
for tool_call in response.choices[0].message.tool_calls:
    tool_name = tool_call.function.name          # 保证是已注册名称
    args = json.loads(tool_call.function.arguments)  # 保证是合法 JSON
    result = await self.execute_tool(tool_name, args)
```

原生 Function Calling 的关键保证：工具名称一定是注册过的名称（不会拼写错误），参数一定是合法 JSON（模型经过专门训练），可以同时输出多个工具调用（并发执行）。

**权衡的核心**：原生 Function Calling 把工具调用的可靠性从"LLM 格式遵从能力"提升到"API 层结构保证"。代价是：依赖服务商的具体 API，不支持 Function Calling 的开源模型必须回退到文本解析。

---

### 3. 循环终止条件：简单计数 vs 复杂状态机

**mini_agent** 的终止逻辑：

```python
if not tool_calls:
    return response.content  # LLM 说完了
if iteration >= max_iterations:
    return "超出最大迭代次数"  # 安全截断
```

**nanobot** 的终止逻辑形成了一个状态机：

```
空闲(IDLE) → 运行(RUNNING) → 等待工具(WAITING_FOR_TOOL) → 运行(RUNNING) → ... → 完成(DONE)
                                                                               ↓
                                                                         压缩(COMPACTING)
                                                                               ↓
                                                                         运行(RUNNING)
```

关键状态是 `COMPACTING`：当检测到上下文接近 token 限制时，不直接终止，而是先压缩上下文，再继续运行。这让长任务（需要 100+ 轮迭代）成为可能。

**hermes-agent** 增加了两个特殊的终止/继续条件：

1. **用户中断（Interrupt-and-redirect）**：用户在 Agent 执行中途发送新消息，Agent 检测到中断，决定是完成当前步骤后再处理，还是立即转向新任务。

2. **自我学习触发**：复杂任务完成后，Agent 不直接停止，而是评估"这次任务有值得学习的模式吗？"如果有，触发"技能创建"子流程。

这展示了一个重要思想：**循环终止是策略，不是条件**。不同 Agent 有不同的"任务完成"定义。

---

### 4. Hook（钩子）模式的工程价值

nanobot 在 Agent 循环中加入了 Hook 系统：

```python
class AgentHook(ABC):
    async def before_iteration(self, context: AgentContext) -> None:
        pass   # 默认无操作
    
    async def before_execute_tools(self, context: AgentContext) -> None:
        pass
    
    async def after_iteration(self, context: AgentContext) -> None:
        pass

# 不修改核心循环，只需添加 Hook：
class AutoCompactHook(AgentHook):
    async def before_iteration(self, context):
        if context.token_count > context.token_limit * 0.8:
            await self.compact(context)  # 自动压缩

class LoggingHook(AgentHook):
    async def after_iteration(self, context):
        logger.info(f"迭代完成，token 数: {context.token_count}")
```

这个设计遵循"开放/封闭原则"：核心循环对修改封闭（不需要改 `AgentLoop` 本身），对扩展开放（增加新 Hook 就能增加新行为）。

对比 mini_agent：如果要在每次迭代后记录日志，你必须修改 `run()` 函数本身——项目规模增大时，核心代码会越来越复杂。Hook 系统把"横切关注点"（日志、监控、压缩）从核心逻辑分离出来。

---

### 5. 上下文压缩的触发时机

当 Agent 在长任务中积累大量工具调用历史，消息列表的 token 数可能超过模型上下文窗口限制。

**方案 A（mini_agent 隐含策略）**：让 API 调用失败，返回错误。教学中可接受，生产中不可接受。

**方案 B（nanobot AutoCompact）**：在 `before_iteration` Hook 中检查 token 数，超过阈值（如 80% 容量）时**在当前迭代开始前**自动压缩。选择"迭代开始前"的原因：此时上下文相对完整，LLM 可以在新一轮迭代中直接使用压缩后的上下文，不会出现"说到一半被截断"的问题。

**方案 C（hermes-agent 和 openclaw）**：提供 `/compress` 或 `/compact` 命令，让用户手动触发。更透明，但需要用户了解 token 限制概念。

---

### 6. 会话持久化：重启后的 Agent 还认识你吗？

**mini_agent** 的会话在进程结束后消失。

**nanobot** 把会话状态存储在工作目录的 JSON 文件中：

```
workspace/
  sessions/
    session_abc123.json   # 消息历史
    session_abc123.mem    # 记忆文件
```

Agent 重启后收到来自 `session_abc123` 的新消息时，从文件恢复历史，用户感觉对话从未中断。

**设计洞察**：会话持久化看似简单（消息写到文件），但引入了新问题：历史中引用的文件路径可能已不存在？如何控制历史增长？这些问题在 mini_agent 中暂时回避，但构建真实产品时无法绕开。

## 设计模式提炼

| 设计维度 | mini_agent | nanobot | hermes-agent | openclaw |
|---------|-----------|---------|-------------|---------|
| 并发模型 | 同步单用户 | 异步多用户 | 异步多用户 | 异步多会话 |
| 工具调用解析 | 文本解析 | 原生 Function Calling | 原生 Function Calling | 原生 Function Calling |
| 工具并发执行 | 串行 | asyncio.gather 并发 | 并发 | 并发 |
| 终止条件 | 计数 + 关键词 | 状态机 + 自动压缩 | 状态机 + 用户中断 | 状态机 + 多会话路由 |
| 扩展机制 | 无 | Hook 系统 | 插件 + 学习循环 | 事件驱动 |
| 会话持久化 | 无 | JSON 文件 | SQLite | 文件 |

## 对初学者的启示

1. **文本解析是学习的最好起点，不是终点**：`TOOL_CALL:` 文本标记让你清楚地看到工具调用的本质。理解概念后，应迁移到原生 Function Calling API，更可靠、功能更强。

2. **同步代码先行**：先用同步代码搞清楚 Agent 逻辑，再考虑异步化。很多人在理解 Agent 循环之前就陷入 `async/await` 细节中，得不偿失。

3. **Hook 模式是软件工程的精华**：把"做什么"和"什么时候做"分离。这个思想让代码在增长时仍然保持整洁。

4. **循环终止策略比你想象的更重要**：一个无法优雅终止的 Agent 在生产中是灾难性的。提前考虑所有可能的终止路径：正常完成、超时、用户中断、token 溢出、工具失败。

5. **先做单用户，再想多用户**：异步和会话隔离是多用户的必要条件，但在单用户原型阶段完全不必要。

## 延伸学习资源

- [nanobot/agent/loop.py](https://github.com/HKUDS/nanobot/blob/main/nanobot/agent/loop.py) — 完整的异步 AgentLoop 实现
- [ReAct 原始论文](https://arxiv.org/abs/2210.03629) — Yao et al., 2022，ReAct 框架的学术来源
- [OpenAI Function Calling 指南](https://platform.openai.com/docs/guides/function-calling) — 原生工具调用 API 完整文档
- [Python asyncio 教程](https://docs.python.org/3/library/asyncio.html) — 理解异步编程的官方文档
