# 扩展阅读：多层次记忆在主流 Agent 项目中的实现

## 本章回顾

ch12 展示了四层记忆架构：**工作记忆**（当前上下文）→ **情景记忆**（历史会话摘要）→ **语义记忆**（事实性知识）→ **程序性记忆**（技能，指向 ch10）。通过 `MultiLevelMemoryManager` 门面，Agent 可以在会话结束时压缩历史、在新会话开始时重建上下文，实现真正的长期记忆。

---

## hermes-agent 的多层次记忆实现

hermes-agent（NousResearch）的记忆系统是目前开源 Agent 中工程化程度最高的之一，其设计与本章的四层模型高度对应。

### Tier 1 对应：会话历史 + `/compress` 命令

hermes-agent 通过内置的 `/compress` 命令手动或自动压缩工作记忆：

```bash
/compress        # 将当前会话历史压缩为摘要，释放 context window 空间
/usage           # 查看当前 token 用量
```

内部实现（简化示意）：

```python
async def compress_context(self, messages: list[Message]) -> str:
    """将长对话历史压缩为简短摘要，注入为新的 system message。"""
    compression_prompt = [
        {"role": "system", "content": "请将以下对话历史压缩为简短摘要，保留关键信息。"},
        *[m.to_dict() for m in messages],
    ]
    summary = await self.llm.complete(compression_prompt)
    return summary
```

### Tier 2 对应：FTS5 会话搜索

hermes-agent 使用 **SQLite FTS5** 索引所有历史会话，支持高效的全文搜索：

```sql
-- hermes-agent 的会话索引（简化示意）
CREATE VIRTUAL TABLE sessions_fts USING fts5(
    session_id,
    summary,
    content,
    tokenize='unicode61 trigram'  -- 支持中日韩语言
);

-- 检索相关会话
SELECT session_id, summary, rank
FROM sessions_fts
WHERE sessions_fts MATCH '排序 DataFrame'
ORDER BY rank
LIMIT 5;
```

与本章的关键词匹配相比，FTS5 的优势：
- **词形变换**：sort / sorting / sorted 均能匹配
- **相关性排序**：BM25 算法自动计算相关性分数
- **Unicode 支持**：中文、日文、韩文的全文检索

### Tier 3 对应：MEMORY.md + Honcho 用户建模

hermes-agent 的语义记忆分为两部分：

**MEMORY.md（平面文本）**

```markdown
# Agent Memory

## User Profile
- Name: Alice
- Preferred language: Python
- Domain: Data analysis
- Code style: concise, minimal comments

## Preferences
- Prefers direct answers without preamble
- Likes code examples over explanations
```

**Honcho 用户建模（结构化 + AI 推理）**

[Honcho](https://github.com/plastic-labs/honcho) 是 hermes-agent 集成的用户建模服务，它不仅存储用户信息，还通过"辩证推理"（dialectic inference）从对话中推断用户的深层偏好：

```python
# hermes-agent + Honcho 集成（简化示意）
from honcho import HonchoClient

client = HonchoClient(app_id="hermes", user_id=user_id)

# 存储一条观察
client.apps.users.sessions.messages.create(
    app_id="hermes",
    user_id=user_id,
    session_id=session_id,
    content=user_message,
    is_user=True,
)

# 获取用户建模推断
user_model = client.apps.users.get_by_name(app_id="hermes", name=user_id)
# user_model 包含：工作领域、技能水平、沟通风格、常见需求…
```

Honcho 的"辩证推理"工作原理：

```
用户消息流
    │
    ▼
Honcho 分析对话模式
    │
    ├── 直接陈述："我用 Python"         → 高置信度事实
    │
    ├── 行为模式："总是要求简洁代码"     → 推断偏好
    │
    └── 反馈信号："这个答案太复杂了"     → 更新用户模型
    │
    ▼
结构化用户模型 → 注入到下次对话的 system prompt
```

### Tier 4 对应：Skills Hub

hermes-agent 的程序性记忆（Skills）在第十章的扩展阅读中已详细介绍。在多层次记忆体系中，它是持久性最强的一层——技能一旦学会便很少"遗忘"，除非被显式删除或替换。

---

## Mem0：专为 Agent 设计的向量记忆库

[Mem0](https://github.com/mem0ai/mem0) 是一个专为 AI Agent 构建的记忆层，支持向量检索，与本章的架构高度互补：

```python
from mem0 import Memory

# 初始化（自动使用向量数据库）
memory = Memory()

# 添加记忆（自动提取并向量化）
memory.add("Alice 是数据科学家，主要使用 Python 和 Pandas", user_id="alice")
memory.add("Alice 喜欢简洁代码，不喜欢过多注释", user_id="alice")

# 语义搜索（不需要精确关键词）
results = memory.search("用户的技术背景", user_id="alice")
# → [{"memory": "Alice 是数据科学家，主要使用 Python 和 Pandas", "score": 0.95}]

# 获取全部记忆
all_memories = memory.get_all(user_id="alice")
```

**与本章 SemanticMemory 的对比**：

| 维度 | 本章 SemanticMemory | Mem0 |
|------|-------------------|------|
| 检索方式 | 关键词精确匹配 | 向量语义搜索 |
| 存储格式 | 结构化 JSON（键值） | 非结构化自然语言 |
| 依赖 | 零依赖 | 需要向量模型 + 数据库 |
| 适用场景 | 教学、原型 | 生产环境 |
| 查询示例 | `recall("user.language")` | `search("用户技术背景")` |

---

## 记忆衰减与遗忘机制

人类记忆会随时间衰减。Agent 的记忆系统也可以引入类似机制：

### 策略一：置信度衰减（本章支持）

```python
# 定期降低长时间未更新的事实的置信度
for fact in semantic.get_all().values():
    days_since_update = (now - fact.updated_at).days
    if days_since_update > 90:
        fact.confidence *= 0.9  # 每 90 天降低 10% 置信度
```

### 策略二：情景记忆压缩（归档远期记忆）

```python
# 将 6 个月前的情景进一步压缩为更短的"年度摘要"
old_episodes = [ep for ep in episodic.list_all()
                if age(ep) > timedelta(days=180)]
annual_summary = llm.summarise(old_episodes)
episodic.archive(old_episodes, summary=annual_summary)
```

### 策略三：按使用频率管理（LRU）

```python
# 删除最近 6 个月从未被检索的情景记忆
stale = [ep for ep in episodic.list_all()
         if ep.last_accessed < six_months_ago]
for ep in stale:
    episodic.delete(ep.session_id)
```

---

## 记忆注入策略：如何构建 System Prompt

记忆是否有用，关键在于**如何注入到 LLM 的上下文**中。几种常见策略：

### 策略一：全量注入（适合记忆少时）

```python
system_prompt = f"""
你是 Alice 的个人助手。

{manager.context_for_new_session()}
"""
```

### 策略二：按需检索注入（hermes-agent 方式）

```python
# 只检索与当前任务最相关的记忆
relevant_episodes = episodic.search(user_input, top_k=3)
user_profile = semantic.by_category("user_profile")

system_prompt = f"""
你是 {semantic.recall('user.name')} 的助手。

用户档案：{format_facts(user_profile)}

相关历史：
{format_episodes(relevant_episodes)}

请根据以上背景信息回答用户的问题。
"""
```

### 策略三：分区注入（结构化 system prompt）

```python
# hermes-agent 使用分区 system prompt
system_prompt = f"""
<identity>你是 Hermes，一个自改进 AI 助手。</identity>

<user_profile>
{semantic_facts_str}
</user_profile>

<recent_context>
{episodic_summary_str}
</recent_context>

<skills>
{procedural_hints_str}
</skills>
"""
```

---

## 多层次记忆的生产设计建议

| 层次 | 生产方案 | 本章方案（教学） |
|------|---------|--------------|
| 工作记忆 | tiktoken 精确 token 计数 + 自动压缩 | deque maxlen |
| 情景记忆 | SQLite FTS5 + 向量混合检索 | JSON + 关键词匹配 |
| 语义记忆 | Honcho / Mem0 + PostgreSQL | JSON KV |
| 程序性记忆 | SQLite + 向量索引 | JSON + 关键词匹配 |

---

## 延伸学习资源

- [hermes-agent Memory 文档](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory) — 持久化记忆和用户档案的完整用户指南
- [Honcho](https://github.com/plastic-labs/honcho) — 专为 Agent 设计的用户建模服务（辩证推理）
- [Mem0](https://github.com/mem0ai/mem0) — 带向量检索的 Agent 记忆层
- [Zep](https://github.com/getzep/zep) — 生产级 Agent 长期记忆服务（时序 + 语义）
- [MemGPT/Letta](https://github.com/letta-ai/letta) — 虚拟上下文分页的记忆管理框架
- [Cognitive Architectures for Language Agents](https://arxiv.org/abs/2309.02427) — 从认知科学角度分析 Agent 记忆架构的综述论文
- [Generative Agents](https://arxiv.org/abs/2304.03442) — Stanford 的情景记忆 + 反思循环经典论文
