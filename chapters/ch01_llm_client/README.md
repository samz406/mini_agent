# 第一章：LLM 客户端抽象层

## 你将学到什么

本章教你如何在任意 LLM API 之上构建一个干净、可复用的**抽象层**。与其在代码中到处直接调用 OpenAI，不如定义一个统一的接口——这样将来想换成其他提供商，只需替换一个类，其余代码完全不用动。

> 📖 学完本章后，可以阅读 `extended_reading.md`，了解 nanobot、hermes-agent 等主流项目是如何设计 LLM 客户端的。

## 核心概念

### 1. 抽象基类（ABC）模式

`BaseLLMClient` 是一个抽象基类，它定义了一个"契约"：任何 LLM 客户端都必须实现 `complete()` 和 `stream()` 这两个方法。

**通俗理解**：就像"充电器"有统一的接口标准，不管是哪个品牌的手机，充电口的形状是一样的。抽象基类就是定义这个"接口形状"。

```python
class BaseLLMClient(ABC):
    @abstractmethod
    def complete(self, messages: list[Message]) -> Message:
        """发送消息，等待完整回复"""
        ...
    
    @abstractmethod  
    def stream(self, messages: list[Message]) -> Iterator[str]:
        """发送消息，逐词返回回复（流式输出）"""
        ...
```

有了这个抽象基类，你可以轻松替换底层实现：

```python
# 用 OpenAI
agent = AgentLoop(llm_client=OpenAIClient(api_key="sk-..."))

# 换成 DeepSeek，Agent 代码一行不用改
agent = AgentLoop(llm_client=OpenAIClient(api_key="sk-...", api_base="https://api.deepseek.com/v1"))

# 测试时用 Mock，完全不需要 API Key
agent = AgentLoop(llm_client=MockLLMClient())
```

### 2. 重试机制与指数退避

LLM 服务商会对 API 调用频率做限制（Rate Limit）。当你调用过于频繁时，服务会返回错误。

**指数退避（Exponential Backoff）**：遇到错误时不立即放弃，而是等待一段时间后重试。等待时间按指数增长：第1次失败等1秒，第2次等2秒，第3次等4秒……这样既避免了立即重试造成的雪崩，又不会等太久。

```python
for attempt in range(self.max_retries):
    try:
        response = self.client.chat.completions.create(...)
        return Message(role="assistant", content=response.choices[0].message.content)
    except RateLimitError:
        wait_time = 2 ** attempt  # 1秒, 2秒, 4秒, 8秒...
        time.sleep(wait_time)
```

### 3. 流式输出（Streaming）

普通模式：等 AI 生成完整回复后，一次性返回全部文字。
流式模式：AI 每生成一个词就立即发送，用户能看到文字逐渐出现。

流式输出对用户体验非常重要——对于长回复，普通模式可能需要等待 10+ 秒，而流式输出几乎立刻就能看到内容开始出现。

```python
# 流式输出：逐词 yield
def stream(self, messages):
    response = self.client.chat.completions.create(stream=True, ...)
    for chunk in response:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content  # 每次 yield 一小块文字
```

### 4. `Message` 数据类

用一个简单的 `Message(role, content)` 结构体来统一表示对话消息，将 Agent 逻辑与 API 细节解耦。

```python
@dataclass
class Message:
    role: str     # "user", "assistant", 或 "system"
    content: str  # 消息文本内容
```

## 代码流程图

```
用户调用 complete(messages)
         │
         ▼
    尝试调用 OpenAI API
         │
    ┌────┴────┐
    │成功      │失败（Rate Limit）
    ▼         ▼
 返回回复   等待 2^n 秒
             │
             ▼
          重试（最多 max_retries 次）
             │
         超出重试次数
             │
             ▼
          抛出异常
```

## 如何运行

```bash
cd chapters/ch01_llm_client

# 设置你的 API Key（选一个你有的提供商）
export DEEPSEEK_API_KEY=sk-your-key-here
# 或者
export DASHSCOPE_API_KEY=sk-your-key-here

python llm_client.py
```

运行后，你将看到：
1. 非流式调用：AI 一次性返回对 "Hello! What can you do?" 的回复
2. 流式调用：AI 的回复逐词打印出来

> ⚠️ 第一章需要真实的 API Key 才能运行。如果你还没有，可以先跳到第二章（使用模拟 LLM，不需要 Key）。
