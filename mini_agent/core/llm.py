"""mini_agent.core.llm — LLM client abstractions and OpenAI-compatible implementation."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Iterator, Optional

from pydantic import BaseModel, Field

from mini_agent.config import AgentConfig


class LLMMessage(BaseModel):
    """A single message in a conversation."""

    role: str
    content: str
    name: Optional[str] = None

    def to_dict(self) -> dict:
        d: dict = {"role": self.role, "content": self.content}
        if self.name:
            d["name"] = self.name
        return d


class ToolCallFunction(BaseModel):
    """The function portion of a tool call."""

    name: str
    arguments: str  # JSON string


class ToolCall(BaseModel):
    """A single tool call emitted by the LLM."""

    id: str
    type: str = "function"
    function: ToolCallFunction


class LLMUsage(BaseModel):
    """Token usage statistics from the API response."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class LLMResponse(BaseModel):
    """Normalised response from any LLM backend."""

    content: Optional[str] = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: Optional[LLMUsage] = None
    finish_reason: str = "stop"


class BaseLLMClient(ABC):
    """Abstract base class — all LLM clients must implement these two methods."""

    @abstractmethod
    def complete(
        self,
        messages: list[LLMMessage],
        tools: Optional[list[dict]] = None,
    ) -> LLMResponse:
        """Send messages (and optional tool schemas) and return a response."""
        ...

    @abstractmethod
    def stream(
        self,
        messages: list[LLMMessage],
        tools: Optional[list[dict]] = None,
    ) -> Iterator[str]:
        """Stream response tokens one chunk at a time."""
        ...


class OpenAICompatibleClient(BaseLLMClient):
    """LLM client that talks to any OpenAI-compatible API.

    Handles:
    - Automatic retry with exponential backoff on rate limit errors
    - Tool / function calling
    - Streaming
    """

    _MAX_RETRIES = 3

    def __init__(self, config: AgentConfig) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError("Install openai: pip install openai") from exc

        self._config = config
        self._client = OpenAI(
            api_key=config.api_key,
            base_url=config.api_base,
        )

    def _messages_to_dicts(self, messages: list[LLMMessage]) -> list[dict]:
        return [m.to_dict() for m in messages]

    def complete(
        self,
        messages: list[LLMMessage],
        tools: Optional[list[dict]] = None,
    ) -> LLMResponse:
        """Call the API with exponential-backoff retry on rate limiting."""
        from openai import RateLimitError

        payload = self._messages_to_dicts(messages)
        last_exc: Exception | None = None

        for attempt in range(self._MAX_RETRIES):
            try:
                kwargs: dict = dict(
                    model=self._config.model,
                    messages=payload,  # type: ignore[arg-type]
                    temperature=self._config.temperature,
                )
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"

                raw = self._client.chat.completions.create(**kwargs)
                choice = raw.choices[0]
                msg = choice.message

                # Parse tool calls if present
                parsed_tool_calls: list[ToolCall] = []
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        parsed_tool_calls.append(
                            ToolCall(
                                id=tc.id,
                                type=tc.type,
                                function=ToolCallFunction(
                                    name=tc.function.name,
                                    arguments=tc.function.arguments,
                                ),
                            )
                        )

                usage: Optional[LLMUsage] = None
                if raw.usage:
                    usage = LLMUsage(
                        prompt_tokens=raw.usage.prompt_tokens,
                        completion_tokens=raw.usage.completion_tokens,
                        total_tokens=raw.usage.total_tokens,
                    )

                return LLMResponse(
                    content=msg.content,
                    tool_calls=parsed_tool_calls,
                    usage=usage,
                    finish_reason=choice.finish_reason or "stop",
                )

            except RateLimitError as exc:
                last_exc = exc
                wait = 2**attempt
                time.sleep(wait)
            except Exception:
                raise

        raise RuntimeError(f"LLM call failed after {self._MAX_RETRIES} retries") from last_exc

    def stream(
        self,
        messages: list[LLMMessage],
        tools: Optional[list[dict]] = None,
    ) -> Iterator[str]:
        """Yield response content tokens as they stream from the API."""
        payload = self._messages_to_dicts(messages)
        kwargs: dict = dict(
            model=self._config.model,
            messages=payload,  # type: ignore[arg-type]
            temperature=self._config.temperature,
            stream=True,
        )
        if tools:
            kwargs["tools"] = tools

        for chunk in self._client.chat.completions.create(**kwargs):
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
