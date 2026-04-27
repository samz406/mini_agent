# Chapter 7: Skill System — Plugin Architecture

## What You'll Learn

This chapter builds a **skill system**: a plugin architecture that lets you compose agents from modular capability units. Each skill bundles tools + prompt additions into a single deployable unit.

## Skills vs Tools

| | Tool | Skill |
|---|---|---|
| What it is | A single function | A bundle of tools + prompt |
| Example | `calculator(expr)` | `CalculatorSkill` |
| Contains | Implementation | Tools + system prompt text |
| Purpose | Atomic action | Domain capability |

## The Plugin Pattern

Skills self-register using the `@skill` class decorator:

```python
@skill
class CalculatorSkill(Skill):
    name = "calculator"
    description = "Math computation skill"
    system_prompt_addition = "You can perform mathematical calculations."
    
    def get_tools(self) -> list:
        return [calculator_tool]
```

No manual registration — importing the module is enough. This is the same pattern used by Flask blueprints, Django apps, and pytest plugins.

## SkillManager: Composing Agents from Skills

```python
manager = SkillManager(skill_names=["calculator", "datetime"])
manager.load_skills()

all_tools = manager.get_all_tools()      # Combined tools from all skills
prompt_additions = manager.get_system_prompt_additions()  # Combined prompt text
```

The agent uses `all_tools` for its tool registry and `prompt_additions` to augment the system prompt. Different agents can have different skill sets.

## Why This Architecture?

- **Composability**: Mix and match skills per use case
- **Isolation**: Skills don't know about each other
- **Extensibility**: Add new skills without modifying existing code
- **Testability**: Each skill can be tested independently

## How to Run

```bash
cd chapters/ch07_skills
python skill_system.py
```
