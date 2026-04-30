# 第十章：学习循环（Learning Loop）

## 你将学到什么

本章介绍 **Agent 的学习循环**：一种让 Agent 从自身经验中自动创建、存储和改进技能的机制。你将：

- 理解什么是"学习循环"以及它解决了什么问题
- 掌握经验（Experience）→ 技能合成（Synthesis）→ 技能存储（Storage）→ 技能检索（Retrieval）的完整闭环
- 学会用关键词匹配实现轻量级技能检索（无需向量数据库）
- 了解技能改进（Skill Improvement）的设计思路
- 理解 hermes-agent 学习循环的工程实现方式

> 📖 学完本章后，可以阅读 `extended_reading.md`，了解 hermes-agent 的自改进技能系统、Honcho 用户建模、以及向量检索技能库的进阶设计。

---

## 为什么需要学习循环？

### 传统 Agent 的问题：每次从零开始

传统 Agent（ch02 的 ReAct 循环）每次对话都独立执行，没有跨会话的学习能力：

```
用户："帮我整理这份数据"
Agent：[花了 5 步解决] ✓

用户（下次）："帮我整理另一份数据"
Agent：[又花了 5 步解决] ✗ 完全没有记忆上次怎么做的
```

### 学习循环的解决方案：积累可复用的技能

```
第 1 次任务 → 执行 → 成功 → 合成技能 → 存入技能库
                                              │
第 2 次相似任务 → 检索技能库 → 找到相关技能 → 参考技能执行 → 成功 → 改进技能
                                              │
第 3 次 → 检索 → 找到改进版技能 → 直接复用 → ✓
```

Agent 越用越聪明，技能库越来越丰富。

---

## 核心概念

### 经验（Experience）

一次成功任务完成的完整记录：

```python
@dataclass
class Experience:
    task: str          # 用户的原始请求
    steps: list[str]   # Agent 实际执行的步骤序列
    outcome: str       # 最终结果
    timestamp: str     # 时间戳
```

经验是技能的"原材料"。

### 技能（Skill）

从经验中提炼出来的、可复用的过程性知识：

```python
@dataclass
class Skill:
    name: str           # 唯一标识符，如 "sort_user_list"
    description: str    # 单句描述，如 "对用户列表按注册时间排序"
    trigger: list[str]  # 触发关键词，如 ["排序", "sort", "order"]
    template: str       # 可复用的执行模板（提示词或伪代码）
    version: int        # 版本号，每次改进时递增
    use_count: int      # 使用次数，用于排序优先级
```

技能与第七章的 Skill 不同：这里的技能是 **运行时动态创建的**，而第七章是静态定义的。

### 技能库（SkillStore）

持久化存储，跨会话保留所有学到的技能：

```
.skill_store.json
{
  "sort_user_list_by": {
    "name": "sort_user_list_by",
    "description": "对用户列表按注册时间排序",
    "trigger": ["排序", "sort", "列表"],
    "template": "任务：{task}\n执行步骤：...",
    "version": 2,
    "use_count": 3
  }
}
```

### 技能合成器（SkillSynthesizer）

将经验转化为技能的组件：

```python
class SkillSynthesizer:
    def synthesize(self, exp: Experience, existing: Optional[Skill]) -> Skill:
        # 1. 从任务描述提取名称和触发关键词
        # 2. 将步骤序列转为模板格式
        # 3. 如果有现有技能，执行"改进"而非"创建"
        ...
```

在 hermes-agent 中，这一步由 LLM 完成——Agent 会向 LLM 发送一个"请把这次经验提炼成技能"的提示词，LLM 直接输出结构化的 Python 技能代码。

---

## 学习循环的完整流程

```
用户请求
   │
   ▼
【检索】: SkillStore.search(task) → 找相关技能
   │
   ├── 找到 → 参考技能提示执行，记录使用次数
   │
   └── 未找到 → 从头执行
   │
   ▼
【执行】: 完成任务，记录步骤和结果
   │
   ▼
【合成】: SkillSynthesizer.synthesize(experience, existing_skill)
   │
   ├── 技能已存在 → 改进（版本号 +1，合并步骤）
   │
   └── 新技能 → 创建并命名
   │
   ▼
【存储】: SkillStore.add() 或 SkillStore.update()
   │
   ▼
下次相似任务可直接检索到此技能 ✓
```

---

## 技能检索策略

本章使用**关键词匹配**：

```python
def search(self, query: str, top_k: int = 3) -> list[Skill]:
    for skill in self._skills.values():
        score = 0
        for kw in skill.trigger:
            if kw in query_words:
                score += 2          # 触发词命中 → 高权重
        for word in query_words:
            if word in description:
                score += 1          # 描述命中 → 低权重
    return top_k_by_score
```

| 策略 | 优点 | 缺点 | 适用场景 |
|------|------|------|------|
| 关键词匹配（本章） | 零依赖，简单透明 | 无法理解语义 | 教学、原型 |
| BM25 全文检索 | 轻量，支持中文分词 | 仍是词法匹配 | 小型生产 |
| 向量检索（Embedding） | 语义理解 | 需要向量模型和索引 | 大型生产 |
| FTS5 + 向量混合 | 精度高 | 实现复杂 | hermes-agent 的方案 |

---

## 技能改进（Skill Versioning）

每次 Agent 成功完成一个与已有技能相似的任务时，不是简单覆盖，而是**改进**：

```
v1 技能（初始）:
  执行步骤:
    1. 读取输入列表
    2. 确定排序键
    3. 调用内置排序
    4. 返回有序列表

v2 技能（改进后，加入降序需求）:
  改进后的执行步骤 (v2):
    1. 读取输入列表
    2. 确定排序键
    3. 确定排序方向（升序/降序）← 新增
    4. 调用内置排序
    5. 返回有序列表
  原有步骤参考 (v1): ...
```

改进的好处：
- **知识积累**：技能越用越完善
- **版本追溯**：可以回溯历史版本了解技能是如何演化的
- **避免遗忘**：新版本保留旧版本的步骤作为参考

---

## 如何运行

```bash
cd chapters/ch10_learning_loop
python learning_loop.py
```

### 运行输出解读

```
📋 任务: 对用户列表按注册时间排序
🔍 未找到相关技能，将从头解决此任务。
🛠  执行步骤:
  1. 读取输入列表
  2. 确定排序键
  3. 调用内置排序算法
  4. 返回有序列表
✅ 结果: 列表已按指定键升序排列
🧠 学到新技能: [sort_user_list]          ← 新技能诞生

...（完成第 2、3 个任务）

--- Round 2: 相似任务，观察技能复用与改进 ---
📋 任务: 将订单列表按金额从大到小排序
🔍 找到 1 个相关技能：
  • [sort_user_list] v1（使用次数: 0）    ← 检索到相关技能！
✅ 结果: 列表已按指定键升序排列（参考技能: sort_user_list）
📈 改进现有技能: [sort_user_list] → v2   ← 技能被改进！
```

---

## 与前几章的对比

| 维度 | ch04 记忆系统 | ch07 技能系统 | **ch10 学习循环** |
|------|------------|------------|------------|
| 存储内容 | 对话历史 + KV键值 | 静态定义的工具集合 | 动态生成的过程性知识 |
| 来源 | 用户输入 | 开发者预定义 | Agent 从经验中合成 |
| 改进 | 无 | 需开发者手动更新 | 自动版本化改进 |
| 检索 | 键名精确匹配 | 名称精确匹配 | 关键词语义检索 |
| 跨会话 | ✅ JSON 持久化 | ❌ 每次重新加载 | ✅ JSON 持久化 |

---

## 核心设计模式

| 模式 | 体现 |
|------|------|
| **闭环学习（Closed-loop Learning）** | 执行 → 记录 → 合成 → 存储 → 检索 → 改进的完整闭环 |
| **经验驱动（Experience-driven）** | 技能来自真实执行，不是预先编程 |
| **版本化（Versioned Knowledge）** | 技能随使用持续改进，保留历史版本 |
| **渐进优先（Frequency-biased Retrieval）** | 高频使用的技能在检索中有更高优先级 |
