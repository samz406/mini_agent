# 第七章：技能系统（插件架构）

## 你将学到什么

本章构建一个**技能系统**：一种插件架构，让你把 Agent 的能力拆分成独立的、可插拔的模块。每个技能（Skill）将工具 + 提示词补充打包成一个可部署单元。

> 📖 学完本章后，可以阅读 `extended_reading.md`，了解 nanobot 的 TOML 配置技能、hermes-agent 的技能自创建与自改进、openclaw 的 ClawHub 技能市场等进阶设计。

## 技能 vs 工具

| | 工具（Tool） | 技能（Skill） |
|---|---|---|
| 是什么 | 单个函数 | 工具集合 + 提示词补充 |
| 例子 | `calculator(expr)` | `CalculatorSkill` |
| 包含内容 | 执行逻辑 | 工具列表 + 系统提示词文字 |
| 目的 | 原子操作 | 领域能力（可理解、可开关、可组合） |

**通俗理解**：工具是"一把锤子"，技能是"装修工具箱"（包含锤子、螺丝刀、卷尺，以及说明书）。

## 插件注册模式

技能通过 `@skill` 类装饰器实现**自动注册**：

```python
@skill
class CalculatorSkill(Skill):
    name = "calculator"
    description = "数学计算技能"
    system_prompt_addition = "你可以使用 'calculate' 工具执行数学计算。需要数值计算时请使用它。"
    
    def get_tools(self) -> list:
        return [calculator_tool]
```

**自动注册的工作原理**：当 Python 导入（import）这个模块时，类定义被执行，`@skill` 装饰器立即把这个类注册到 `SkillRegistry` 中。你不需要写任何注册代码——导入模块本身就完成了注册。

这和 Flask blueprints、Django apps、pytest 插件是同一个模式。

## SkillManager：从技能组装 Agent

```python
manager = SkillManager(skill_names=["calculator", "datetime"])
manager.load_skills()

# 获取所有技能提供的工具（合并列表）
all_tools = manager.get_all_tools()

# 获取所有技能的提示词补充（拼接字符串）
prompt_additions = manager.get_system_prompt_additions()

# 组装 Agent：不同的技能组合 → 不同能力的 Agent
```

不同的 Agent 可以加载不同的技能组合，实现能力的灵活定制。

## 为什么需要这种架构？

| 优点 | 解释 |
|------|------|
| **可组合** | 为每种用途选择不同的技能组合 |
| **隔离性** | 技能之间互不依赖，不会相互干扰 |
| **可扩展** | 添加新技能不需要修改现有代码 |
| **可测试** | 每个技能可以独立测试 |

**对比无技能系统的情况**：如果所有工具都直接注册到 Agent，随着工具增多，Agent 会变得越来越难以管理，不同场景下的工具组合也无法灵活调整。

## 如何运行

```bash
cd chapters/ch07_skills
python skill_system.py
```

你将看到：
1. 所有可用技能的列表（通过扫描技能目录发现）
2. `SkillManager` 加载两个技能后的工具总列表
3. 两个技能各自的提示词补充文字
4. 各工具的实际执行结果（计算 10×7、获取时间和日期）
