"""mini_agent.memory.persistent — JSON-backed persistent key-value memory."""

from __future__ import annotations

import json
import os
from typing import Any, Optional


class PersistentMemory:
    """Long-term key-value memory persisted to a JSON file.

    Data is loaded from the file on initialisation and written back
    on every ``set()`` or ``delete()`` call.
    """

    def __init__(self, filepath: str = ".mini_agent_memory.json") -> None:
        self.filepath = filepath
        self._data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Load data from the JSON file (no-op if file does not exist)."""
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
        """Return the value stored under *key*, or ``None`` if absent."""
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
        q = query.lower()
        return {k: v for k, v in self._data.items() if q in k.lower() or q in str(v).lower()}

    def get_all(self) -> dict:
        """Return a copy of all stored data."""
        return dict(self._data)
