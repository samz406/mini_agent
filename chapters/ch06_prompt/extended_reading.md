# 扩展阅读：提示词工程设计 — 主流 Agent 项目实现对比

## 本章回顾

ch06 实现了三个提示词工具：`SystemPromptBuilder`（链式 Builder 模式，按区块组装系统提示词）、`PromptTemplate`（`{variable}` 占位符替换）、`FewShotBuilder`（少样本示例构造）。核心思想：**将提示词当作代码来管理，而不是随意拼接字符串**。

## 为什么要看其他项目？

提示词工程是 Agent 质量最直接的决定因素，但也是最"软"的工程领域——没有编译错误，问题只会以"输出质量变差"的方式体现。生产级项目在提示词管理上投入了大量工程精力，包括：模板引擎（比字符串拼接更强大）、人格文件（将 Agent 个性化为可配置的数据）、动态工具描述（工具自我描述其当前状态）、以及多代理的提示词隔离。这些设计直接影响 Agent 的行为质量。

## 项目简介

| 项目 | 语言 | 提示词工程特色 |
|------|------|--------------|
| mini_agent ch06 | Python | Builder 模式 + PromptTemplate + FewShot |
| nanobot (HKUDS) | Python | Jinja2 模板引擎，SOUL.md 人格文件，Skills 注入提示词 |
| hermes-agent (NousResearch) | Python | Personalities 系统，Context 文件，动态工具描述 |
| openclaw | TypeScript | YAML Skills 提示词区块，SOUL.md，多代理提示词路由 |

## 核心设计对比

### 1. 代码构建器 vs 模板引擎：两种提示词生成方式

**mini_agent** 使用 Python 代码构建提示词：

```python
prompt = (
    SystemPromptBuilder()
    .add_role("你是 Python 助手。")
    .add_tools_section(tool_schemas)
    .add_rules(["优先可读性", "提示边界情况"])
    .build()
)
```

**优点**：无额外依赖，IDE 自动补全，Python 逻辑可直接嵌入（条件区块、循环等）。
**缺点**：提示词的展示形式（最终文字是什么）分散在多个 `add_*` 方法实现中，不如模板文件直观；改提示词需要改 Python 代码，不便于产品经理或非技术角色协作。

**nanobot** 使用 Jinja2 模板引擎：

```jinja2
{# templates/system_prompt.j2 #}
## 角色
{{ role_description }}

{% if tools %}
## 可用工具
{% for tool in tools %}
- **{{ tool.name }}**: {{ tool.description }}
{% endfor %}
{% endif %}

{% if memories %}
## 记忆
{% for memory in memories %}
- {{ memory }}
{% endfor %}
{% endif %}

## 行为规则
{% for rule in rules %}
{{ loop.index }}. {{ rule }}
{% endfor %}
```

```python
# Python 端只需传数据，不关心格式
template = env.get_template("system_prompt.j2")
prompt = template.render(
    role_description="你是专业的 Python 助手",
    tools=tool_schemas,
    memories=recent_memories,
    rules=["优先可读性", "提示边界情况"]
)
```

**Jinja2 的优势**：

1. **关注点分离**：提示词的结构在模板文件中，数据在 Python 中，互不耦合。
2. **非技术角色可参与**：产品经理可以直接编辑 `.j2` 模板文件调整提示词，无需改 Python 代码。
3. **条件逻辑**：`{% if tools %}` 在没有工具时自动省略工具区块。
4. **继承机制**：`{% extends "base.j2" %}` 可以让不同 Agent 共享基础提示词结构，只重写差异部分。

---

### 2. SOUL.md：将 Agent 人格提炼为配置文件

**nanobot** 和 **openclaw** 都支持 `SOUL.md`——一个 Markdown 文件，定义 Agent 的人格、价值观和行为风格：

```markdown
# SOUL.md — Agent 的人格定义

你是一个专注于代码质量的编程助手。你的核心特质：

**风格**：直接、精确、不废话。当用户问一个简单问题时，你给出简单答案，不做无关联系或冗长铺垫。

**价值观**：你相信可读性比聪明技巧更重要。当代码可以用简单方式写时，你不会为了展示技巧而用复杂方式。

**边界**：你拒绝生成以下内容的代码：恶意软件、数据窃取、绕过安全限制。当用户请求可疑操作时，你会直接说明原因并拒绝。

**沟通**：你用"我们"而不是"你"，营造协作感。你会主动问清楚模糊需求，而不是猜测。
```

**为什么这个设计有价值？**

不使用 SOUL.md 时，人格描述散布在代码的各个地方（硬编码在 `system_prompt` 字符串里）。想修改 Agent 的语气，需要搜索代码才能找到正确位置。

使用 SOUL.md 时，人格是**数据**，不是**代码**。你可以为不同场景维护不同版本的 SOUL.md（工作版、轻松版、教学版），切换 Agent 的"人格"就像切换配置文件。

---

### 3. Few-Shot 示例的选择策略

**mini_agent** 的 `FewShotBuilder` 是静态的——你手动添加示例：

```python
builder = FewShotBuilder()
builder.add_example(input="2+2?", output="4")
builder.add_example(input="法国首都？", output="巴黎")
```

这对于固定的任务格式有效，但不灵活。

**hermes-agent** 实现了**动态 Few-Shot 选择**：从历史对话中自动挑选最接近当前查询的示例：

```python
# 语义检索最相关的历史对话作为示例
def get_few_shot_examples(self, current_query: str, n: int = 3) -> list:
    all_successful_pairs = self.memory.get_successful_qa_pairs()
    
    # 用 Embedding 找最语义相关的历史问答对
    query_embedding = self.embedder.embed(current_query)
    scored = [
        (pair, cosine_similarity(query_embedding, pair.embedding))
        for pair in all_successful_pairs
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [pair for pair, _ in scored[:n]]
```

**动态 Few-Shot 的价值**：对于"帮我优化这段 Python 代码"的请求，系统自动找到历史上类似的代码优化示例；对于"帮我写一首诗"的请求，自动找到历史创意写作示例。这比静态示例效果好得多，因为示例的相关性更高。

---

### 4. 多代理场景下的提示词隔离

当系统包含多个 Agent（主 Agent + 子 Agent + 专项 Agent）时，提示词管理变得复杂。

**nanobot 的子代理（Subagent）提示词**：

```python
class SubagentManager:
    def spawn_subagent(self, task: str, agent_type: str) -> SubAgent:
        # 子代理有独立的系统提示词，不继承主代理的人格
        subagent_prompt = self.template_env.get_template(
            f"subagent_{agent_type}.j2"
        ).render(task=task)
        
        return SubAgent(
            system_prompt=subagent_prompt,
            # 子代理通常只有最小化的工具集
            tools=SUBAGENT_TOOLS[agent_type]
        )
```

主代理可能是"友好的通用助手"，但它生成的"代码审查子代理"应该有更严格、更专业的提示词。这种隔离确保不同角色的 Agent 行为清晰且可控。

**openclaw** 的多代理路由：不同的"频道"（Telegram、Discord、本地 CLI）可以有不同的系统提示词，同一个 openclaw 安装在不同渠道呈现不同的"人格"。

---

### 5. 提示词版本管理

**mini_agent** 的提示词在 Python 代码中，受 git 管理，有完整的版本历史——这实际上已经是不错的实践。

**更进一步的做法**（hermes-agent 等项目的经验）：

```
prompts/
├── system/
│   ├── v1.0.md   # 第一版系统提示词
│   ├── v1.1.md   # 修复了 Agent 过于啰嗦的问题
│   └── v2.0.md   # 完整重写，更专注
├── tools/
│   └── calculator.md  # calculator 工具的描述（单独管理）
└── experiments/
    └── friendlier_tone.md  # A/B 测试的实验性提示词
```

将提示词文件从代码中分离出来，使得：
- 非技术角色可以提交 PR 修改提示词
- 更容易做 A/B 测试（修改文件而不是代码）
- 提示词的 git blame 和 diff 更直观

## 设计模式提炼

| 设计维度 | mini_agent | nanobot | hermes-agent | openclaw |
|---------|-----------|---------|-------------|---------|
| 构建方式 | Python Builder | Jinja2 模板引擎 | Python + 配置文件 | YAML + Markdown |
| 人格管理 | 硬编码 | SOUL.md 文件 | Personalities 系统 | SOUL.md 文件 |
| 工具描述 | 静态（定义时固定） | 动态（工具自描述） | 动态 | YAML 定义 |
| Few-Shot | 静态手动 | 静态（通过技能注入） | 动态语义检索 | 技能文件中定义 |
| 多代理隔离 | 无 | 子代理独立提示词 | 无 | 渠道级别路由 |

## 对初学者的启示

1. **Builder 是入门的最佳实践**：相比随意拼接字符串，Builder 模式已经大大提升了可维护性。在掌握 Builder 之前，不需要引入模板引擎的额外复杂性。

2. **提示词是第一等公民的代码**：不要把提示词当作字符串常量对待。给它们起有意义的名字，放在专门的文件或函数中，写注释解释每一段的作用。

3. **SOUL.md 是一个值得学习的模式**：将人格从代码中分离出来，让"Agent 是谁"成为可配置的数据，而不是硬编码的字符串。这在实际产品开发中非常有用。

4. **Few-Shot 质量比数量更重要**：3 个高度相关的示例比 10 个随机示例效果更好。动态选择相关示例是进阶技巧。

5. **模板引擎的门槛不高**：Jinja2 的学习曲线很浅（一两天就能掌握基础），但收益很大。当你的提示词超过 200 字时，认真考虑引入模板引擎。

## 延伸学习资源

- [Jinja2 官方文档](https://jinja.palletsprojects.com) — Python 最流行的模板引擎
- [nanobot/templates/](https://github.com/HKUDS/nanobot/tree/main/nanobot/templates) — 查看 Jinja2 提示词模板实例
- [Few-Shot Prompting 指南](https://www.promptingguide.ai/techniques/fewshot) — 系统性的 Few-Shot 方法论
- [OpenAI 提示词工程指南](https://platform.openai.com/docs/guides/prompt-engineering) — OpenAI 官方最佳实践
