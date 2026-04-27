"""mini_agent.providers — Registry of supported LLM provider configurations.

Each provider entry contains:
- ``api_base``:      The OpenAI-compatible base URL for that provider.
- ``default_model``: Sensible default model name for the provider.
- ``key_env_var``:   Name of the environment variable that holds the API key.

All providers listed here expose an OpenAI-compatible chat-completions API,
so they all work with :class:`~mini_agent.core.llm.OpenAICompatibleClient`
without any additional code.

Usage
-----
Set the provider via an environment variable or the ``--provider`` CLI flag::

    MINI_AGENT_PROVIDER=qwen DASHSCOPE_API_KEY=sk-... mini-agent

Supported provider names (case-insensitive):
  openai, qwen, kimi, moonshot, minimax, deepseek, glm, zhipu
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ProviderConfig:
    """Static configuration for a single LLM provider."""

    name: str
    api_base: str
    default_model: str
    key_env_var: str
    description: str = ""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_PROVIDERS: dict[str, ProviderConfig] = {
    "openai": ProviderConfig(
        name="openai",
        api_base="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        key_env_var="OPENAI_API_KEY",
        description="OpenAI (GPT-4o, GPT-4o-mini, …)",
    ),
    "qwen": ProviderConfig(
        name="qwen",
        api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        default_model="qwen-turbo",
        key_env_var="DASHSCOPE_API_KEY",
        description="Alibaba Cloud Qwen (qwen-turbo, qwen-plus, qwen-max, …)",
    ),
    "kimi": ProviderConfig(
        name="kimi",
        api_base="https://api.moonshot.cn/v1",
        default_model="moonshot-v1-8k",
        key_env_var="MOONSHOT_API_KEY",
        description="Moonshot AI Kimi (moonshot-v1-8k, moonshot-v1-32k, moonshot-v1-128k, …)",
    ),
    "moonshot": ProviderConfig(
        # Alias for kimi
        name="moonshot",
        api_base="https://api.moonshot.cn/v1",
        default_model="moonshot-v1-8k",
        key_env_var="MOONSHOT_API_KEY",
        description="Moonshot AI (alias: kimi)",
    ),
    "minimax": ProviderConfig(
        name="minimax",
        api_base="https://api.minimax.chat/v1",
        default_model="MiniMax-Text-01",
        key_env_var="MINIMAX_API_KEY",
        description="MiniMax (MiniMax-Text-01, abab6.5s-chat, …)",
    ),
    "deepseek": ProviderConfig(
        name="deepseek",
        api_base="https://api.deepseek.com/v1",
        default_model="deepseek-chat",
        key_env_var="DEEPSEEK_API_KEY",
        description="DeepSeek (deepseek-chat, deepseek-reasoner, …)",
    ),
    "glm": ProviderConfig(
        name="glm",
        api_base="https://open.bigmodel.cn/api/paas/v4",
        default_model="glm-4-flash",
        key_env_var="ZHIPU_API_KEY",
        description="Zhipu AI / GLM (glm-4-flash, glm-4, glm-4-plus, …)",
    ),
    "zhipu": ProviderConfig(
        # Alias for glm
        name="zhipu",
        api_base="https://open.bigmodel.cn/api/paas/v4",
        default_model="glm-4-flash",
        key_env_var="ZHIPU_API_KEY",
        description="Zhipu AI (alias: glm)",
    ),
}


def get_provider(name: str) -> Optional[ProviderConfig]:
    """Return the :class:`ProviderConfig` for *name* (case-insensitive), or ``None``."""
    return _PROVIDERS.get(name.lower())


def list_providers() -> list[ProviderConfig]:
    """Return all registered providers, excluding hidden aliases."""
    seen: set[str] = set()
    result: list[ProviderConfig] = []
    for cfg in _PROVIDERS.values():
        # Skip duplicate aliases (same api_base + same key_env_var already added)
        key = (cfg.api_base, cfg.key_env_var)
        if key not in seen:
            seen.add(key)
            result.append(cfg)
    return result


def provider_names() -> list[str]:
    """Return the canonical (non-alias) provider names."""
    return [p.name for p in list_providers()]
