# 扩展阅读：学习循环在主流 Agent 项目中的应用

## 本章回顾

ch10 展示了 Agent 学习循环的完整机制：从任务经验提炼技能、持久化到技能库、下次相似任务时检索并复用，以及基于新经验持续改进技能版本。核心思想：**Agent 应该越用越聪明，而不是每次从零出发**。

---

## hermes-agent 的学习循环实现

hermes-agent（NousResearch）是目前工程化程度最高的开源自改进 Agent 之一，其学习循环包含以下几个核心机制：

### 1. 自主技能创建（Autonomous Skill Creation）

当 Agent 完成一个复杂任务后，它会自动触发技能创建流程：

```
Agent 完成任务
    │
    ▼
内部提示词："你刚才解决了一个复杂任务。请将这个解决方案提炼为一个可复用的技能。
             技能应该是一段 Python 代码，包含完整的步骤描述和参数说明。"
    │
    ▼
LLM 输出结构化技能（Python 代码 + 元数据）
    │
    ▼
技能写入 ~/.hermes/skills/ 目录（按类别组织）
```

**关键设计**：技能本身就是 Python 代码，而不仅仅是描述性文本。这让技能可以被直接执行，而不只是被"参考"。

### 2. 周期性记忆推送（Periodic Memory Nudges）

hermes-agent 会在会话中适时触发"记忆整理"：

```python
# hermes-agent 内部机制（简化示意）
if should_nudge_memory(turn_count, last_nudge_time):
    agent.run_internal_prompt(
        "请检查本次会话，有什么重要信息应该添加到你的长期记忆？"
        "有什么模式或技能值得提炼？"
    )
```

这确保了知识不会因为会话结束而丢失。

### 3. FTS5 全文检索技能库

hermes-agent 使用 SQLite FTS5 索引所有技能，支持高效的全文搜索：

```sql
-- hermes-agent 的技能索引（简化示意）
CREATE VIRTUAL TABLE skills_fts USING fts5(
    name,
    description,
    content,
    tokenize='unicode61 trigram'  -- 支持中日韩语言
);

SELECT name, description, rank
FROM skills_fts
WHERE skills_fts MATCH '排序 列表'
ORDER BY rank;
```

与本章的关键词匹配相比，FTS5 支持：
- 词形变换（sort/sorting/sorted 都能匹配）
- 相关性排序（BM25 算法）
- Unicode 全文支持（中日韩等语言）

### 4. 技能执行与改进闭环

```
用户请求
  │
  ▼
hermes: "搜索技能库：{query}"
  │
  ├── 找到技能 → 执行技能
  │               │
  │               ▼
  │           执行过程中如发现更好的方法 →
  │           hermes: "请更新技能 X，加入以下改进：..."
  │
  └── 未找到 → 直接解决 → 提炼新技能
```

---

## agentskills.io 开放标准

hermes-agent 兼容 [agentskills.io](https://agentskills.io) 开放标准——一个跨 Agent 框架的技能共享生态：

```yaml
# agentskills.io 技能格式（.skill.yaml）
name: sort_dataframe_by_column
version: "1.0.0"
description: 对 Pandas DataFrame 按指定列排序
author: community
license: MIT
tags: [pandas, sort, dataframe]
triggers:
  - "sort dataframe"
  - "order by column"
template: |
  import pandas as pd
  df = pd.read_csv("{input_file}")
  df_sorted = df.sort_values(by="{column}", ascending={ascending})
  df_sorted.to_csv("{output_file}", index=False)
```

**与本章的 SkillStore 对比**：

| 维度 | 本章 SkillStore | agentskills.io |
|------|----------------|----------------|
| 存储格式 | JSON | YAML |
| 共享 | 本地私有 | 公开技能市场 |
| 版本管理 | 内部 version 字段 | semver（语义化版本） |
| 触发机制 | 关键词列表 | 结构化 triggers |
| 代码包含 | 提示词模板 | 可执行代码 |

---

## Honcho 用户建模：记住"你是谁"

hermes-agent 集成了 [Honcho](https://github.com/plastic-labs/honcho) 进行用户建模（User Modeling）。这是学习循环的另一维度——不只学习"怎么做任务"，还学习"用户是什么样的人"：

```
Honcho 存储的用户模型（示例）：
  - 工作领域: 数据科学
  - 常用语言: Python, SQL
  - 偏好风格: 简洁代码，不喜欢过度注释
  - 专业水平: 中级，熟悉 Pandas，不熟悉 Spark
  - 沟通风格: 喜欢直接回答，不要废话
```

这些信息让 Agent 的响应越来越个性化，与用户的工作方式越来越匹配。

---

## 技能学习的几种策略对比

### 策略一：立即学习（本章）

每次任务完成后立即合成技能。

| 优点 | 缺点 |
|------|------|
| 简单，延迟低 | 可能学到偶然成功的"错误技能" |
| 经验不会遗失 | 技能库可能膨胀过快 |

### 策略二：延迟学习（延迟合成）

积累 N 次相似经验后才合成一个技能，避免学习噪音。

```python
if len(similar_experiences) >= 3:
    skill = synthesize_from_multiple(similar_experiences)
    store.add(skill)
```

### 策略三：强化学习驱动（hermes 高级版）

只有得到用户正向反馈的经验才触发技能创建：

```python
if user_feedback == "positive" and task_complexity > threshold:
    agent.create_skill_from_last_session()
```

### 策略四：对比学习（试错改进）

对同一类任务尝试多种方法，选择成功率最高的方法合成技能：

```python
for method in candidate_methods:
    result = try_method(task, method)
    scores.append(evaluate(result))
best_method = max(zip(candidate_methods, scores), key=lambda x: x[1])
skill = synthesize(best_method)
```

---

## RL 训练数据：技能作为轨迹

hermes-agent 的另一个创新是将技能学习与强化学习训练结合。Agent 的执行轨迹（trajectory）可以被用来训练下一代模型：

```python
# hermes-agent RL 集成（简化示意）
trajectory = {
    "prompt": task,
    "steps": agent_steps,
    "outcome": result,
    "reward": user_feedback_score,
}
# 发送给 Atropos RL 训练环境
atropos_client.submit_trajectory(trajectory)
```

这形成了一个更大的闭环：
```
Agent 执行 → 收集轨迹 → 训练新模型 → 更好的 Agent → 执行 → ...
```

---

## 延伸学习资源

- [hermes-agent Skills 文档](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills) — 技能系统的完整用户指南
- [agentskills.io](https://agentskills.io) — 跨 Agent 框架的开放技能标准
- [Honcho](https://github.com/plastic-labs/honcho) — 用于 Agent 的用户建模库
- [Mem0](https://github.com/mem0ai/mem0) — 带向量检索的 Agent 记忆层
- [Self-RAG](https://arxiv.org/abs/2310.11511) — 自反思增强生成（学习循环的学术基础）
- [Reflexion](https://arxiv.org/abs/2303.11366) — 通过语言反馈学习的 Agent 框架（学习循环的经典论文）
