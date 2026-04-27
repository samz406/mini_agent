"""mini_agent.memory.conversation — Short-term sliding-window conversation memory."""

from __future__ import annotations

from collections import deque
from datetime import datetime

from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    """A single message stored in conversation memory."""

    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)


class ConversationMemory:
    """Short-term conversation history backed by a ``collections.deque``.

    When the buffer reaches ``max_size``, the oldest message is automatically
    evicted when a new one is added.
    """

    def __init__(self, max_size: int = 100) -> None:
        self._buf: deque[ConversationMessage] = deque(maxlen=max_size)

    def add(self, role: str, content: str) -> None:
        """Append a new message to the conversation."""
        self._buf.append(ConversationMessage(role=role, content=content))

    def get_all(self) -> list[ConversationMessage]:
        """Return all stored messages in chronological order."""
        return list(self._buf)

    def to_messages(self) -> list[dict]:
        """Return messages as plain dicts suitable for LLM API calls."""
        return [{"role": m.role, "content": m.content} for m in self._buf]

    def clear(self) -> None:
        """Remove all messages from memory."""
        self._buf.clear()

    def __len__(self) -> int:
        return len(self._buf)
