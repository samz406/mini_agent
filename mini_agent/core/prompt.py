"""mini_agent.core.prompt — System prompt assembly."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from mini_agent.config import AgentConfig


class PromptBuilder:
    """Assemble a structured system prompt from config, tools, and memories.

    Usage::

        builder = PromptBuilder(config)
        builder.set_tools(tool_schemas).set_memories({"user": "Alice"})
        system_msg = builder.get_system_message()
    """

    def __init__(self, config: "AgentConfig") -> None:
        self._config = config
        self._tools: list[dict] = []
        self._memories: dict = {}

    def set_tools(self, tools: list[dict]) -> Self:
        """Store the list of OpenAI tool schemas to include in the prompt."""
        self._tools = tools
        return self

    def set_memories(self, memories: dict) -> Self:
        """Store key-value memories to surface in the prompt."""
        self._memories = memories
        return self

    def build(self) -> str:
        """Assemble and return the full system prompt string."""
        sections: list[str] = []

        # --- Persona ---
        base = self._config.system_prompt or (
            "You are a helpful, knowledgeable AI assistant. "
            "You answer questions accurately and help users accomplish their goals."
        )
        sections.append(f"## ROLE\n{base}")

        # --- Tools ---
        if self._tools:
            lines: list[str] = []
            for t in self._tools:
                fn = t.get("function", t)
                name = fn.get("name", "?")
                desc = fn.get("description", "")
                lines.append(f"- **{name}**: {desc}")
            sections.append("## AVAILABLE TOOLS\n" + "\n".join(lines))

        # --- Memory ---
        if self._memories:
            lines2 = [f"- {k}: {v}" for k, v in self._memories.items()]
            sections.append("## REMEMBERED FACTS\n" + "\n".join(lines2))

        # --- Rules (always present) ---
        rules = [
            "When you need to use a tool, use it via the function calling mechanism — do not describe what you would do, just call it.",
            "If a tool call fails, explain the error to the user and suggest an alternative.",
            "Be concise. Use bullet points for lists. Use code blocks for code.",
            "If you don't know something, say so rather than guessing.",
        ]
        sections.append("## RULES\n" + "\n".join(f"{i + 1}. {r}" for i, r in enumerate(rules)))

        return "\n\n".join(sections)

    def get_system_message(self) -> dict:
        """Return the system prompt as an OpenAI message dict."""
        return {"role": "system", "content": self.build()}
