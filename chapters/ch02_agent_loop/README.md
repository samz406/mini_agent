# 第二章：Agent 循环（ReAct 模式）

## 你将学到什么

本章实现了所有 Agent 的核心：**推理循环**。我们实现的是 **ReAct**（Reasoning + Acting，推理+行动）模式——这是大多数生产级 Agent 的骨架。

> 📖 学完本章后，可以阅读 `extended_reading.md`，了解 nanobot（异步+Hook系统）、hermes-agent（自我改进循环）等项目是如何设计 Agent Loop 的。

## ReAct 模式

```
用户输入
    │
    ▼
┌─────────────────────────────────────┐
│  推理（REASON）：调用 LLM，获取回复  │
│                                     │
│  解析（PARSE）：提取工具调用指令     │
│                                     │
│  行动（ACT）：执行工具              │
│                                     │
│  观察（OBSERVE）：把结果加入历史     │
│                                     │
│  → 重复，直到没有工具调用           │
│    或达到最大迭代次数               │
└─────────────────────────────────────┘
    │
    ▼
最终回复
```

**通俗理解**：想象你让 AI 帮你查天气、订餐厅。AI 不是一步回答，而是先思考"我需要查天气"，然后调用查天气的工具，看到结果后再思考"现在我需要找附近的餐厅"……这个"思考→行动→观察→再思考"的循环，就是 ReAct 模式。

## 工具调用格式

本章使用文本解析方式识别工具调用。LLM 被要求在回复中用固定格式标记工具调用：

```
TOOL_CALL: {"name": "calculator", "args": {"expression": "2 + 2"}}
```

Agent 会扫描 LLM 的回复文本，找到所有 `TOOL_CALL:` 标记，依次执行对应的工具，然后把执行结果作为新消息追加到对话历史中，再次调用 LLM。

> **注意**：这种文本解析方式适合教学，让你清楚地看到工具调用的本质。生产环境中通常使用 OpenAI 原生的 Function Calling API（见扩展阅读）。

## 循环停止条件

满足以下**任意一个**条件时，循环停止：

1. **LLM 回复中不含工具调用** → 说明 AI 认为已经有了最终答案
2. **达到 `max_iterations` 上限** → 安全保护，防止无限循环

## 代码结构

```python
class AgentLoop:
    def run(self, user_input: str) -> str:
        # 1. 把用户输入加入对话历史
        self.history.append(Message("user", user_input))
        
        for iteration in range(self.max_iterations):
            # 2. 推理：调用 LLM
            response = self.llm.complete(self.history)
            self.history.append(Message("assistant", response.content))
            
            # 3. 解析：找出所有工具调用
            tool_calls = self.parse_tool_calls(response.content)
            
            if not tool_calls:
                return response.content  # 没有工具调用，返回最终答案
            
            # 4. 行动 + 观察：执行工具，把结果追加历史
            for tc in tool_calls:
                result = self._execute_tool(tc)
                observation = f"TOOL_RESULT: {tc.name} returned: {result}"
                self.history.append(Message("user", observation))
        
        return "已达到最大迭代次数。"  # 安全截断
```

## 对话历史的作用

每一轮迭代，整个对话历史都会发送给 LLM。这样 LLM 就能"记住"之前做过什么：

```
[用户]: 2+2 是多少，现在几点？
[助手]: 我需要计算 2+2。
        TOOL_CALL: {"name": "calculator", "args": {"expression": "2+2"}}
[用户]: TOOL_RESULT: calculator returned: 4
[助手]: 计算结果是 4，现在查一下时间。
        TOOL_CALL: {"name": "get_time", "args": {}}
[用户]: TOOL_RESULT: get_time returned: 14:30:00
[助手]: 2+2=4，现在是下午 2:30。
```

## 如何运行

```bash
cd chapters/ch02_agent_loop
python agent_loop.py
```

**无需 API Key！** 本章使用 `MockLLMClient`（模拟 LLM），会按脚本返回预设回复，让你能看到完整的 ReAct 循环，而不需要真实的 AI 服务。

你将看到：
- 每一轮迭代的 LLM 调用
- 工具调用的解析和执行
- 观察结果如何追加到历史
- 最终答案的返回
