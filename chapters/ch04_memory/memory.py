"""Chapter 4: Memory System.

Teaches: conversation memory with deque, persistent JSON memory, memory manager facade.
"""

from __future__ import annotations

import json
import os
from collections import deque
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
    """A conversation message with an automatic timestamp."""

    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)


class ConversationMemory:
    """Short-term sliding-window conversation history.

    Uses a ``collections.deque`` so the oldest messages are automatically
    evicted when the buffer is full.
    """

    def __init__(self, max_size: int = 100) -> None:
        self._buf: deque[Message] = deque(maxlen=max_size)

    def add(self, role: str, content: str) -> None:
        """Append a new message to the conversation."""
        self._buf.append(Message(role=role, content=content))

    def get_all(self) -> list[Message]:
        """Return all stored messages in chronological order."""
        return list(self._buf)

    def clear(self) -> None:
        """Remove all messages."""
        self._buf.clear()

    def to_dict_list(self) -> list[dict]:
        """Return messages as plain dicts (for LLM API calls)."""
        return [{"role": m.role, "content": m.content} for m in self._buf]

    def __len__(self) -> int:
        return len(self._buf)


class PersistentMemory:
    """Long-term key-value memory backed by a JSON file.

    Survives between sessions; good for user preferences, facts to remember, etc.
    """

    def __init__(self, filepath: str = ".memory.json") -> None:
        self.filepath = filepath
        self._data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Load data from the JSON file (if it exists)."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as fh:
                    self._data = json.load(fh)
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def save(self) -> None:
        """Write current data to the JSON file."""
        with open(self.filepath, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2, ensure_ascii=False)

    def get(self, key: str) -> Optional[Any]:
        """Return the value for *key*, or ``None`` if absent."""
        return self._data.get(key)

    def set(self, key: str, value: Any) -> None:
        """Store *value* under *key* and persist immediately."""
        self._data[key] = value
        self.save()

    def delete(self, key: str) -> None:
        """Remove *key* from memory and persist."""
        self._data.pop(key, None)
        self.save()

    def search(self, query: str) -> dict:
        """Return all entries whose key or value string contains *query*."""
        query_lower = query.lower()
        return {
            k: v
            for k, v in self._data.items()
            if query_lower in k.lower() or query_lower in str(v).lower()
        }

    def get_all(self) -> dict:
        return dict(self._data)


class MemoryManager:
    """Facade that combines conversation and persistent memory."""

    def __init__(
        self,
        max_conversation_size: int = 100,
        persistent_file: str = ".memory.json",
    ) -> None:
        self.conversation = ConversationMemory(max_size=max_conversation_size)
        self.persistent = PersistentMemory(filepath=persistent_file)

    def add_message(self, role: str, content: str) -> None:
        self.conversation.add(role, content)

    def get_conversation(self) -> list[dict]:
        return self.conversation.to_dict_list()

    def remember(self, key: str, value: Any) -> None:
        self.persistent.set(key, value)

    def recall(self, key: str) -> Optional[Any]:
        return self.persistent.get(key)

    def search_memory(self, query: str) -> dict:
        return self.persistent.search(query)


if __name__ == "__main__":
    import tempfile, pathlib

    # Use a temp-like path in cwd to avoid /tmp
    demo_file = str(pathlib.Path(__file__).parent / ".memory_demo.json")

    manager = MemoryManager(max_conversation_size=5, persistent_file=demo_file)

    print("=== Conversation Memory (max 5 messages) ===")
    for i in range(7):
        role = "user" if i % 2 == 0 else "assistant"
        manager.add_message(role, f"Message {i}")

    print(f"Stored {len(manager.conversation)} messages (max 5):")
    for msg in manager.get_conversation():
        print(f"  [{msg['role']}] {msg['content']}")

    print("\n=== Persistent Memory ===")
    manager.remember("user_name", "Alice")
    manager.remember("preferred_lang", "Python")
    manager.remember("last_topic", "AI agents")

    print(f"Recalled user_name: {manager.recall('user_name')}")
    print(f"Search 'Python': {manager.search_memory('Python')}")
    print(f"All entries: {manager.persistent.get_all()}")

    # Cleanup demo file
    if os.path.exists(demo_file):
        os.remove(demo_file)
        print("\nDemo memory file cleaned up.")
