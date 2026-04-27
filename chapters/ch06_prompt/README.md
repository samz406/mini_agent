# Chapter 6: Prompt Engineering & Builder Pattern

## What You'll Learn

Prompts are code. This chapter treats them that way: structured, composable, and testable. You'll build three complementary tools for crafting high-quality prompts.

## The Three Tools

### 1. `SystemPromptBuilder` — Fluent Builder Pattern

Complex system prompts are hard to maintain as raw strings. The builder breaks them into named sections with a chainable API:

```python
prompt = (
    SystemPromptBuilder()
    .add_role("You are a helpful coding assistant.")
    .add_tools_section(tool_schemas)
    .add_memory_section({"user_name": "Alice"})
    .add_rules(["Always cite sources", "Be concise"])
    .build()
)
```

Each `add_*` method returns `self`, enabling the chain. `build()` assembles everything into a well-formatted string.

### 2. `PromptTemplate` — Variable Substitution

```python
template = PromptTemplate("Hello {name}, today is {date}.")
result = template.render(name="Alice", date="Monday")
# → "Hello Alice, today is Monday."

template.get_variables()  # → ["name", "date"]
```

### 3. `FewShotBuilder` — Example Construction

Few-shot prompting dramatically improves output quality by showing the model examples:

```python
examples = (
    FewShotBuilder()
    .add_example(input="What is 2+2?", output="4")
    .add_example(input="What is 10/2?", output="5")
    .build(prefix="Here are example Q&A pairs:")
)
```

## Why Structured Prompts?

- **Maintainability**: Change one section without touching others
- **Testability**: Each section can be unit-tested independently
- **Reusability**: Templates can be parameterized and shared
- **Debuggability**: Print individual sections to diagnose issues

## How to Run

```bash
cd chapters/ch06_prompt
python prompt_builder.py
```
