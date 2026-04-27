# 扩展阅读：LLM 客户端抽象层 — 主流 Agent 项目实现对比

## 本章回顾

ch01 用抽象基类（ABC）定义了 `BaseLLMClient` 接口，实现了 `OpenAIClient`（含指数退避重试和流式输出），并提供 `MockLLMClient` 用于无 Key 测试。核心思想：**将 Agent 逻辑与 LLM 提供商解耦**。

## 为什么要看其他项目？

mini_agent 的 LLM 客户端是"最小可行版本"——清晰展示核心概念。真实项目中，这个层需要支持并发用户、多个提供商之间的自动切换、成本追踪、以及在不中断对话的前提下热切换模型。比较不同实现，能让你看到"从 demo 到生产"之间的真实距离。

## 项目简介

| 项目 | 语言 | 定位 | LLM 客户端特色 |
|------|------|------|--------------|
| mini_agent ch01 | Python | 教学项目 | 简洁 ABC 抽象，单提供商，同步调用 |
| nanobot (HKUDS) | Python | 轻量生产级 | ProviderSnapshot + 异步 AsyncGenerator |
| hermes-agent (NousResearch) | Python | 自进化代理 | litellm 统一接口，200+ 模型，会话中切换 |
| openclaw | TypeScript | 个人助手 | OAuth 订阅式，模型故障转移，thinking 级别 |

## 核心设计对比

### 1. 提供商注册表：静态 vs 动态

**mini_agent** 的提供商在 `providers.py` 中硬编码为字典：

```python
PROVIDERS = {
    "openai": ProviderConfig(name="openai", api_base="https://api.openai.com/v1", ...),
    "deepseek": ProviderConfig(name="deepseek", api_base="https://api.deepseek.com/v1", ...),
}
```

这种方式简单直接，但添加新提供商需要修改源代码。

**nanobot** 使用 `ProviderSnapshot` 设计——提供商配置在运行时从配置文件加载，并支持 MCP（Model Context Protocol）服务器作为 LLM 来源：

```python
class ProviderSnapshot:
    """运行时可替换的提供商快照。
    
    每次用户切换提供商时，生成一个新快照，
    不影响正在进行的请求。
    """
    provider: LLMProvider
    model: str
    snapshot_id: str  # 用于追踪哪个快照服务了哪些请求
```

**hermes-agent** 借助 `litellm` 库支持 200+ 模型。litellm 是一个统一接口库，把 OpenAI、Anthropic、Cohere、HuggingFace 等几十个提供商的 API 归一化为相同的调用格式：

```python
# litellm 让切换提供商变成只改一个字符串
response = litellm.completion(
    model="gpt-4o-mini",       # 或 "claude-3-5-sonnet", 或 "deepseek/deepseek-chat"
    messages=messages,
)
```

**设计权衡**：硬编码注册表实现简单，适合教学和小项目；动态注册表（配置文件/插件系统）适合需要经常增删提供商的场景；litellm 这样的适配层则是"一劳永逸"方案，但引入了额外依赖和一层抽象。

---

### 2. 流式输出：Iterator vs AsyncGenerator vs WebSocket

**mini_agent** 使用同步 `Iterator[str]`：

```python
def stream(self, messages) -> Iterator[str]:
    response = self.client.chat.completions.create(stream=True, ...)
    for chunk in response:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
```

调用方用 `for token in client.stream(messages)` 逐 token 处理。同步迭代器简单，但每次 yield 时会阻塞当前线程。

**nanobot** 使用异步 `AsyncGenerator`：

```python
async def stream(self, messages) -> AsyncGenerator[str, None]:
    async for chunk in await self.async_client.chat.completions.create(stream=True, ...):
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
```

`async for` 在等待下一个 token 时，Python 的事件循环可以去处理其他协程（比如响应另一个用户的请求）。这是多用户并发场景的必要条件。

**openclaw** 是 TypeScript 项目，通过 WebSocket 把流式 token 实时推送到前端/Telegram/Discord 等渠道：

```typescript
// Node.js EventEmitter + WebSocket 模式
for await (const chunk of stream) {
  this.emit('token', chunk.choices[0].delta.content);
  await this.gateway.broadcast(chunk);  // 同时推送到所有订阅渠道
}
```

**关键洞察**：流式输出的实现方式取决于你的并发模型。单用户 CLI 工具用同步 Iterator 够了；多用户服务需要异步；实时推送到多个渠道需要事件系统或 WebSocket。

---

### 3. 重试策略：固定退避 vs 自适应重试

**mini_agent** 的指数退避是固定的：

```python
wait = 2 ** attempt  # 1s, 2s, 4s, 8s ...
```

**nanobot** 有三种重试模式（`provider_retry_mode`）：
- `"none"`：不重试，立即报错
- `"standard"`：指数退避（类似 mini_agent）
- `"aggressive"`：更激进的重试，适合任务关键型场景

不同场景适合不同策略：交互式 CLI 用户可以接受"等 1 秒后重试"；自动化批处理任务则可能需要更强的重试保证。

**hermes-agent** 额外追踪 API 调用的 token 消耗和错误率，当错误率上升时自动切换到备用提供商（Model Failover），而不仅仅是重试同一个提供商。

---

### 4. 模型切换的用户体验

**mini_agent** 通过 `--provider` CLI 参数在启动时选择提供商，对话开始后不能切换。

**hermes-agent** 支持在对话进行中切换：

```
> /model openrouter:anthropic/claude-3-5-sonnet
已切换到 claude-3-5-sonnet。当前对话历史将继续使用。
```

切换后，对话历史保持不变，新模型会继承完整的上下文。这对于需要在不同任务中使用不同模型（比如写代码用 Sonnet，对话用更便宜的模型）的场景非常有用。

**openclaw** 更进一步，支持**模型故障转移（Model Failover）**：预先配置多个 API Key 和模型，当主力模型不可用时自动切换到备用模型，整个过程对用户透明。

---

## 设计模式提炼

| 设计维度 | mini_agent | nanobot | hermes-agent | openclaw |
|---------|-----------|---------|-------------|---------|
| 接口设计 | ABC 抽象基类 | LLMProvider 协议类 | litellm 统一包装 | TypeScript 接口 |
| 流式实现 | 同步 Iterator | 异步 AsyncGenerator | 异步 AsyncGenerator | WebSocket 广播 |
| 重试策略 | 固定指数退避 | 3 种可配置模式 | 多提供商故障转移 | OAuth 配置自动轮换 |
| 模型切换 | 启动时固定 | 运行时热切换 | 对话中 /model 切换 | 自动故障转移 |
| 成本追踪 | 无 | 日志 token 用量 | /usage 命令 | 无 |

## 对初学者的启示

1. **抽象是杠杆**：`BaseLLMClient` 让整个教程剩余部分与具体 API 无关。这个思想贯穿整个软件工程——好的抽象乘以你的代码价值。

2. **同步先行，异步随后**：先用同步 Iterator 把逻辑跑通，需要多用户并发时再迁移到异步。过早的异步化是初学者最常见的过度复杂化陷阱。

3. **litellm 是生产捷径**：如果你不需要教学目的，直接用 litellm 可以省掉大量提供商适配工作，但你也会错过理解底层机制的机会。

4. **重试不是万能药**：指数退避能处理瞬时网络问题，但无法处理服务长时间中断。生产系统需要多提供商故障转移。

## 延伸学习资源

- [nanobot/providers/](https://github.com/HKUDS/nanobot/tree/main/nanobot/providers) — 查看生产级 Provider 实现
- [litellm 文档](https://docs.litellm.ai) — 200+ 模型统一接口
- [OpenAI Streaming 指南](https://platform.openai.com/docs/guides/streaming) — 官方流式输出文档
- [Python ABC 文档](https://docs.python.org/3/library/abc.html) — 抽象基类的官方说明
