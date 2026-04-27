# 扩展阅读：记忆系统设计 — 主流 Agent 项目实现对比

## 本章回顾

ch04 构建了两层记忆系统：`ConversationMemory`（用 deque 实现的滑动窗口短期记忆）和 `PersistentMemory`（JSON 文件键值对长期记忆），并用 `MemoryManager` 门面统一管理。核心思想：**对话上下文（易失）与用户知识（持久）是两种不同的记忆需求，应该分开设计**。

## 为什么要看其他项目？

mini_agent 的记忆系统解决了"基本问题"：让 Agent 记住当前对话和几个关键事实。但生产级 Agent 面临更难的问题：如何跨会话维护连贯的用户模型？如何在百万条历史对话中快速找到相关记忆？如何让 Agent 自动决定记什么、忘什么？这些问题的解决方案揭示了记忆系统的真正复杂性。

## 项目简介

| 项目 | 语言 | 记忆系统特色 |
|------|------|------------|
| mini_agent ch04 | Python | deque 短期 + JSON 长期，字符串搜索 |
| nanobot (HKUDS) | Python | Dream 两阶段整合，LLM 驱动压缩，FTS 全文搜索 |
| hermes-agent (NousResearch) | Python | FTS5 SQLite 搜索，Honcho 用户建模，技能即程序化记忆 |
| openclaw | TypeScript | MEMORY.md/USER.md/SOUL.md 文件，人类可读 |

## 核心设计对比

### 1. 存储格式：结构化 JSON vs 人类可读 Markdown

**mini_agent** 的持久化记忆用 JSON 键值对：

```json
{
  "user_name": "Alice",
  "preferred_lang": "Python",
  "last_topic": "AI agents"
}
```

**优点**：查询快（O(1) 按键查找），格式标准，便于程序处理。
**缺点**：需要 Agent 提前知道存哪些键，不灵活；人类不容易直接阅读和手动编辑。

**openclaw** 使用 Markdown 文件存储记忆：

```markdown
# MEMORY.md — Agent 的长期记忆

## 用户偏好
- 喜欢简洁的代码解释，不喜欢冗长的铺垫
- 主要使用 Python，偶尔写 TypeScript

## 进行中的任务
- 正在学习 AI Agent 开发，第 4 章

## 重要事实
- 用户名：Alice，时区：UTC+8
```

**优点**：人类可以直接读取和编辑记忆文件；Agent 可以用自然语言描述复杂的、难以结构化的信息；无需预定义 schema。
**缺点**：搜索需要文本匹配而非精确查询；格式取决于 Agent 的写作习惯，可能不一致。

**设计洞察**：JSON 是"数据库思维"，Markdown 是"笔记本思维"。对于经常变化、难以结构化的用户信息（如"用户偏好轻松幽默的对话风格"），Markdown 反而更自然。

---

### 2. Dream 记忆整合：空闲时的自动压缩

**nanobot** 实现了一个非常有趣的设计——**Dream**（类比人类的梦境记忆整合理论）：

```python
class Dream:
    """在 Agent 空闲时（没有用户请求时）自动运行的记忆整合器"""
    
    async def run(self) -> None:
        # 阶段1：分析最近的对话，提取值得记住的信息
        facts_to_remember = await self._extract_facts(recent_messages)
        
        # 阶段2：与已有记忆合并，更新过时信息，删除无关信息
        updated_memory = await self._merge_with_existing(
            new_facts=facts_to_remember,
            existing_memory=self.memory.get_all()
        )
        
        # 阶段3：将整合后的记忆写回
        await self.memory.save(updated_memory)
```

**为什么在空闲时运行？**

如果在每次对话后立即整合记忆，会延长用户等待时间（需要额外的 LLM 调用）。在用户不活跃时（比如深夜）悄悄整合，就像人类在睡眠中固化记忆一样，对用户完全透明。

**两阶段整合的价值**：单纯存储"用户说了什么"容量有限。整合阶段做的事情是：把"用户在第3次对话中提到喜欢简洁代码，在第7次对话中抱怨解释太长"合并为"用户偏好简洁的代码解释"——更高层次、更持久的知识。

---

### 3. 记忆检索：字符串匹配 vs 全文搜索 vs 向量搜索

**mini_agent** 使用简单字符串匹配：

```python
def search(self, query: str) -> dict:
    return {k: v for k, v in self.data.items() if query in str(v) or query in k}
```

**优点**：零依赖，实现简单。
**缺点**：无法处理近义词（搜"代码"找不到"programming"）；无排名（所有结果同等重要）；不支持复杂查询。

**hermes-agent** 使用 SQLite FTS5（全文搜索）：

```python
# 创建全文索引
cursor.execute("""
    CREATE VIRTUAL TABLE memories_fts USING fts5(
        key, value, timestamp,
        tokenize='trigram'  -- 支持中文分词
    )
""")

# 检索时使用 FTS5 语法
results = cursor.execute(
    "SELECT * FROM memories_fts WHERE memories_fts MATCH ? ORDER BY rank",
    (query,)
).fetchall()
```

FTS5 的优势：支持词干还原（search/searching/searched 都能匹配）；结果按相关性排序；支持布尔运算（`Python AND 编程`）；在百万条记录中仍然快速。

**向量搜索（语义搜索）**：mini_agent 和以上项目都没有实现向量搜索。向量搜索把每条记忆和查询都编码成向量（Embedding），通过余弦相似度找到语义上最接近的结果，而不是文字匹配。

```
查询："Python 代码风格"
匹配："用户偏好简洁的编程习惯"（虽然没有相同词汇，但语义相关）
```

向量搜索适合大型记忆库，但需要 Embedding 模型，增加了成本和延迟。

---

### 4. Honcho 用户建模：超越记忆的用户理解

**hermes-agent** 集成了 [Honcho](https://github.com/plastic-labs/honcho)，一个专门用于**用户建模**的开源库：

```python
# Honcho 使用"辩证法"（dialectic）方式构建用户模型
# 不只是记住用户说了什么，而是推断用户的心理模型
honcho.update_user_model(
    user_id="alice_123",
    message="我不喜欢长段落的解释",
    inference="用户偏好简洁、直接的交流风格，可能有较高的技术水平"
)

# 下次对话时注入用户模型
user_profile = honcho.get_user_model("alice_123")
system_prompt += f"\n关于用户的推断：{user_profile}"
```

这比"记住用户说过什么"更进一步——Agent 会尝试推断用户的认知风格、偏好、专业水平，并将这些推断注入每次对话的系统提示词中。

**与 mini_agent 对比**：mini_agent 记的是"事实"（`user_name: Alice`）；Honcho 建模的是"人"（`Alice 是一个有经验的工程师，喜欢直接获取答案，不需要基础概念解释`）。

---

### 5. 技能作为程序化记忆

**hermes-agent** 有一个独特的记忆形式：**Skills（技能）作为程序化记忆**。

当 Agent 通过多步骤完成了一个复杂任务（比如"自动部署 Flask 应用到 VPS"），它不只是记住"我做过这件事"，而是把整个操作流程提炼成一个可复用的 Skill：

```python
# Agent 自动创建的技能
class DeployFlaskAppSkill(Skill):
    name = "deploy_flask_app"
    description = "把 Flask 应用部署到 VPS 的完整流程"
    
    def execute(self, app_dir: str, server_ip: str) -> str:
        # 步骤1：打包应用
        # 步骤2：SCP 上传
        # 步骤3：配置 Nginx
        # 步骤4：启动 Gunicorn
        ...
```

下次用户说"帮我部署这个 Flask 应用"，Agent 直接调用这个 Skill，而不需要再次推理所有步骤。这是"学习"在 Agent 中的一种具体实现形式。

## 设计模式提炼

| 设计维度 | mini_agent | nanobot | hermes-agent | openclaw |
|---------|-----------|---------|-------------|---------|
| 短期记忆 | deque 滑动窗口 | deque + Session | deque + SQLite | 会话文件 |
| 长期记忆格式 | JSON 键值对 | JSON + LLM 整合 | SQLite + FTS5 | Markdown 文件 |
| 记忆检索 | 字符串匹配 | 全文搜索 | FTS5 SQLite | 文本匹配 |
| 自动整合 | 无 | Dream（空闲时运行） | 周期性 Nudge | 无 |
| 用户建模 | 无 | 无 | Honcho 辩证法 | USER.md 文件 |
| 程序化记忆 | 无 | 无 | Skills 自创建 | Skills YAML |

## 对初学者的启示

1. **从简单开始是对的**：JSON 键值对是最容易理解和调试的记忆形式。在证明你需要更复杂的方案之前，不要过早引入数据库或向量搜索。

2. **两种记忆需求是不同的**：对话历史（需要按时间顺序读取，会老化）和用户知识（需要按主题查询，长期有效）本质上是不同的数据，用不同的存储结构更合理。

3. **Dream 模式揭示了一个深刻洞察**：整合比存储更有价值。100 条原始对话不如 10 条精炼的洞察。Agent 设计中的"整合"步骤通常被忽视，但对长期使用体验影响巨大。

4. **向量搜索是可扩展性的关键**：当记忆库超过几千条时，字符串匹配和 FTS5 都会面临准确性问题（无法处理语义相关但词汇不同的情况）。向量搜索是这个问题的标准解决方案。

## 延伸学习资源

- [nanobot/agent/memory.py](https://github.com/HKUDS/nanobot/blob/main/nanobot/agent/memory.py) — Dream 记忆整合的完整实现
- [Honcho 文档](https://github.com/plastic-labs/honcho) — 辩证用户建模库
- [SQLite FTS5 文档](https://www.sqlite.org/fts5.html) — 全文搜索的官方说明
- [OpenAI Embeddings 指南](https://platform.openai.com/docs/guides/embeddings) — 向量搜索的入门材料
