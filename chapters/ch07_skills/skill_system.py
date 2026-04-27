"""Chapter 7: Skill System — Plugin Architecture.

Teaches: abstract base class for skills, @skill decorator auto-registration,
         SkillRegistry singleton, SkillManager for composing agent capabilities.
"""

from __future__ import annotations

import ast
import operator
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Minimal tool representation (standalone, no dependency on ch03)
# ---------------------------------------------------------------------------

class SimpleTool:
    """Lightweight tool container used within skills."""

    def __init__(self, name: str, description: str, fn: Any) -> None:
        self.name = name
        self.description = description
        self._fn = fn

    def __call__(self, **kwargs: Any) -> Any:
        return self._fn(**kwargs)

    def __repr__(self) -> str:
        return f"SimpleTool(name={self.name!r})"


# ---------------------------------------------------------------------------
# Skill abstract base class
# ---------------------------------------------------------------------------

class Skill(ABC):
    """Abstract base class for agent skills.

    A skill is a domain-specific capability bundle: it contributes tools
    to the agent's tool registry and text to the system prompt.
    """

    name: str = ""
    description: str = ""
    system_prompt_addition: str = ""

    @abstractmethod
    def get_tools(self) -> list[SimpleTool]:
        """Return the tools this skill provides."""
        ...

    def get_prompt_addition(self) -> str:
        """Return text to append to the system prompt."""
        return self.system_prompt_addition


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class SkillRegistry:
    """Singleton registry for all skill classes."""

    def __init__(self) -> None:
        self._skills: dict[str, type[Skill]] = {}

    def register(self, skill_cls: type[Skill]) -> None:
        """Register a skill class by its ``name`` attribute."""
        if not skill_cls.name:
            raise ValueError(f"Skill class {skill_cls.__name__} must define a non-empty 'name'.")
        self._skills[skill_cls.name] = skill_cls

    def get(self, name: str) -> Optional[type[Skill]]:
        """Return a skill class by name, or None."""
        return self._skills.get(name)

    def list_skills(self) -> list[str]:
        """Return names of all registered skills."""
        return list(self._skills.keys())

    def create(self, name: str) -> Skill:
        """Instantiate a registered skill by name."""
        skill_cls = self._skills.get(name)
        if skill_cls is None:
            raise KeyError(f"Skill {name!r} not found. Available: {self.list_skills()}")
        return skill_cls()


SKILL_REGISTRY = SkillRegistry()


def skill(cls: type[Skill]) -> type[Skill]:
    """Class decorator that auto-registers a Skill subclass."""
    SKILL_REGISTRY.register(cls)
    return cls


# ---------------------------------------------------------------------------
# Built-in skills
# ---------------------------------------------------------------------------

def _safe_math_eval(expression: str) -> float:
    """Evaluate a math expression safely using AST."""
    OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.USub: operator.neg,
    }

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            return OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
            return OPS[type(node.op)](_eval(node.operand))
        raise ValueError(f"Disallowed node: {type(node).__name__}")

    tree = ast.parse(expression, mode="eval")
    return _eval(tree.body)


@skill
class CalculatorSkill(Skill):
    """Math computation capability."""

    name = "calculator"
    description = "Provides mathematical calculation tools."
    system_prompt_addition = (
        "You can perform mathematical calculations using the 'calculate' tool. "
        "Use it whenever the user asks for numeric computations."
    )

    def get_tools(self) -> list[SimpleTool]:
        def calculate(expression: str) -> str:
            try:
                result = _safe_math_eval(expression)
                return str(int(result) if result == int(result) else round(result, 10))
            except Exception as exc:
                return f"Error: {exc}"

        return [SimpleTool("calculate", "Evaluate a math expression safely.", calculate)]


@skill
class DateTimeSkill(Skill):
    """Date and time information capability."""

    name = "datetime"
    description = "Provides current date and time information."
    system_prompt_addition = (
        "You can access the current date and time using 'get_time' and 'get_date' tools."
    )

    def get_tools(self) -> list[SimpleTool]:
        def get_time() -> str:
            return datetime.now().strftime("%H:%M:%S")

        def get_date() -> str:
            return datetime.now().strftime("%Y-%m-%d")

        return [
            SimpleTool("get_time", "Return the current local time.", get_time),
            SimpleTool("get_date", "Return the current local date.", get_date),
        ]


# ---------------------------------------------------------------------------
# Skill Manager
# ---------------------------------------------------------------------------

class SkillManager:
    """Loads a set of skills and aggregates their tools and prompt additions."""

    def __init__(self, skill_names: list[str]) -> None:
        self.skill_names = skill_names
        self._loaded: list[Skill] = []

    def load_skills(self) -> None:
        """Instantiate all requested skills from the registry."""
        self._loaded = [SKILL_REGISTRY.create(name) for name in self.skill_names]
        print(f"Loaded {len(self._loaded)} skill(s): {[s.name for s in self._loaded]}")

    def get_all_tools(self) -> list[SimpleTool]:
        """Return the combined tool list from all loaded skills."""
        tools: list[SimpleTool] = []
        for sk in self._loaded:
            tools.extend(sk.get_tools())
        return tools

    def get_system_prompt_additions(self) -> str:
        """Return concatenated system prompt additions from all loaded skills."""
        parts = [sk.get_prompt_addition() for sk in self._loaded if sk.get_prompt_addition()]
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Available Skills ===")
    print(SKILL_REGISTRY.list_skills())

    print("\n=== SkillManager ===")
    manager = SkillManager(skill_names=["calculator", "datetime"])
    manager.load_skills()

    print("\nAll tools:")
    for t in manager.get_all_tools():
        print(f"  • {t.name}: {t.description}")

    print("\nSystem prompt additions:")
    print(manager.get_system_prompt_additions())

    print("\n=== Tool Execution ===")
    tools = {t.name: t for t in manager.get_all_tools()}
    print(f"  calculate('10 * (3 + 4)') = {tools['calculate'](expression='10 * (3 + 4)')}")
    print(f"  get_time() = {tools['get_time']()}")
    print(f"  get_date() = {tools['get_date']()}")
