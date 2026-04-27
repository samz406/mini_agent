"""mini_agent.skills.base — Skill abstraction, registry, and decorator."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from mini_agent.tools.base import Tool


class BaseSkill(ABC):
    """Abstract base for all agent skills.

    A skill bundles:
    - A set of tools it contributes to the agent's tool registry.
    - Optional additions to the system prompt.
    """

    name: str = ""
    description: str = ""
    system_prompt_addition: str = ""

    @abstractmethod
    def get_tools(self) -> list["Tool"]:
        """Return the list of tools this skill provides."""
        ...

    def get_prompt_addition(self) -> str:
        """Return text to append to the system prompt (empty string = nothing)."""
        return self.system_prompt_addition


class SkillRegistry:
    """Central registry for skill classes.

    Skills register themselves via the ``@skill`` decorator.
    """

    def __init__(self) -> None:
        self._skills: dict[str, type[BaseSkill]] = {}

    def register(self, skill_cls: type[BaseSkill]) -> None:
        """Register *skill_cls* by its ``name`` attribute."""
        if not skill_cls.name:
            raise ValueError(f"Skill {skill_cls.__name__} must have a non-empty 'name'.")
        self._skills[skill_cls.name] = skill_cls

    def get(self, name: str) -> Optional[type[BaseSkill]]:
        """Return the skill class registered under *name*, or ``None``."""
        return self._skills.get(name)

    def list_skills(self) -> list[str]:
        """Return names of all registered skills."""
        return list(self._skills.keys())

    def create(self, name: str) -> BaseSkill:
        """Instantiate and return the skill registered under *name*."""
        cls = self._skills.get(name)
        if cls is None:
            raise KeyError(f"Skill '{name}' not found. Available: {self.list_skills()}")
        return cls()


SKILL_REGISTRY = SkillRegistry()


def skill(cls: type[BaseSkill]) -> type[BaseSkill]:
    """Class decorator that auto-registers a ``BaseSkill`` subclass."""
    SKILL_REGISTRY.register(cls)
    return cls


def load_skills(names: list[str]) -> list[BaseSkill]:
    """Create and return instances of the named skills from the global registry."""
    return [SKILL_REGISTRY.create(name) for name in names]
