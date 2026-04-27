"""mini_agent.skills — Skill system exports."""

from mini_agent.skills.base import (
    BaseSkill,
    SkillRegistry,
    SKILL_REGISTRY,
    skill,
    load_skills,
)

__all__ = [
    "BaseSkill",
    "SkillRegistry",
    "SKILL_REGISTRY",
    "skill",
    "load_skills",
]
