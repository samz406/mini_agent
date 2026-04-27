"""Chapter 1: LLM Client Abstraction.

Teaches: ABC pattern, retry logic, streaming, message abstraction.
"""

from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator


@dataclass
class Message:
    """A single conversation message."""

    role: str
    content: str

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


class BaseLLMClient(ABC):
    """Abstract base class for all LLM clients.

    Any LLM provider (OpenAI, Anthropic, local) must implement these two methods.
    This lets agent code remain provider-agnostic.
    """

    @abstractmethod
    def complete(self, messages: list[Message]) -> Message:
        """Send messages and return the assistant's reply."""
        ...

    @abstractmethod
    def stream(self, messages: list[Message]) -> Iterator[str]:
        """Send messages and yield response tokens as they arrive."""
        ...


class OpenAIClient(BaseLLMClient):
    """OpenAI chat completion client with retry logic and streaming support."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        temperature: float = 0.7,
        max_retries: int = 3,
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError("Install openai: pip install openai") from exc

        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries
        self.client = OpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY", ""),
            base_url=base_url,
        )

    def complete(self, messages: list[Message]) -> Message:
        """Call the API with exponential-backoff retry on rate limit errors."""
        from openai import RateLimitError

        payload = [m.to_dict() for m in messages]
        last_exc: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=payload,  # type: ignore[arg-type]
                    temperature=self.temperature,
                )
                content = response.choices[0].message.content or ""
                return Message(role="assistant", content=content)
            except RateLimitError as exc:
                last_exc = exc
                wait = 2**attempt
                print(f"[Rate limited] Retrying in {wait}s (attempt {attempt + 1}/{self.max_retries})")
                time.sleep(wait)
            except Exception as exc:
                raise exc

        raise RuntimeError(f"Failed after {self.max_retries} retries") from last_exc

    def stream(self, messages: list[Message]) -> Iterator[str]:
        """Stream response tokens one chunk at a time."""
        payload = [m.to_dict() for m in messages]
        response = self.client.chat.completions.create(
            model=self.model,
            messages=payload,  # type: ignore[arg-type]
            temperature=self.temperature,
            stream=True,
        )
        for chunk in response:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content


if __name__ == "__main__":
    client = OpenAIClient(model="gpt-4o-mini")

    # --- Non-streaming ---
    print("=== Non-streaming ===")
    msgs = [
        Message(role="system", content="You are a helpful assistant."),
        Message(role="user", content="Hello! What can you do?"),
    ]
    reply = client.complete(msgs)
    print(f"Assistant: {reply.content}\n")

    # --- Streaming ---
    print("=== Streaming ===")
    msgs.append(reply)
    msgs.append(Message(role="user", content="Give me a one-sentence fun fact about Python."))
    print("Assistant: ", end="", flush=True)
    for token in client.stream(msgs):
        print(token, end="", flush=True)
    print()
