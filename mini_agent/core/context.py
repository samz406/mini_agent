"""mini_agent.core.context — Token counting and context window management."""

from __future__ import annotations

from typing import Optional


class TokenCounter:
    """Count tokens using tiktoken, with a character-based fallback.

    If tiktoken is not installed, every token is estimated as 4 characters.
    """

    def __init__(self, encoding_name: str = "cl100k_base") -> None:
        self._enc: Optional[object] = None
        try:
            import tiktoken
            self._enc = tiktoken.get_encoding(encoding_name)
        except Exception:
            pass

    def count(self, text: str) -> int:
        """Return the number of tokens in *text*."""
        if self._enc is not None:
            return len(self._enc.encode(text))  # type: ignore[attr-defined]
        return max(1, len(text) // 4)

    def count_messages(self, messages: list[dict]) -> int:
        """Estimate total tokens for a list of message dicts.

        Adds 4 tokens per message for role/formatting overhead (matches OpenAI billing).
        """
        total = 0
        for msg in messages:
            total += 4
            total += self.count(msg.get("content") or "")
            total += self.count(msg.get("role", ""))
        total += 2  # reply priming
        return total


class ContextManager:
    """Trim a message list to fit within a token budget.

    Strategy: always preserve the system message; drop the oldest non-system
    messages until the total token count is within budget.
    """

    def __init__(self, max_tokens: int = 8000) -> None:
        self.max_tokens = max_tokens
        self._counter = TokenCounter()

    def get_token_count(self, messages: list[dict]) -> int:
        """Return the estimated token count for *messages*."""
        return self._counter.count_messages(messages)

    def trim(self, messages: list[dict]) -> list[dict]:
        """Return a copy of *messages* trimmed to fit within ``max_tokens``.

        The system message (role == "system") is always kept.
        Older non-system messages are dropped first.
        """
        if not messages:
            return []

        if self.get_token_count(messages) <= self.max_tokens:
            return list(messages)

        system_msgs = [m for m in messages if m.get("role") == "system"]
        other_msgs = [m for m in messages if m.get("role") != "system"]

        # Build from the most recent messages backwards
        kept: list[dict] = []
        for msg in reversed(other_msgs):
            candidate = system_msgs + [msg] + kept
            if self._counter.count_messages(candidate) <= self.max_tokens:
                kept.insert(0, msg)
            else:
                break

        dropped = len(other_msgs) - len(kept)
        if dropped > 0:
            pass  # Caller can log if needed

        return system_msgs + kept
