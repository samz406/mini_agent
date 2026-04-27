# 扩展阅读：技能系统（Skill System）设计 — 主流 Agent 项目实现对比

## 本章回顾

ch07 用 `@skill` 类装饰器实现自动注册，`SkillRegistry` 单例管理所有技能，`Skill` 基类要求实现 `get_tools()` 和 `system_prompt_addition`，`SkillManager` 负责加载指定技能并合并工具集和提示词。核心思想：**将 Agent 的能力模块化为独立的、可插拔的单元**。

## 为什么要看其他项目？

mini_agent 的技能系统展示了插件架构的骨架。但生产级项目在此基础上解决了更有趣的问题：技能能不能自动创建（Agent 从经验中学习）？技能能不能自我改进（Agent 优化已有技能）？如何建立技能的社区生态（ClawHub、agentskills.io）？技能和 MCP 服务器的边界在哪里？这些问题揭示了技能系统在整个 Agent 架构中的战略地位。

## 项目简介

| 项目 | 语言 | 技能系统特色 |
|------|------|------------|
| mini_agent ch07 | Python | @skill 装饰器，SkillRegistry，SkillManager |
| nanobot (HKUDS) | Python | TOML 配置技能目录，内置技能 + 用户技能，Dream 自发现 |
| hermes-agent (NousResearch) | Python | Agent 自创建技能，技能自改进，agentskills.io 标准 |
| openclaw | TypeScript | YAML 技能文件，ClawHub 市场，managed 自动更新 |

## 核心设计对比

### 1. Python 类技能 vs 配置文件技能：两种定义方式

**mini_agent** 使用 Python 类：

```python
@skill
class CalculatorSkill(Skill):
    name = "calculator"
    description = "数学计算技能"
    system_prompt_addition = "你可以使用 'calculate' 工具执行数学计算。"
    
    def get_tools(self) -> list:
        return [calculator_tool, ...] 
```

**优点**：可以使用 Python 全部特性（数据库连接、HTTP 客户端、复杂初始化逻辑）；IDE 支持（类型检查、自动补全）；测试框架可直接测试技能类。
**缺点**：非程序员无法创建技能；技能安装需要 Python 导入（安全风险更高）。

**nanobot** 使用 TOML 配置文件：

```toml
# ~/.nanobot/skills/weather/skill.toml

[skill]
name = "weather"
description = "查询天气信息"
version = "1.0.0"

[tools.get_weather]
description = "获取指定城市的当前天气"
type = "python"
module = "weather_skill"  # 指向同目录下的 weather_skill.py
function = "get_weather"

[prompt]
addition = """
你可以使用 get_weather 工具查询任意城市的天气。
查询天气时，请同时告诉用户体感温度和着装建议。
"""
```

**优点**：技能以目录形式存在，可以像安装软件包一样"安装"（复制目录即可）；TOML 文件非技术角色也能编辑；每个技能目录完全自包含（TOML + Python 实现 + 文档）。

**openclaw** 走得更远，把工具实现也放进 YAML：

```yaml
# ~/.openclaw/skills/web-search/skill.yaml
name: web-search
version: 2.1.0
description: 网络搜索技能

tools:
  - name: search_web
    description: 在互联网上搜索信息
    parameters:
      - name: query
        type: string
        description: 搜索关键词
        required: true
    # 工具实现直接内嵌（适合简单工具）
    impl: |
      const response = await fetch(`https://api.search.example.com?q=${encodeURIComponent(query)}`);
      return await response.json();

prompt: |
  你可以使用 search_web 工具搜索互联网上的最新信息。
  对于需要实时信息（新闻、天气、股价）的问题，主动使用此工具。
```

**设计洞察**：三种方式代表了三种权衡——Python 类追求灵活性和工程能力；TOML 目录追求清晰结构和可安装性；全 YAML 追求最低门槛和最大可配置性。

---

### 2. 技能自动创建：Agent 从经验中学习

这是 **hermes-agent** 最独特的设计——**Agent 在完成复杂任务后，会自动创建新技能**：

```python
class LearningLoop:
    """在任务完成后运行，决定是否创建新技能"""
    
    async def after_task_complete(self, task: Task, trajectory: list[dict]) -> None:
        # 1. 评估这次任务是否值得提炼为技能
        should_create = await self.llm.complete([
            {"role": "system", "content": SKILL_CREATION_PROMPT},
            {"role": "user", "content": f"任务：{task.description}\n执行轨迹：{trajectory}"}
        ])
        
        if should_create.content.strip() == "YES":
            # 2. 让 LLM 把轨迹提炼成可复用的技能代码
            skill_code = await self.llm.complete([
                {"role": "system", "content": SKILL_EXTRACTION_PROMPT},
                {"role": "user", "content": f"请将以下执行轨迹提炼为一个可复用的技能：\n{trajectory}"}
            ])
            
            # 3. 保存技能
            await self.skill_registry.save(skill_code)
            logger.info(f"自动创建技能：{skill_code.name}")
```

**这意味着什么？**

Agent 第一次执行"部署 Flask 应用到 AWS EC2"时，需要 15 步工具调用，花了 3 分钟。完成后，Agent 把这个流程提炼为一个 `DeployFlaskToEC2` 技能。下次用户说"帮我把这个 Flask 项目部署到 AWS"，Agent 直接调用这个技能，可能只需要 2 步工具调用，花 30 秒。

**这不只是效率问题，而是 Agent 设计哲学的差异**：mini_agent 的技能是静态的（由程序员预定义）；hermes-agent 的技能是动态的（由 Agent 自己积累）。前者更可控，后者更强大。

---

### 3. 技能自我改进

**hermes-agent** 的技能不只能被创建，还能被**自我改进**：

```python
async def use_skill(self, skill: Skill, task: str) -> str:
    result = await skill.execute(task)
    
    # 执行后，检查技能是否需要改进
    improvement_needed = await self.llm.complete([
        {"role": "user", "content": f"""
技能：{skill.name}
执行结果：{result}
用户反馈：{user_feedback}

这个技能的执行是否有改进空间？如果有，请提供改进后的技能代码。
        """}
    ])
    
    if improvement_needed.suggests_change:
        await self.skill_registry.update(skill.name, improvement_needed.new_code)
```

这形成了一个"使用→改进→使用"的正反馈循环：技能越用越好。

**潜在风险**：自我改进的技能可能往不好的方向"学习"（比如，某个失败的任务导致技能变得更激进）。生产环境中通常需要人类审核技能改动，或限制改进范围（只能修改提示词，不能修改工具调用逻辑）。

---

### 4. 社区生态：ClawHub vs agentskills.io

**openclaw** 的 **ClawHub**：

```bash
# 安装社区技能
claw install web-search
claw install github-copilot
claw install gmail

# 查看已安装技能
claw skills list

# 更新所有技能
claw skills update
```

ClawHub 是一个类似 npm 的技能注册中心。技能由社区贡献，经过审核后发布。Managed 技能（`managed: true`）会自动接收更新，就像软件包的自动安全更新一样。

**hermes-agent** 的 **agentskills.io**：

一个开放标准，任何实现了该标准的平台都可以互相共享技能。标准定义了技能的接口格式、元数据要求和安全检查项。这类似于 Open API / Swagger 对 REST API 的标准化作用——不绑定特定平台，促进生态互通。

**对 mini_agent 的启示**：虽然教学项目不需要技能市场，但理解这个方向很重要——技能系统的终极价值不在于你自己定义了多少技能，而在于是否能接入更大的生态。

---

### 5. 技能 vs 工具 vs MCP 服务器：三个层次

这三个概念经常让初学者困惑，以下是清晰的层次关系：

```
MCP 服务器（最底层协议）
    ↑ 封装
工具（Tool）（单个可调用功能）
    ↑ 组合
技能（Skill）（功能 + 提示词补充 + 生命周期管理）
```

**MCP 服务器**：定义工具的标准协议，运行为独立进程，通过 stdio 或 HTTP 与 Agent 通信。

**工具**：单个原子操作（读文件、搜索网络、执行代码）。可以从 MCP 服务器动态发现，也可以在代码中静态定义。

**技能**：打包了相关工具 + 该工具集的使用指南（提示词补充）+ 可选的初始化/清理逻辑。技能是面向"用例"的（天气技能、代码技能），工具是面向"操作"的（HTTP GET、文件写入）。

## 设计模式提炼

| 设计维度 | mini_agent | nanobot | hermes-agent | openclaw |
|---------|-----------|---------|-------------|---------|
| 技能定义 | Python 类 + @skill | TOML 目录 | Python 类（可自创建） | YAML 文件 |
| 技能注册 | 导入即注册 | 目录扫描 | 导入 + 动态创建 | 目录扫描 |
| 技能自创建 | 无 | 无 | ✅ 从任务轨迹自动提炼 | 无 |
| 技能自改进 | 无 | 无 | ✅ 执行后评估改进 | 无 |
| 社区生态 | 无 | MCP 服务器生态 | agentskills.io | ClawHub |
| 技能更新 | 手动代码更改 | 文件替换 | 自动学习 | managed 自动更新 |

## 对初学者的启示

1. **@skill 装饰器模式是生产可用的**：mini_agent 的插件注册模式（导入即注册）与 Flask、pytest 使用的是完全相同的模式，在实际项目中完全可以使用。

2. **TOML 目录是扩展的下一步**：当你的技能数量超过 5 个时，考虑迁移到"技能目录 + 配置文件"的组织方式，更清晰，也更容易分享。

3. **技能自创建是 Agent 的杀手级功能**：hermes-agent 的自动技能创建让 Agent 随使用积累能力，这是"越用越聪明"的具体实现。理解这个设计，会让你对 Agent 的长期价值有不同的认识。

4. **MCP 是未来的工具接入标准**：如果你只学一个生产技术，学 MCP。它让你的 Agent 能接入整个社区的工具生态，而不是从头构建所有工具。

5. **三层结构是分析 Agent 架构的框架**：MCP 服务器（协议层）→ 工具（功能层）→ 技能（用例层）。用这个框架分析任何 Agent 项目，你很快就能看清它的架构。

## 延伸学习资源

- [nanobot/agent/skills.py](https://github.com/HKUDS/nanobot/blob/main/nanobot/agent/skills.py) — TOML 技能加载实现
- [hermes-agent Skills Hub](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills) — 技能自创建和 Skills Hub 文档
- [ClawHub](https://clawhub.ai) — openclaw 社区技能市场
- [agentskills.io](https://agentskills.io) — 开放技能标准
- [MCP 官方文档](https://modelcontextprotocol.io/introduction) — 工具协议标准
