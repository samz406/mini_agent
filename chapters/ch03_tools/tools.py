"""Chapter 3: Tool System.

Teaches: tool abstraction, decorator pattern, JSON schema generation, tool registry.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from pydantic import BaseModel


class ToolParameter(BaseModel):
    """Describes a single parameter of a tool."""

    name: str
    type: str
    description: str
    required: bool = True


@dataclass
class Tool:
    """A callable tool with metadata for LLM function calling."""

    name: str
    description: str
    parameters: list[ToolParameter]
    function: Callable[..., Any]

    def __call__(self, **kwargs: Any) -> Any:
        return self.function(**kwargs)

    def to_json_schema(self) -> dict:
        """Generate OpenAI-compatible function calling schema."""
        properties: dict[str, dict] = {}
        required_params: list[str] = []

        for param in self.parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description,
            }
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
    """Central registry for all available tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool_instance: Tool) -> None:
        """Add a tool to the registry."""
        self._tools[tool_instance.name] = tool_instance

    def get(self, name: str) -> Optional[Tool]:
        """Retrieve a tool by name, or None if not found."""
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def to_openai_schema(self) -> list[dict]:
        """Export all tools as OpenAI function calling schemas."""
        return [t.to_json_schema() for t in self._tools.values()]


# Module-level default registry
_default_registry = ToolRegistry()


def tool(
    name: str,
    description: str,
    parameters: Optional[list[ToolParameter]] = None,
    registry: Optional[ToolRegistry] = None,
) -> Callable:
    """Decorator factory that wraps a function as a Tool and registers it.

    Usage::

        @tool(name="echo", description="Echo a message",
              parameters=[ToolParameter(name="message", type="string", description="Text to echo")])
        def echo(message: str) -> str:
            return message
    """
    reg = registry or _default_registry

    def decorator(fn: Callable) -> Callable:
        tool_instance = Tool(
            name=name,
            description=description,
            parameters=parameters or [],
            function=fn,
        )
        reg.register(tool_instance)
        fn._tool = tool_instance  # type: ignore[attr-defined]
        return fn

    return decorator
