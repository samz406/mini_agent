"""Agent configuration — loads from environment variables or defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class AgentConfig:
    """Centralised configuration for the Mini Agent.

    All fields can be overridden via environment variables (see ``from_env``).

    Provider selection
    ------------------
    Set ``MINI_AGENT_PROVIDER`` (or pass ``--provider`` on the CLI) to one of
    the built-in provider names: ``openai``, ``qwen``, ``kimi``, ``minimax``,
    ``deepseek``, ``glm``.  When a provider is set, its ``api_base`` and the
    corresponding API-key environment variable are resolved automatically.
    Explicit ``MINI_AGENT_API_BASE`` and ``OPENAI_API_KEY`` values always take
    precedence over the provider defaults.
    """

    model: str = "gpt-4o-mini"
    api_base: str = "https://api.openai.com/v1"
    api_key: str = ""
    provider: str = "openai"
    max_iterations: int = 10
    max_context_tokens: int = 8000
    temperature: float = 0.7
    system_prompt: str = ""
    memory_file: str = ".mini_agent_memory.json"

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Create an ``AgentConfig`` from environment variables.

        Supported variables:
        - ``MINI_AGENT_PROVIDER``         — provider name (e.g. ``qwen``)
        - ``MINI_AGENT_MODEL``            — model name override
        - ``MINI_AGENT_API_BASE``         — API base URL override
        - ``OPENAI_API_KEY``              — API key (OpenAI / generic)
        - ``DASHSCOPE_API_KEY``           — API key for Qwen
        - ``MOONSHOT_API_KEY``            — API key for Kimi / Moonshot
        - ``MINIMAX_API_KEY``             — API key for MiniMax
        - ``DEEPSEEK_API_KEY``            — API key for DeepSeek
        - ``ZHIPU_API_KEY``               — API key for GLM / Zhipu AI
        - ``MINI_AGENT_MAX_ITERATIONS``
        - ``MINI_AGENT_MAX_TOKENS``
        - ``MINI_AGENT_TEMPERATURE``
        - ``MINI_AGENT_SYSTEM_PROMPT``
        - ``MINI_AGENT_MEMORY_FILE``
        """
        load_dotenv()

        from mini_agent.providers import get_provider  # local import to avoid circular

        provider_name = os.getenv("MINI_AGENT_PROVIDER", "openai").lower()
        provider_cfg = get_provider(provider_name)

        # Resolve api_base: explicit env var > provider default > OpenAI default
        if provider_cfg is not None:
            default_api_base = provider_cfg.api_base
            default_model = provider_cfg.default_model
            # API key: read from the provider-specific env var, fallback to OPENAI_API_KEY
            default_api_key = os.getenv(provider_cfg.key_env_var) or os.getenv("OPENAI_API_KEY", "")
        else:
            default_api_base = "https://api.openai.com/v1"
            default_model = "gpt-4o-mini"
            default_api_key = os.getenv("OPENAI_API_KEY", "")

        return cls(
            provider=provider_name,
            model=os.getenv("MINI_AGENT_MODEL", default_model),
            api_base=os.getenv("MINI_AGENT_API_BASE", default_api_base),
            api_key=default_api_key,
            max_iterations=int(os.getenv("MINI_AGENT_MAX_ITERATIONS", "10")),
            max_context_tokens=int(os.getenv("MINI_AGENT_MAX_TOKENS", "8000")),
            temperature=float(os.getenv("MINI_AGENT_TEMPERATURE", "0.7")),
            system_prompt=os.getenv("MINI_AGENT_SYSTEM_PROMPT", ""),
            memory_file=os.getenv("MINI_AGENT_MEMORY_FILE", ".mini_agent_memory.json"),
        )
