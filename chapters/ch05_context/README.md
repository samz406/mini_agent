# 第五章：上下文窗口管理

## 你将学到什么

每个 LLM 都有有限的上下文窗口（Context Window）。当对话超过这个限制时，API 要么报错，要么悄悄截断消息。本章构建主动管理上下文的工具，防患于未然。

> 📖 学完本章后，可以阅读 `extended_reading.md`，了解 nanobot 的 AutoCompact 自动压缩、hermes-agent 的 /compress 命令、不同 Token 计数器的精度权衡等设计。

## 为什么需要上下文管理？

- GPT-4o 约有 128k token 上下文；较小/便宜的模型只有 4k–8k
- 每个 token 都要花钱——浪费的上下文 = 更高的账单
- 不做限制，长对话最终会崩溃（API 报错或静默截断）

**什么是 Token？**
Token 是 LLM 处理文本的基本单位。简单理解：1 个英文单词约 1 个 token，1 个中文字约 1.5–2 个 token。`"Hello world"` 大约是 2 个 token，`"你好世界"` 大约是 4–6 个 token。

## Token 计数

`TokenCounter` 封装了 tiktoken（OpenAI 官方分词库）：

```python
counter = TokenCounter()
counter.count("Hello, world!")        # → 约 4 个 token
counter.count("你好，世界！")          # → 约 8 个 token
counter.count_messages([
    {"role": "user", "content": "Hi"}
])  # → 约 8 个 token（含角色标记）
```

如果 tiktoken 未安装，会回退到 `len(text) // 4` 近似计算（英文平均每个单词约 4 个字符约 1 个 token）。

## 裁剪策略

### 滑动窗口策略（Sliding Window）

保留**系统消息**（定义 Agent 的人格和能力）以及尽可能多的**最近消息**，直到超出 token 预算。最旧的消息最先被丢弃。

```
[系统] [旧消息1] [旧消息2] [最近3] [最近4] [最近5]
                  ↑ 为了节省 token 被丢弃
```

**优点**：简单可靠，不需要额外 LLM 调用。
**缺点**：丢失早期对话细节，可能导致 Agent 忘记早期确立的重要信息。

### 摘要策略（Summarization Strategy，进阶）

不直接丢弃旧消息，而是用 LLM 把它们压缩成一段摘要，再替换原始消息：

```
[系统] [摘要：旧消息1+2的内容] [最近3] [最近4] [最近5]
```

**优点**：保留了早期对话的信息本质。
**缺点**：需要额外调用一次 LLM（增加成本和延迟）；如果没有提供 `summarize_fn`，本章实现会回退到滑动窗口策略。

## 核心代码结构

```python
class ContextWindowManager:
    def __init__(self, max_tokens: int = 4000):
        self.max_tokens = max_tokens
        self.counter = TokenCounter()
    
    def trim(self, messages: list[dict], strategy="sliding_window") -> list[dict]:
        total = self.counter.count_messages(messages)
        
        if total <= self.max_tokens:
            return messages  # 不需要裁剪
        
        if strategy == "sliding_window":
            return self._sliding_window(messages)
        elif strategy == "summarize":
            return self._summarize(messages)
```

## 如何运行

```bash
cd chapters/ch05_context
python context_manager.py
```

你将看到：
1. 各种文本的 token 计数
2. 一组消息是否超出预算的判断
3. 滑动窗口策略的裁剪效果（21 条消息 → 6 条）
4. 摘要策略（本章为 stub，回退到滑动窗口）
