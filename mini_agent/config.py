"""Agent configuration — loads from environment variables or defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class AgentConfig:
    """Centralised configuration for the Mini Agent.

    All fields can be overridden via environment variables (see ``from_env``).
    """

    model: str = "gpt-4o-mini"
    api_base: str = "https://api.openai.com/v1"
    api_key: str = ""
    max_iterations: int = 10
    max_context_tokens: int = 8000
    temperature: float = 0.7
    system_prompt: str = ""
    memory_file: str = ".mini_agent_memory.json"

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Create an ``AgentConfig`` from environment variables.

        Supported variables:
        - ``OPENAI_API_KEY``
        - ``MINI_AGENT_MODEL``
        - ``MINI_AGENT_API_BASE``
        - ``MINI_AGENT_MAX_ITERATIONS``
        - ``MINI_AGENT_MAX_TOKENS``
        - ``MINI_AGENT_TEMPERATURE``
        - ``MINI_AGENT_SYSTEM_PROMPT``
        - ``MINI_AGENT_MEMORY_FILE``
        """
        load_dotenv()
        return cls(
            model=os.getenv("MINI_AGENT_MODEL", "gpt-4o-mini"),
            api_base=os.getenv("MINI_AGENT_API_BASE", "https://api.openai.com/v1"),
            api_key=os.getenv("OPENAI_API_KEY", ""),
            max_iterations=int(os.getenv("MINI_AGENT_MAX_ITERATIONS", "10")),
            max_context_tokens=int(os.getenv("MINI_AGENT_MAX_TOKENS", "8000")),
            temperature=float(os.getenv("MINI_AGENT_TEMPERATURE", "0.7")),
            system_prompt=os.getenv("MINI_AGENT_SYSTEM_PROMPT", ""),
            memory_file=os.getenv("MINI_AGENT_MEMORY_FILE", ".mini_agent_memory.json"),
        )
