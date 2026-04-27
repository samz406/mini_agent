# 第四章：记忆系统

## 你将学到什么

Agent 要在多轮对话中真正有用，就需要记忆。本章构建两种互补的记忆系统，以及一个统一管理它们的门面（Facade）类。

> 📖 学完本章后，可以阅读 `extended_reading.md`，了解 nanobot 的 Dream 两阶段记忆整合、hermes-agent 的 FTS5 全文搜索记忆、openclaw 的 Markdown 记忆文件等不同设计。

## 两种记忆类型

### 对话记忆（短期记忆）

存储当前会话的消息历史，用于给 LLM 提供上下文。使用 Python 的 `collections.deque` 并设置 `maxlen`，当对话超长时自动丢弃最旧的消息。

```
[用户: 你好] [助手: 你好！] [用户: 帮我算一下] [助手: 结果是4] ... → 最旧消息被自动丢弃
```

### 持久化记忆（长期记忆）

用 JSON 文件存储的键值对，**会话结束后仍然保留**。Agent 可以把重要信息存进去，下次对话时仍然能取出。

```python
# 本次对话存储
persistent.set("user_name", "Alice")

# 重启后仍然有效
persistent.get("user_name")  # → "Alice"
```

## 关键实现细节

### `deque(maxlen=N)` 实现滑动窗口

当你往满了的 deque 追加新元素时，它会自动从左边删除最旧的元素。零维护成本：

```python
from collections import deque
buf = deque(maxlen=3)
buf.extend([1, 2, 3])  # deque([1, 2, 3])
buf.append(4)           # deque([2, 3, 4])  ← 1 被自动丢弃
buf.append(5)           # deque([3, 4, 5])  ← 2 被自动丢弃
```

### JSON 持久化

`PersistentMemory` 在每次 `set()` 或 `delete()` 时同步读写 JSON 文件。简单、轻量、无需数据库：

```python
def set(self, key: str, value: Any) -> None:
    data = self._load()          # 读取当前文件
    data[key] = value            # 更新内容
    self._save(data)             # 写回文件
```

### 字符串搜索

`search(query)` 在所有键和值中查找包含查询字符串的条目：

```python
persistent.set("preferred_lang", "Python")
persistent.set("user_name", "Alice")

persistent.search("Python")  # → {"preferred_lang": "Python"}
```

对小型记忆库够用；如果需要更强的搜索能力，可以替换为向量搜索（见扩展阅读）。

## MemoryManager 门面模式

**门面模式（Facade Pattern）**：把两个子系统（对话记忆 + 持久化记忆）封装在一个统一接口后面，让外部调用者不需要关心底层细节：

```python
manager = MemoryManager()

# 对话记忆操作
manager.add_message("user", "你好")           # 添加消息
messages = manager.get_conversation()         # 获取对话历史（字典列表）

# 持久化记忆操作
manager.remember("user_name", "Alice")        # 保存到文件
manager.recall("user_name")                  # 从文件读取 → "Alice"
results = manager.search_memory("Alice")     # 搜索记忆
```

**通俗理解**：就像"前台接待"——你不需要知道公司内部怎么运作，只需要跟前台说你要做什么，前台帮你协调。

## 如何运行

```bash
cd chapters/ch04_memory
python memory.py
```

运行后你会看到：
1. 对话记忆的滑动窗口效果（超出 5 条时最旧的被丢弃）
2. 持久化记忆的增删查操作
3. 字符串搜索的结果

运行期间会创建一个临时的 `.memory_demo.json` 文件，运行结束后自动清理。
