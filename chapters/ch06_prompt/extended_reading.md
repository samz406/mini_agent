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
| hermes-agent (NousResearch) | Python | SOUL.md 人格文件，Personalities 系统，Context 文件 |
| claude-code (samz406) | TypeScript | 多层级覆盖系统，Skills + Plugins 动态注入 |

---

## 提示词组装详解：三大 Agent 实现拆解

> 本节深入研究三个生产级 Agent 的提示词组装代码，逐层拆解每个 Agent 最终发给模型的系统提示词是如何一块一块拼出来的。

### 什么是"提示词组装"？

提示词组装（Prompt Assembly）是指在每次调用 LLM 之前，将多个来源的文本片段合并成一个完整系统提示词的过程。与简单的字符串拼接不同，生产级 Agent 的组装过程通常涉及：

- **多个独立来源**：人格文件、工具描述、记忆摘要、用户上下文、运行时信息……
- **优先级与覆盖逻辑**：某些来源可以替换其他来源（例如自定义提示词替换默认提示词）
- **条件性包含**：只有在特定条件成立时才包含某个区块（例如只有存在可用技能时才包含技能列表）
- **每轮动态注入**：部分信息（当前时间、会话 ID）在每次用户消息时重新注入，而非固定在系统提示词中

---

### 1. Claude Code 的提示词组装（TypeScript）

**代码仓库**：[samz406/claude-code](https://github.com/samz406/claude-code)  
**核心文件**：`src/utils/systemPrompt.ts`、`src/utils/queryContext.ts`、`src/QueryEngine.ts`

#### 1.1 组装入口：`submitMessage()`

每次用户发送消息时，`QueryEngine.submitMessage()` 被调用，它触发完整的提示词组装流程：

```typescript
// src/QueryEngine.ts（简化）
async *submitMessage(prompt, options) {
  // ① 获取系统提示词的各个组成部分
  const { defaultSystemPrompt, userContext, systemContext } =
    await fetchSystemPromptParts({
      tools,
      mainLoopModel,
      additionalWorkingDirectories,
      mcpClients,
      customSystemPrompt,  // 用户通过 --system-prompt 传入的自定义提示词
    })

  // ② 可选：注入内存机制提示词
  //    仅在 SDK 模式下且设置了 CLAUDE_COWORK_MEMORY_PATH_OVERRIDE 时启用
  const memoryMechanicsPrompt =
    customPrompt !== undefined && hasAutoMemPathOverride()
      ? await loadMemoryPrompt()
      : null

  // ③ 将所有部分拼装成最终系统提示词
  const systemPrompt = asSystemPrompt([
    ...(customPrompt !== undefined ? [customPrompt] : defaultSystemPrompt),
    ...(memoryMechanicsPrompt ? [memoryMechanicsPrompt] : []),
    ...(appendSystemPrompt ? [appendSystemPrompt] : []),
  ])

  // ④ 异步加载 Skills 和 Plugins（并行执行）
  const [skills, { enabled: enabledPlugins }] = await Promise.all([
    getSlashCommandToolSkills(getCwd()),
    loadAllPluginsCacheOnly(),
  ])

  // ⑤ 构建最终的 system init 消息（含工具列表）
  yield buildSystemInitMessage({ tools, skills, plugins: enabledPlugins, ... })
}
```

#### 1.2 多层级覆盖系统：`buildEffectiveSystemPrompt()`

Claude Code 最精妙的设计在于其**多层级提示词覆盖系统**。`src/utils/systemPrompt.ts` 中的 `buildEffectiveSystemPrompt()` 实现了严格的优先级：

```typescript
// src/utils/systemPrompt.ts（简化，保留核心优先级逻辑）
export function buildEffectiveSystemPrompt({
  mainThreadAgentDefinition,   // 当前激活的 Agent 定义（可选）
  toolUseContext,
  customSystemPrompt,          // --system-prompt 传入的自定义提示词
  defaultSystemPrompt,         // 从 constants/prompts.ts 构建的默认提示词
  appendSystemPrompt,          // --append-system-prompt 永远追加在末尾
  overrideSystemPrompt,        // 最高优先级覆盖（循环模式等）
}): SystemPrompt {

  // 优先级 0：覆盖提示词（最高优先级，直接替换一切）
  if (overrideSystemPrompt) {
    return asSystemPrompt([overrideSystemPrompt])
    // 注意：appendSystemPrompt 在此模式下也被忽略
  }

  // 优先级 1：协调者模式（多代理编排时主 Agent 使用专用提示词）
  if (isCoordinatorMode() && !mainThreadAgentDefinition) {
    return asSystemPrompt([
      getCoordinatorSystemPrompt(),
      ...(appendSystemPrompt ? [appendSystemPrompt] : []),
    ])
  }

  // 优先级 2：Agent 系统提示词（特定 Agent 激活时）
  const agentSystemPrompt = mainThreadAgentDefinition
    ? mainThreadAgentDefinition.getSystemPrompt()
    : undefined

  // 在"主动模式"（Proactive/Kairos）下，Agent 提示词叠加在默认提示词之上
  if (agentSystemPrompt && isProactiveActive()) {
    return asSystemPrompt([
      ...defaultSystemPrompt,
      `\n# Custom Agent Instructions\n${agentSystemPrompt}`,
      ...(appendSystemPrompt ? [appendSystemPrompt] : []),
    ])
  }

  // 其他情况：优先级 3（agentPrompt）> 4（customPrompt）> 5（defaultPrompt）
  return asSystemPrompt([
    ...(agentSystemPrompt
      ? [agentSystemPrompt]          // Agent 提示词（替换默认）
      : customSystemPrompt
        ? [customSystemPrompt]       // 用户自定义提示词（替换默认）
        : defaultSystemPrompt),      // 默认提示词（兜底）
    ...(appendSystemPrompt ? [appendSystemPrompt] : []),
  ])
}
```

#### 1.3 默认系统提示词的来源

`defaultSystemPrompt` 来自 `getSystemPrompt()` 函数（`src/constants/prompts.ts`，约 54KB 的 TypeScript 文件），这是 Claude Code 的核心行为定义，硬编码在代码中，内容包括：

- Claude 的角色定位（编程助手，直接、高效）
- 工具使用规则（何时用 `Read`、`Write`、`Bash` 等）
- 代码质量要求
- 安全和权限限制
- 工作目录上下文

#### 1.4 组装结果示意图

```
┌─────────────────────────────────────────────────┐
│              最终系统提示词（按优先级）               │
├─────────────────────────────────────────────────┤
│  [Block 1] 主体部分（四选一，互斥）：               │
│    - overrideSystemPrompt（最高优先级）             │
│    - coordinatorSystemPrompt（协调者模式）          │
│    - agentSystemPrompt（特定 Agent）               │
│    - customSystemPrompt 或 defaultSystemPrompt    │
├─────────────────────────────────────────────────┤
│  [Block 2] memoryMechanicsPrompt（可选）           │
│    - 仅在 SDK 模式 + 内存路径覆盖时注入              │
├─────────────────────────────────────────────────┤
│  [Block 3] appendSystemPrompt（可选，永远追加）     │
│    - 通过 --append-system-prompt 指定              │
├─────────────────────────────────────────────────┤
│  + tools 列表（通过 function calling 结构传入）     │
│  + skills（斜杠命令技能）                          │
│  + plugins（启用的插件）                           │
└─────────────────────────────────────────────────┘
```

---

### 2. Nanobot 的提示词组装（Python + Jinja2）

**代码仓库**：[HKUDS/nanobot](https://github.com/HKUDS/nanobot)  
**核心文件**：`nanobot/agent/context.py`、`nanobot/templates/agent/identity.md`

#### 2.1 组装入口：`ContextBuilder`

Nanobot 使用 `ContextBuilder` 类统一管理提示词组装，每次用户发消息时调用 `build_messages()`：

```python
# nanobot/agent/context.py
class ContextBuilder:
    # 启动时必须加载的"引导文件"列表
    BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md"]

    def build_system_prompt(self, skill_names=None, channel=None) -> str:
        """将所有部分拼装成完整的系统提示词。"""
        parts = []

        # ① 核心身份区块（通过 Jinja2 模板渲染）
        parts.append(self._get_identity(channel=channel))

        # ② 引导文件区块（从工作目录读取，用户可自定义）
        bootstrap = self._load_bootstrap_files()
        if bootstrap:
            parts.append(bootstrap)

        # ③ 记忆区块（跨会话的持久化记忆，非默认模板才注入）
        memory = self.memory.get_memory_context()
        if memory and not self._is_template_content(memory, "memory/MEMORY.md"):
            parts.append(f"# Memory\n\n{memory}")

        # ④ "永远激活"技能区块（配置为 always-on 的技能全文注入）
        always_skills = self.skills.get_always_skills()
        if always_skills:
            always_content = self.skills.load_skills_for_context(always_skills)
            if always_content:
                parts.append(f"# Active Skills\n\n{always_content}")

        # ⑤ 技能目录区块（其余可用技能的摘要，按需读取）
        skills_summary = self.skills.build_skills_summary(exclude=set(always_skills))
        if skills_summary:
            parts.append(render_template("agent/skills_section.md",
                                         skills_summary=skills_summary))

        # ⑥ 最近历史区块（最多 50 条，最多 32KB）
        entries = self.memory.read_unprocessed_history(
            since_cursor=self.memory.get_last_dream_cursor()
        )
        if entries:
            capped = entries[-50:]
            history_text = "\n".join(
                f"- [{e['timestamp']}] {e['content']}" for e in capped
            )
            parts.append("# Recent History\n\n" + history_text[:32_000])

        # 用 "---" 分隔符连接所有区块
        return "\n\n---\n\n".join(parts)
```

#### 2.2 核心身份区块：Jinja2 模板

身份区块由 `nanobot/templates/agent/identity.md` 渲染而来，这是真正体现 Jinja2 价值的地方——同一份模板根据运行时参数输出不同内容：

```jinja2
{# nanobot/templates/agent/identity.md #}
## Runtime
{{ runtime }}

## Workspace
Your workspace is at: {{ workspace_path }}
- Long-term memory: {{ workspace_path }}/memory/MEMORY.md
- History log: {{ workspace_path }}/memory/history.jsonl

{{ platform_policy }}

{# 根据平台动态切换格式提示 #}
{% if channel == 'telegram' or channel == 'qq' or channel == 'discord' %}
## Format Hint
This conversation is on a messaging app. Use short paragraphs. Avoid large headings.
{% elif channel == 'whatsapp' or channel == 'sms' %}
## Format Hint
This conversation is on a text messaging platform. Use plain text only.
{% elif channel == 'cli' %}
## Format Hint
Output is rendered in a terminal. Avoid markdown headings and tables.
{% endif %}

## Search & Discovery
- Prefer built-in `grep` / `glob` over `exec` for workspace search.
```

渲染调用：

```python
def _get_identity(self, channel: str | None = None) -> str:
    workspace_path = str(self.workspace.expanduser().resolve())
    system = platform.system()
    runtime = f"{'macOS' if system == 'Darwin' else system} {platform.machine()}, Python {platform.python_version()}"

    return render_template(
        "agent/identity.md",
        workspace_path=workspace_path,
        runtime=runtime,
        platform_policy=render_template("agent/platform_policy.md", system=system),
        channel=channel or "",
    )
```

#### 2.3 引导文件：工作目录中的可覆盖配置

```python
def _load_bootstrap_files(self) -> str:
    """加载工作目录中的引导文件（用户可自定义覆盖）。"""
    parts = []
    for filename in ["AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md"]:
        file_path = self.workspace / filename
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            parts.append(f"## {filename}\n\n{content}")
    return "\n\n".join(parts) if parts else ""
```

默认 `SOUL.md` 内容（`nanobot/templates/SOUL.md`）：

```markdown
# Soul
I am nanobot 🐈, a personal AI assistant.

## Core Principles
- Solve by doing, not by describing what I would do.
- Keep responses short unless depth is asked for.
- Say what I know, flag what I don't, and never fake confidence.

## Execution Rules
- Act immediately on single-step tasks — never end a turn with just a plan.
- Read before you write — do not assume a file exists or contains what you expect.
```

#### 2.4 每轮动态注入：运行时上下文

系统提示词是**一次性构建**的，但每次用户发消息时，会在用户消息**前面**拼入一段运行时元数据：

```python
def build_messages(self, history, current_message, ...) -> list:
    # 构建运行时上下文（每次都刷新）
    runtime_ctx = self._build_runtime_context(channel, chat_id, self.timezone, session_summary)
    user_content = self._build_user_content(current_message, media)

    # 将运行时上下文和用户消息合并进同一个 user 消息
    merged = f"{runtime_ctx}\n\n{user_content}"

    messages = [
        {"role": "system", "content": self.build_system_prompt(skill_names, channel)},
        *history,
        {"role": "user", "content": merged},
    ]
    return messages

@staticmethod
def _build_runtime_context(channel, chat_id, timezone, session_summary=None) -> str:
    """构建每轮注入的运行时元数据块。"""
    lines = [f"Current Time: {current_time_str(timezone)}"]
    if channel and chat_id:
        lines += [f"Channel: {channel}", f"Chat ID: {chat_id}"]
    if session_summary:
        lines += ["", "[Resumed Session]", session_summary]

    # 明确标注这是元数据，不是指令，防止模型将其视为用户指令
    return (
        "[Runtime Context — metadata only, not instructions]\n"
        + "\n".join(lines)
        + "\n[/Runtime Context]"
    )
```

#### 2.5 子代理提示词：独立 Jinja2 模板

子代理（subagent）使用**完全独立**的系统提示词（`templates/agent/subagent_system.md`），不继承主代理的人格和记忆，只关注任务本身：

```jinja2
{# nanobot/templates/agent/subagent_system.md #}
# Subagent

{{ time_ctx }}

You are a subagent spawned by the main agent to complete a specific task.
Stay focused on the assigned task. Your final response will be reported
back to the main agent.

## Workspace
{{ workspace }}
{% if skills_summary %}
## Skills
Read SKILL.md with read_file to use a skill.
{{ skills_summary }}
{% endif %}
```

#### 2.6 组装结果示意图

```
┌─────────────────────────────────────────────────┐
│              系统提示词（system 消息）               │
├─────────────────────────────────────────────────┤
│  [Part 1] identity.md（Jinja2 渲染）              │
│    - 运行时信息（OS、Python 版本）                  │
│    - 工作目录路径                                  │
│    - 平台策略（条件分支）                           │
│    - 格式提示（按 channel 动态输出）                 │
├─────────────────────────────────────────────────┤
│  [Part 2] Bootstrap 文件（工作目录中读取，可覆盖）    │
│    - AGENTS.md（任务特定指令）                     │
│    - SOUL.md（人格 / 核心原则）                    │
│    - USER.md（用户画像）                           │
│    - TOOLS.md（工具使用注意事项）                   │
├─────────────────────────────────────────────────┤
│  [Part 3] Memory（跨会话记忆，可选）                │
├─────────────────────────────────────────────────┤
│  [Part 4] Active Skills（永远激活的技能全文，可选）  │
├─────────────────────────────────────────────────┤
│  [Part 5] Skills 目录摘要（可选）                  │
├─────────────────────────────────────────────────┤
│  [Part 6] Recent History（最近 50 条，可选）        │
└─────────────────────────────────────────────────┘
          各部分之间用 "\n\n---\n\n" 分隔

┌─────────────────────────────────────────────────┐
│              每轮 user 消息（动态注入）              │
├─────────────────────────────────────────────────┤
│  [Runtime Context 标签块]                        │
│    - 当前时间                                     │
│    - Channel + Chat ID                           │
│    - 会话摘要（恢复会话时）                         │
├─────────────────────────────────────────────────┤
│  [用户实际输入的文本 / 图片]                        │
└─────────────────────────────────────────────────┘
```

---

### 3. Hermes-Agent 的提示词组装（Python）

**代码仓库**：[NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)  
**核心文件**：`hermes_cli/default_soul.py`、`hermes_cli/main.py`

#### 3.1 人格基础：SOUL.md 文件

Hermes-Agent 的提示词组装以 SOUL.md 为出发点。在 `~/.hermes/SOUL.md` 不存在时，系统使用 `default_soul.py` 中的默认人格：

```python
# hermes_cli/default_soul.py
DEFAULT_SOUL_MD = (
    "You are Hermes Agent, an intelligent AI assistant created by Nous Research. "
    "You are helpful, knowledgeable, and direct. You assist users with a wide "
    "range of tasks including answering questions, writing and editing code, "
    "analyzing information, creative work, and executing actions via your tools. "
    "You communicate clearly, admit uncertainty when appropriate, and prioritize "
    "being genuinely useful over being verbose unless otherwise directed below. "
    "Be targeted and efficient in your exploration and investigations."
)
```

用户可以在 `~/.hermes/SOUL.md` 中完全替换这段文本——这是定义 Agent 人格的首选方式。

#### 3.2 系统提示词组装的各个层次

Hermes-Agent 的系统提示词由以下层次顺序组装（核心逻辑分布在 `hermes_cli/main.py` 的会话初始化代码中）：

```
系统提示词组装顺序
=================
① SOUL.md 内容
   └─ 读取 ~/.hermes/SOUL.md（用户自定义人格）
   └─ 若不存在则使用 DEFAULT_SOUL_MD
   └─ 若通过 /personality 切换了人格则使用对应人格文件

② Personality 系统（可选）
   └─ /personality <name> 命令切换到预设人格
   └─ 人格文件覆盖 SOUL.md 中的角色描述

③ Memory 注入（可选）
   └─ ~/.hermes/memory/MEMORY.md 内容
   └─ ~/.hermes/memory/USER.md 用户画像
   └─ 自动由 Dream 后台进程维护和压缩

④ Context 文件注入（可选）
   └─ 项目级 AGENTS.md（当前目录或父目录中）
   └─ 定义项目特定的行为规则和工具偏好

⑤ Skills 区块（可选）
   └─ 已激活技能的系统提示词片段追加到末尾
   └─ 每个技能通过 SKILL.md 文件自描述

⑥ 工具描述（通过 function calling 结构传入）
   └─ 40+ 内置工具
   └─ MCP 服务器动态发现的工具
```

#### 3.3 Personalities 系统：多人格切换

Hermes-Agent 支持通过 `/personality` 命令在运行时切换 Agent 的人格，无需重启。人格文件通常存放在 `~/.hermes/personalities/` 目录下，每个人格是一份独立的 Markdown 文件：

```bash
# 使用示例
/personality coder         # 切换到编程专家人格
/personality assistant     # 切换回通用助手人格
/personality researcher    # 切换到研究员人格
```

每次切换后，系统在下一轮请求时用新人格文件的内容替换系统提示词中的 SOUL 区块，其余部分（记忆、技能、工具）保持不变。

#### 3.4 跨平台：同一组装逻辑，不同渠道

Hermes-Agent 支持 CLI、Telegram、Discord、WhatsApp、Slack 等多个平台。不同平台的**核心系统提示词相同**（SOUL + 记忆 + 技能），只在消息发送格式上有差异。这与 Nanobot 的渠道感知格式提示设计理念相同，但实现层面不同：

- Nanobot 在 Jinja2 模板中使用 `{% if channel == 'telegram' %}` 动态插入格式提示
- Hermes-Agent 通过网关（Gateway）层做消息格式转换，系统提示词层保持平台无关

#### 3.5 Memory Dream 机制：自动维护系统提示词中的记忆

Hermes-Agent 的记忆注入最大的特点是**自动维护**。系统有一个"Dream"后台进程，定期：

1. 读取对话历史
2. 调用 LLM 提取值得记住的关键信息
3. 压缩并写入 MEMORY.md

这意味着注入系统提示词的记忆区块是**经过 LLM 筛选和整理**的，而不是原始的对话记录。

```
[Dream 机制流程]
对话历史 → LLM 分析 → 提取关键信息 → 写入 MEMORY.md
                                              ↓
                         下次会话系统提示词 ← 读取 MEMORY.md
```

#### 3.6 组装结果示意图

```
┌─────────────────────────────────────────────────┐
│              系统提示词（system 消息）               │
├─────────────────────────────────────────────────┤
│  [Part 1] SOUL / Personality                    │
│    - ~/.hermes/SOUL.md（用户自定义）               │
│    - 或 DEFAULT_SOUL_MD（默认兜底）                │
│    - 或 personalities/<name>.md（切换人格时）       │
├─────────────────────────────────────────────────┤
│  [Part 2] Memory（可选，Dream 自动维护）           │
│    - ~/.hermes/memory/MEMORY.md                 │
│    - ~/.hermes/memory/USER.md                   │
├─────────────────────────────────────────────────┤
│  [Part 3] Context Files（可选，项目级）            │
│    - 当前目录 / 父目录中的 AGENTS.md              │
├─────────────────────────────────────────────────┤
│  [Part 4] Active Skills（可选）                  │
│    - 每个激活技能的系统提示词片段                   │
├─────────────────────────────────────────────────┤
│  + 工具列表（function calling 结构）              │
│  + MCP 工具（动态发现）                           │
└─────────────────────────────────────────────────┘
```

---

### 4. 三大 Agent 提示词组装对比总结

#### 4.1 相同点

| 维度 | Claude Code | Nanobot | Hermes-Agent |
|------|-------------|---------|--------------|
| **人格文件化** | 默认提示词在代码中，可通过 customSystemPrompt 替换 | SOUL.md 文件（工作目录级） | SOUL.md 文件（用户主目录级） |
| **工具通过 FC 传递** | ✅ function calling 结构 | ✅ function calling 结构 | ✅ function calling 结构 |
| **记忆注入** | ✅ 通过 memoryMechanicsPrompt | ✅ Memory 区块 | ✅ Dream 机制 |
| **技能/插件系统** | ✅ Skills + Plugins | ✅ Skills（按需/永久激活） | ✅ Skills（agentskills.io 标准） |
| **条件性区块** | ✅ 多层覆盖条件判断 | ✅ 每个 Part 有存在性检查 | ✅ 各区块按配置开关 |
| **多代理支持** | ✅ 子代理/协调者专用提示词 | ✅ subagent_system.md 模板 | ✅ 子代理 RPC 调用 |

**三者共同的核心设计原则**：
1. **系统提示词是数据，不是魔法**：所有内容都有明确的来源，可以追踪和修改
2. **分区管理**：人格、记忆、工具、规则各自独立管理，互不耦合
3. **渐进增强**：有一个稳定的"最小系统提示词"，其余功能通过叠加区块来增强
4. **工具描述与系统提示词分离**：工具通过 function calling 结构传递，不内嵌在提示词文本中

#### 4.2 不同点

| 维度 | Claude Code | Nanobot | Hermes-Agent |
|------|-------------|---------|--------------|
| **语言** | TypeScript | Python | Python |
| **提示词主体存放** | 硬编码在 TypeScript 代码中（`constants/prompts.ts`，54KB） | Jinja2 模板文件（`templates/`） | SOUL.md 文件（纯文本） |
| **覆盖机制复杂度** | 高：5 个优先级层，互斥且有顺序 | 低：各 Part 独立叠加，无优先级冲突 | 中：人格文件可切换，其余固定叠加 |
| **运行时信息注入** | 不注入（环境信息通过工具调用获取） | 每轮注入：当前时间、Channel、Chat ID | 不注入固定元数据 |
| **平台适配方式** | 无（纯代码工具，单一平台） | Jinja2 模板中条件分支（channel 参数） | 网关层消息格式转换 |
| **人格切换** | 运行时通过 `--system-prompt` 替换 | 工作目录中替换 SOUL.md 文件 | `/personality` 命令热切换 |
| **记忆维护** | 依赖外部（SDK 调用者负责） | Dream 处理写入，ContextBuilder 读取注入 | Dream 后台进程自动维护 |
| **子代理提示词隔离** | ✅ 协调者模式专用提示词 | ✅ 完全独立的 subagent_system.md 模板 | ✅ 子代理 RPC 调用，隔离 context |
| **提示词可观测性** | 低（硬编码在大文件中） | 高（模板文件直接可读） | 中（SOUL.md 可读，其余分散） |

#### 4.3 设计哲学差异

**Claude Code** 的设计重点是**灵活性和可扩展性**：通过多层覆盖系统，任何调用者都可以在不修改代码的情况下定制 Agent 的行为。代价是组装逻辑相对复杂，提示词内容对非工程师不透明。

**Nanobot** 的设计重点是**关注点分离和透明度**：提示词的结构（模板）和内容（配置文件）完全分离，工作目录中的 Markdown 文件对用户完全可见。任何人都可以通过直接编辑文件来改变 Agent 的行为，无需理解代码。

**Hermes-Agent** 的设计重点是**个性化和长期关系**：以用户为中心，SOUL.md 定义 Agent 的"灵魂"，Dream 机制让 Agent 持续学习用户的偏好和历史，技能系统让能力可以动态增长。提示词不只是技术配置，而是 Agent 与用户长期关系的载体。

#### 4.4 对 mini_agent 的启发

从这三个项目的组装方式，可以提炼出对 mini_agent `ch06` 的进化路径：

| 当前状态 | 进化方向 |
|---------|---------|
| `SystemPromptBuilder` Python 代码构建 | 可引入 Jinja2 模板，实现结构与内容分离 |
| 人格硬编码在 `add_role()` 参数中 | 可提取为 `SOUL.md` 文件，支持运行时切换 |
| 无覆盖机制 | 可参考 Claude Code 的优先级系统 |
| 无运行时信息注入 | 可参考 Nanobot 的 Runtime Context 标签块 |
| 记忆手动管理 | 可参考 Hermes-Agent 的 Dream 机制 |

---

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
