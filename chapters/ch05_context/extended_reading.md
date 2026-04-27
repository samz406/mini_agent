# 扩展阅读：上下文窗口管理 — 主流 Agent 项目实现对比

## 本章回顾

ch05 构建了 `TokenCounter`（封装 tiktoken，带降级回退）、`SlidingWindowStrategy`（保留系统消息 + 最近消息）和 `SummarizationStrategy`（LLM 摘要，stub 实现）。核心思想：**上下文是有限资源，必须主动管理，而不是被动等崩溃**。

## 为什么要看其他项目？

上下文管理是 Agent 最容易被低估的工程挑战。mini_agent 给你了工具，但没有回答更难的问题：什么时候压缩？压缩多少？压缩时如何不打断正在进行的推理？如何在流式输出中安全地截断？比较不同项目的解决方案，能让你理解这些问题的真实难度。

## 项目简介

| 项目 | 语言 | 上下文管理特色 |
|------|------|--------------|
| mini_agent ch05 | Python | TokenCounter + 滑动窗口 + 摘要 stub |
| nanobot (HKUDS) | Python | ContextBuilder 分层组装，AutoCompact 自动压缩，Context Block 限制 |
| hermes-agent (NousResearch) | Python | /compress 手动压缩，/usage 用量查看，对话洞察分析 |
| openclaw | TypeScript | /compact 手动压缩，Context 文件永久注入，thinking 级别控制 |

## 核心设计对比

### 1. ContextBuilder：上下文组装的顺序与优先级

**mini_agent** 的上下文就是直接传入的消息列表，没有特别的组装逻辑。

**nanobot** 的 `ContextBuilder` 在每轮迭代中按**固定优先级顺序**组装上下文：

```python
class ContextBuilder:
    """按优先级组装 Agent 上下文"""
    
    def build(self) -> list[dict]:
        context = []
        
        # 第1优先级：系统提示词（绝不裁剪）
        context.append({"role": "system", "content": self.system_prompt})
        
        # 第2优先级：记忆注入（最重要的 N 条记忆）
        for memory in self.memory.get_top_k(k=5):
            context.append({"role": "system", "content": f"记忆：{memory}"})
        
        # 第3优先级：工具定义（让 LLM 知道有哪些工具）
        # （通过 tools 参数传递，不占 context 空间）
        
        # 第4优先级：会话历史（从最旧开始，超出限制时丢弃最旧的）
        context.extend(self._trim_history(self.history))
        
        return context
```

**优先级的意义**：系统提示词定义了 Agent 的行为，绝不能被裁剪；最近的 N 条记忆是个性化的关键，优先保留；而旧的对话历史则是最可牺牲的。这个优先级顺序体现了工程判断，而不是随意决定的。

**mini_agent 的改进方向**：可以在 ch05 的 `ContextWindowManager` 中加入优先级感知的裁剪：先保护系统消息，再保护最近 N 条消息，最后才裁剪较旧的历史。

---

### 2. 自动压缩 vs 手动压缩：两种设计哲学

**nanobot AutoCompact**：主动防御型

```python
class AutoCompact:
    """在 before_iteration Hook 中检查，超过阈值时自动压缩"""
    
    async def check_and_compact(self, context: AgentContext) -> None:
        token_count = self.counter.count(context.messages)
        capacity = context.token_limit
        
        if token_count / capacity > 0.8:  # 超过 80% 容量
            # 在当前迭代开始前压缩，不打断推理
            summary = await self._summarize_old_messages(context.messages)
            context.replace_old_messages_with_summary(summary)
            logger.info(f"AutoCompact: {token_count} → {self.counter.count(context.messages)} tokens")
```

**为什么选择 80% 而不是 100%**：

如果等到 100% 才压缩，LLM 下一次调用就会失败（API 报错）。选择 80% 留有余量，确保有足够空间让压缩后的上下文 + 摘要文本 + 下一轮工具调用都能放下。这个阈值需要根据实际使用调整。

**hermes-agent 和 openclaw**：用户主导型

```
# 用户需要自己判断何时压缩
> /compress
正在压缩对话历史...
已将 47 条消息压缩为 3 条摘要。节省了约 6,200 tokens。
```

**哪种更好？** 这是一个真实的工程权衡：

- 自动压缩：用户体验更流畅，但压缩时机由系统决定，可能在关键推理中途压缩导致信息丢失
- 手动压缩：用户完全控制，但需要用户理解 token 概念，学习曲线更陡

对于面向普通用户的产品，自动压缩更好；对于高级用户（程序员），手动控制更受欢迎。

---

### 3. Token 计数器的精度与性能权衡

**mini_agent** 的降级策略：

```python
try:
    import tiktoken
    enc = tiktoken.encoding_for_model("gpt-4o")
    # 精确计数：每个 token 准确无误
    return len(enc.encode(text))
except ImportError:
    # 降级回退：len(text) // 4，误差约 ±20%
    return len(text) // 4
```

`len(text) // 4` 的依据：英文平均每个词 ~4 字符，每个词 ~1 token。对于中文，这个比例更不准确（中文字符更密集）。

**更精确的近似公式**（不需要 tiktoken）：

```python
# 更准确的启发式估算
def estimate_tokens(text: str) -> int:
    # 英文词汇约 1 token/词
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    # 数字和标点约 1 token/个
    numbers_punct = len(re.findall(r'[0-9\.,!?;:]', text))
    # 中文字符约 0.6 token/字（BPE 倾向于将中文词组合为多 token）
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    
    return int(english_words + numbers_punct + chinese_chars * 1.5)
```

**nanobot 的做法**：为每个提供商维护不同的 Token 计数器，因为不同模型使用不同的 tokenizer（GPT-4 和 Claude 对同一文本的 token 计数可能相差 10–20%）。精确计数对于接近上下文窗口边界的场景非常重要。

---

### 4. 系统提示词的保护策略

所有生产级项目都有一个共识：**系统提示词必须受到保护，无论如何都不能被裁剪**。

**nanobot** 的保护方式：

```python
def _trim_history(self, messages: list[dict], budget: int) -> list[dict]:
    # 系统消息单独处理，不进入裁剪候选池
    system_messages = [m for m in messages if m["role"] == "system"]
    history_messages = [m for m in messages if m["role"] != "system"]
    
    # 计算历史消息可用的 token 预算（总预算 - 系统消息占用）
    system_tokens = self.counter.count(system_messages)
    history_budget = budget - system_tokens
    
    # 只从历史消息中裁剪
    trimmed = self._sliding_window(history_messages, history_budget)
    return system_messages + trimmed
```

**为什么这很重要**：如果系统提示词被裁剪，Agent 会失去对自己角色、能力、规则的记忆，行为会变得不可预测。这种情况下的错误很难调试，因为表现是"Agent 似乎不记得它的限制了"而不是明显的报错。

---

### 5. 流式输出中的上下文管理

这是一个在 mini_agent 中没有涉及但非常重要的问题：**在 LLM 正在流式输出时，如何安全地进行上下文管理？**

问题场景：nanobot 在 `before_iteration` Hook 中检查上下文，发现需要压缩。但此时前一次迭代的流式输出可能还没有完全结束（用户还在看 token 一个个出现）。

**nanobot 的解决方案**：将自动压缩设计为**只在迭代边界触发**（`before_iteration`，而不是在流式传输过程中）。这保证了：

1. 每次压缩都在 LLM 完成完整回复后才发生
2. 用户不会看到"回复被突然截断"
3. 压缩后的上下文是完整的，LLM 下一轮可以正常工作

## 设计模式提炼

| 设计维度 | mini_agent | nanobot | hermes-agent | openclaw |
|---------|-----------|---------|-------------|---------|
| Token 计数 | tiktoken + 降级 | 按模型精确计数 | litellm 内置 | tiktoken-like |
| 压缩触发 | 无自动触发 | 80% 容量自动触发 | /compress 手动 | /compact 手动 |
| 组装优先级 | 无 | 系统→记忆→历史 | 系统→历史 | 系统→Context文件→历史 |
| 系统消息保护 | 无专门保护 | 独立保护，不裁剪 | 独立保护 | 独立保护 |
| 流式安全 | N/A | 迭代边界压缩 | 迭代边界压缩 | 迭代边界压缩 |

## 对初学者的启示

1. **上下文管理是"隐形基础设施"**：用户永远看不到你做了多少上下文管理工作，但他们能感受到 Agent 是否"记得清楚"。这是最需要做但最不被看见的工程工作之一。

2. **保护系统消息是第一要务**：永远先计算系统消息的 token 数，再决定历史消息可以用多少预算。这个顺序不能颠倒。

3. **80% 阈值是经验值**：自动压缩的触发阈值需要根据你的工具调用和响应长度调整。工具结果很长（如代码文件内容）时，可能需要更保守的 60% 阈值。

4. **精确 Token 计数有时很重要**：对于使用免费或低成本模型（上下文窗口小）的 Agent，`len(text) // 4` 的误差可能导致频繁的 API 错误。在接近边界时，精确计数值得额外的依赖。

## 延伸学习资源

- [nanobot/agent/context.py](https://github.com/HKUDS/nanobot/blob/main/nanobot/agent/context.py) — ContextBuilder 完整实现
- [nanobot/agent/autocompact.py](https://github.com/HKUDS/nanobot/blob/main/nanobot/agent/autocompact.py) — AutoCompact 实现
- [tiktoken 文档](https://github.com/openai/tiktoken) — OpenAI 官方分词库
- [Anthropic 上下文管理最佳实践](https://docs.anthropic.com/en/docs/build-with-claude/context-windows) — Claude 上下文窗口指南
