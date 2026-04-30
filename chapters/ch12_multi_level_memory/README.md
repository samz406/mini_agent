# 第十二章：多层次记忆（Multi-Level Memory）

## 你将学到什么

本章介绍 **多层次记忆系统**：将认知心理学中的记忆分层模型引入 AI Agent，让 Agent 在跨会话的长期使用过程中越来越了解用户、越来越高效。你将：

- 理解为什么单一记忆结构无法满足长期 Agent 的需求
- 掌握四层记忆架构：**工作记忆 → 情景记忆 → 语义记忆 → 程序性记忆**
- 学会在会话结束时将工作记忆压缩为情景摘要（Episode）
- 实现基于类别的语义记忆（用户画像 + 偏好）
- 理解如何在新会话开始时注入历史上下文
- 了解 hermes-agent 的多层次记忆工程实现

> 📖 学完本章后，可以阅读 `extended_reading.md`，了解 hermes-agent 的 MEMORY.md + Honcho 用户建模、Mem0 向量记忆库，以及生产环境中的记忆管理策略。

---

## 为什么需要多层次记忆？

### 第四章的局限：两层远远不够

第四章（ch04）给了我们两种记忆：
- **对话记忆**：当前会话的消息历史（deque）
- **持久化记忆**：简单的 JSON 键值对

这对于短期演示够用，但真实的长期 Agent 面临的问题：

```
问题 1：context window 有限
  100 次对话 × 平均 500 token = 50,000 token → 超出上下文窗口！

问题 2：历史信息无法检索
  用户三周前说过"我喜欢简洁代码"，Agent 已经完全不记得了。

问题 3：无法区分"事件"和"事实"
  "Alice 昨天问了排序问题"（事件）
  "Alice 使用 Python"（事实）
  ← 这两类信息需要不同的存储和检索策略。
```

### 认知心理学的启发：四层记忆模型

```
┌──────────────────────────────────────────────────────────┐
│  Tier 1：工作记忆（Working Memory）                       │
│  当前对话上下文，会话结束即清空，容量受 context window 限制  │
├──────────────────────────────────────────────────────────┤
│  Tier 2：情景记忆（Episodic Memory）                      │
│  历史会话的自然语言摘要，按时间存储，可按关键词检索           │
├──────────────────────────────────────────────────────────┤
│  Tier 3：语义记忆（Semantic Memory）                      │
│  关于用户和世界的事实性知识，结构化存储，按类别或键名查询     │
├──────────────────────────────────────────────────────────┤
│  Tier 4：程序性记忆（Procedural Memory）                  │
│  如何完成任务的步骤性技能，见第十章学习循环                  │
└──────────────────────────────────────────────────────────┘
```

---

## 核心概念

### Tier 1：工作记忆（Working Memory）

```python
class WorkingMemory:
    def __init__(self, max_messages: int = 20) -> None:
        self._buf: deque[dict] = deque(maxlen=max_messages)

    def add(self, role: str, content: str) -> None: ...
    def get_messages(self) -> list[dict]: ...    # 直接传给 LLM
    def summarise(self) -> str: ...             # 会话结束时生成摘要
    def clear(self) -> None: ...                # 会话结束后清空
```

**特点**：
- 容量受限（deque + maxlen），最旧的消息自动淘汰
- 完全在内存中，速度最快
- 会话结束时通过 `summarise()` 生成摘要，存入情景记忆

### Tier 2：情景记忆（Episodic Memory）

```python
@dataclass
class Episode:
    session_id: str       # 会话 ID（时间戳）
    summary: str          # 会话内容的自然语言摘要
    keywords: list[str]   # 检索用关键词（自动提取）
    started_at: str       # 会话开始时间
    ended_at: str         # 会话结束时间
    message_count: int    # 原始消息数量
```

**核心操作**：

```python
# 会话结束时：
episode = manager.close_session()  # 压缩工作记忆 → 情景

# 新会话开始时：
past = episodic.search("Python 排序")   # 关键词检索
recent = episodic.get_recent(n=5)       # 最近 N 个会话
```

### Tier 3：语义记忆（Semantic Memory）

```python
@dataclass
class SemanticFact:
    key: str           # "user.language"
    value: Any         # "Python"
    category: str      # "user_profile" | "preference" | "world"
    confidence: float  # 0.0–1.0，低值表示不确定或可能过时
    source: str        # "user_stated" | "inferred"
```

**核心操作**：

```python
# 从对话中提取并存储事实
semantic.remember("user.name", "Alice", category="user_profile")
semantic.remember("user.code_style", "简洁", category="preference", confidence=0.9)

# 按类别检索（构建用户画像）
profile = semantic.by_category("user_profile")

# 按键名检索
lang = semantic.recall("user.language")  # → "Python"
```

### Tier 4：程序性记忆（指向第十章）

程序性记忆（如何完成任务）由第十章的 `SkillStore` 实现。本章通过 `ProceduralMemoryRef` 将这一层显式纳入四层体系，形成完整的架构图。

---

## 完整工作流程

```
新会话开始
   │
   ▼
① 注入历史上下文（inject context）
   ├── semantic.by_category("user_profile")  → 用户画像注入 system prompt
   └── episodic.search(query)               → 相关历史会话注入 system prompt
   │
   ▼
② 会话进行中（in-session）
   └── working.add(role, content)           → 消息追加到工作记忆
   │
   ▼
③ 从对话中提取事实（fact extraction）
   └── semantic.remember(key, value, ...)   → 存入语义记忆
   │
   ▼
④ 会话结束（session end）
   └── manager.close_session()             → 工作记忆 → 情景摘要 → 持久化
                                           → 工作记忆清空
   │
   ▼
下次会话重复 ①
```

---

## 统一门面：MultiLevelMemoryManager

```python
manager = MultiLevelMemoryManager(
    max_working_messages=20,
    episodic_filepath=".episodic.json",
    semantic_filepath=".semantic.json",
)

# 访问各层
manager.working      # WorkingMemory
manager.episodic     # EpisodicMemory
manager.semantic     # SemanticMemory
manager.procedural   # ProceduralMemoryRef（指向 ch10）

# 会话结束
episode = manager.close_session()

# 新会话上下文构建
context_str = manager.context_for_new_session(query="用户上次问了什么")
```

`context_for_new_session()` 的输出会被注入到新会话的 `system` 消息中，让 Agent 在不读取全部历史的情况下，依然"记得"用户的偏好和上次的对话内容。

---

## 如何运行

```bash
cd chapters/ch12_multi_level_memory
python multi_level_memory.py
```

### 运行输出解读

```
── Session 1: 用户自我介绍 ──
  工作记忆中有 4 条消息
  → 已存入语义记忆：用户名、语言偏好、领域、代码风格
  → 会话 1 已压缩为情景记忆（4 条 → 1 个情景）

── Session 2: 用户询问排序问题 ──
  工作记忆中有 6 条消息
  → 会话 2 已压缩为情景记忆

── Session 3: 新会话开始，重建上下文 ──
  ## 关于用户的已知信息
  - user.domain: 数据分析
  - user.language: Python
  - user.name: Alice
  - user.code_style: 简洁，少注释   ← 语义记忆注入

  ## 相关历史会话摘要
  - [session-002] [用户] 帮我用 Python 对 DataFrame 按照销售额排序…
                                                        ← 情景记忆检索命中
```

---

## 各层对比

| 维度 | 工作记忆 | 情景记忆 | 语义记忆 | 程序性记忆 |
|------|---------|---------|---------|----------|
| **存储位置** | 内存 | JSON 文件 | JSON 文件 | JSON 文件（ch10） |
| **生命周期** | 单次会话 | 永久 | 永久 | 永久 |
| **容量** | 受 maxlen 限制 | 无限（磁盘） | 无限（磁盘） | 无限（磁盘） |
| **存储内容** | 原始消息 | 会话摘要 | 事实键值 | 步骤性技能 |
| **检索方式** | 顺序访问 | 关键词搜索 | 键名/类别 | 关键词匹配 |
| **认知类比** | 工作记忆 | 情景记忆 | 语义记忆 | 程序性记忆 |
| **对应认知** | 当下意识 | 自传体记忆 | 百科知识 | 肌肉记忆 |

---

## 与前几章的关系

| 章节 | 内容 | 在四层体系中的位置 |
|------|------|----------------|
| ch04 ConversationMemory | deque 对话历史 | Tier 1（工作记忆）升级版 |
| ch04 PersistentMemory | JSON KV 存储 | Tier 3（语义记忆）前身 |
| ch05 ContextManager | Token 计数与截断 | 与 Tier 1 配合使用 |
| ch10 SkillStore | 技能持久化 | Tier 4（程序性记忆）完整实现 |
| **ch12（本章）** | **四层统一架构** | **完整体系** |

---

## 核心设计模式

| 模式 | 体现 |
|------|------|
| **分层存储（Tiered Storage）** | 四层各司其职，按访问频率和生命周期分配存储策略 |
| **压缩归档（Compression）** | 工作记忆在会话结束时压缩为情景摘要，节省 token |
| **上下文重建（Context Reconstruction）** | 新会话开始时从持久化层拉取相关历史，注入 system prompt |
| **置信度管理（Confidence Tracking）** | 语义记忆支持置信度字段，标记不确定或可能过时的事实 |
| **门面模式（Facade）** | MultiLevelMemoryManager 统一入口，屏蔽四层细节 |
