"""Chapter 6: Prompt Engineering — Builder Pattern.

Teaches: SystemPromptBuilder (fluent API), PromptTemplate, FewShotBuilder.
"""

from __future__ import annotations

import re
import string
from typing import Self


class SystemPromptBuilder:
    """Build structured system prompts with a fluent (chainable) interface.

    Each ``add_*`` method returns ``self`` so calls can be chained.
    Call ``build()`` at the end to get the assembled string.
    """

    def __init__(self) -> None:
        self._sections: list[tuple[str, str]] = []  # (title, content)

    def add_role(self, role_description: str) -> Self:
        """Set the agent's persona / role."""
        self._sections.append(("ROLE", role_description))
        return self

    def add_tools_section(self, tools: list[dict]) -> Self:
        """Document available tools (list of {name, description} dicts or full schemas)."""
        if not tools:
            return self
        lines: list[str] = []
        for t in tools:
            fn = t.get("function", t)
            name = fn.get("name", "unknown")
            desc = fn.get("description", "")
            lines.append(f"- {name}: {desc}")
        self._sections.append(("AVAILABLE TOOLS", "\n".join(lines)))
        return self

    def add_memory_section(self, memories: dict) -> Self:
        """Include key facts from persistent memory."""
        if not memories:
            return self
        lines = [f"- {k}: {v}" for k, v in memories.items()]
        self._sections.append(("REMEMBERED FACTS", "\n".join(lines)))
        return self

    def add_rules(self, rules: list[str]) -> Self:
        """Add a numbered list of rules / guidelines."""
        if not rules:
            return self
        lines = [f"{i + 1}. {rule}" for i, rule in enumerate(rules)]
        self._sections.append(("RULES", "\n".join(lines)))
        return self

    def add_section(self, title: str, content: str) -> Self:
        """Add an arbitrary named section."""
        self._sections.append((title.upper(), content))
        return self

    def build(self) -> str:
        """Assemble all sections into the final system prompt string."""
        parts: list[str] = []
        for title, content in self._sections:
            parts.append(f"## {title}\n{content}")
        return "\n\n".join(parts)


class PromptTemplate:
    """A string template with ``{variable}`` placeholders.

    Uses Python's built-in ``string.Formatter`` for safe substitution.
    """

    def __init__(self, template: str) -> None:
        self.template = template
        self._formatter = string.Formatter()

    def render(self, **kwargs: str) -> str:
        """Substitute all placeholders and return the rendered string."""
        return self._formatter.format(self.template, **kwargs)

    def get_variables(self) -> list[str]:
        """Return a list of unique variable names found in the template."""
        seen: set[str] = set()
        result: list[str] = []
        for _, field_name, _, _ in self._formatter.parse(self.template):
            if field_name and field_name not in seen:
                seen.add(field_name)
                result.append(field_name)
        return result


class FewShotBuilder:
    """Build few-shot example blocks for prompts.

    Add input/output pairs, then call ``build()`` to format them.
    """

    def __init__(self) -> None:
        self._examples: list[tuple[str, str]] = []

    def add_example(self, input: str, output: str) -> Self:
        """Append an input/output example pair."""
        self._examples.append((input, output))
        return self

    def build(self, prefix: str = "") -> str:
        """Format all examples into a string block.

        Args:
            prefix: Optional header line before the examples.
        """
        lines: list[str] = []
        if prefix:
            lines.append(prefix)
        for i, (inp, out) in enumerate(self._examples, start=1):
            lines.append(f"\nExample {i}:")
            lines.append(f"  Input:  {inp}")
            lines.append(f"  Output: {out}")
        return "\n".join(lines)


if __name__ == "__main__":
    print("=== SystemPromptBuilder ===")
    builder = SystemPromptBuilder()
    prompt = (
        builder
        .add_role("You are a helpful Python programming assistant.")
        .add_tools_section([
            {"function": {"name": "run_code", "description": "Execute Python code safely"}},
            {"function": {"name": "search_docs", "description": "Search Python documentation"}},
        ])
        .add_memory_section({"user_name": "Alice", "preferred_lang": "Python"})
        .add_rules([
            "Always explain your reasoning before writing code.",
            "Prefer readable code over clever one-liners.",
            "Mention potential edge cases.",
        ])
        .build()
    )
    print(prompt)

    print("\n=== PromptTemplate ===")
    template = PromptTemplate(
        "Hello {name}! You asked about {topic}. Here is what I know:\n{answer}"
    )
    print(f"Variables: {template.get_variables()}")
    rendered = template.render(name="Bob", topic="recursion", answer="Recursion is a function calling itself.")
    print(rendered)

    print("\n=== FewShotBuilder ===")
    few_shot = (
        FewShotBuilder()
        .add_example("What is 2 + 2?", "4")
        .add_example("What is the capital of France?", "Paris")
        .add_example("Translate 'hello' to Spanish.", "hola")
        .build(prefix="Here are examples of the expected format:")
    )
    print(few_shot)
