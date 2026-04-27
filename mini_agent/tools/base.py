"""mini_agent.tools.base — Tool abstraction, registry, and decorator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from pydantic import BaseModel


class ToolParameter(BaseModel):
    """Describes a single parameter accepted by a tool."""

    name: str
    type: str
    description: str
    required: bool = True
    enum: Optional[list] = None


class ToolResult(BaseModel):
    """Standardised return value from a tool execution."""

    success: bool
    result: str
    error: Optional[str] = None


@dataclass
class Tool:
    """A callable tool with metadata for LLM function calling.

    Provides:
    - ``execute(**kwargs)`` — safe wrapper that returns a ``ToolResult``
    - ``to_openai_schema()`` — OpenAI function calling JSON schema
    """

    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)
    function: Callable[..., Any] = field(default=lambda: None)
    returns_description: str = ""

    def execute(self, **kwargs: Any) -> ToolResult:
        """Call the underlying function and wrap the result in ``ToolResult``."""
        try:
            raw = self.function(**kwargs)
            return ToolResult(success=True, result=str(raw) if raw is not None else "")
        except Exception as exc:
            return ToolResult(success=False, result="", error=str(exc))

    def to_openai_schema(self) -> dict:
        """Generate an OpenAI-compatible function calling schema dict."""
        properties: dict[str, dict] = {}
        required_params: list[str] = []

        for param in self.parameters:
            prop: dict = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            properties[param.name] = prop
            if param.required:
                required_params.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required_params,
                },
            },
        }


class ToolRegistry:
    """Central store for all available tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool_instance: Tool) -> None:
        """Add *tool_instance* to the registry."""
        self._tools[tool_instance.name] = tool_instance

    def get(self, name: str) -> Optional[Tool]:
        """Return the tool with *name*, or ``None``."""
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def to_openai_schemas(self) -> list[dict]:
        """Return all tools formatted as OpenAI function calling schemas."""
        return [t.to_openai_schema() for t in self._tools.values()]


# Module-level singleton registry — all @tool decorated functions register here.
GLOBAL_REGISTRY = ToolRegistry()


def tool(
    name: str,
    description: str,
    parameters: Optional[list[ToolParameter]] = None,
    returns: str = "",
    registry: Optional[ToolRegistry] = None,
) -> Callable:
    """Decorator factory: register a function as a Tool in the global registry.

    Usage::

        @tool(name="echo", description="Echo a message back",
              parameters=[ToolParameter(name="message", type="string", description="Text")])
        def echo(message: str) -> str:
            return message
    """
    reg = registry if registry is not None else GLOBAL_REGISTRY

    def decorator(fn: Callable) -> Callable:
        tool_instance = Tool(
            name=name,
            description=description,
            parameters=parameters or [],
            function=fn,
            returns_description=returns,
        )
        reg.register(tool_instance)
        fn._tool = tool_instance  # type: ignore[attr-defined]
        return fn

    return decorator
