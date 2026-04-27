"""Chapter 5: Context Window Management.

Teaches: token counting, sliding window trim, summarization strategy stub.
"""

from __future__ import annotations

import json
from typing import Callable, Optional


class TokenCounter:
    """Count tokens using tiktoken, falling back to char-based estimate."""

    def __init__(self, encoding_name: str = "cl100k_base") -> None:
        self._enc = None
        try:
            import tiktoken
            self._enc = tiktoken.get_encoding(encoding_name)
        except Exception:
            pass  # Will use fallback

    def count(self, text: str) -> int:
        """Return token count for *text*."""
        if self._enc is not None:
            return len(self._enc.encode(text))
        # Fallback: ~4 chars per token is a reasonable English estimate
        return max(1, len(text) // 4)

    def count_messages(self, messages: list[dict]) -> int:
        """Estimate total tokens for a list of message dicts.

        OpenAI charges ~4 extra tokens per message for role/formatting overhead.
        """
        total = 0
        for msg in messages:
            total += 4  # message overhead
            total += self.count(msg.get("content", ""))
            total += self.count(msg.get("role", ""))
        total += 2  # reply prime tokens
        return total


class ContextWindow:
    """Checks whether a message list fits in a token budget."""

    def __init__(self, max_tokens: int = 8000) -> None:
        self.max_tokens = max_tokens
        self._counter = TokenCounter()

    def fits(self, messages: list[dict]) -> bool:
        """Return True if messages fit within the token limit."""
        return self.token_count(messages) <= self.max_tokens

    def token_count(self, messages: list[dict]) -> int:
        return self._counter.count_messages(messages)


class SlidingWindowStrategy:
    """Trim strategy that preserves the system message and drops oldest messages."""

    def __init__(self) -> None:
        self._counter = TokenCounter()

    def trim(self, messages: list[dict], max_tokens: int) -> list[dict]:
        """Return a trimmed copy of *messages* that fits within *max_tokens*.

        Always keeps the system message (if present). Drops oldest non-system
        messages until the list fits.
        """
        if not messages:
            return []

        system_msgs = [m for m in messages if m.get("role") == "system"]
        other_msgs = [m for m in messages if m.get("role") != "system"]

        # Start from the most recent and work backwards
        trimmed: list[dict] = []
        for msg in reversed(other_msgs):
            candidate = system_msgs + [msg] + trimmed
            if self._counter.count_messages(candidate) <= max_tokens:
                trimmed.insert(0, msg)
            else:
                break  # Can't fit more

        result = system_msgs + trimmed
        dropped = len(other_msgs) - len(trimmed)
        if dropped > 0:
            print(f"  [context] Dropped {dropped} old message(s) to fit token limit.")
        return result


class SummarizationStrategy:
    """Trim strategy that summarizes old messages instead of dropping them.

    Falls back to SlidingWindowStrategy if no summarize_fn is provided.
    """

    def __init__(self) -> None:
        self._counter = TokenCounter()
        self._sliding = SlidingWindowStrategy()

    def trim(
        self,
        messages: list[dict],
        max_tokens: int,
        summarize_fn: Optional[Callable[[list[dict]], str]] = None,
    ) -> list[dict]:
        """Trim messages using summarization or sliding window fallback."""
        if self._counter.count_messages(messages) <= max_tokens:
            return messages

        if summarize_fn is None:
            print("  [context] No summarize_fn provided, falling back to sliding window.")
            return self._sliding.trim(messages, max_tokens)

        system_msgs = [m for m in messages if m.get("role") == "system"]
        other_msgs = [m for m in messages if m.get("role") != "system"]

        # Summarize the oldest half of non-system messages
        split_point = len(other_msgs) // 2
        old_msgs = other_msgs[:split_point]
        recent_msgs = other_msgs[split_point:]

        if old_msgs:
            summary_text = summarize_fn(old_msgs)
            summary_msg = {"role": "system", "content": f"[Summary of earlier conversation]: {summary_text}"}
            result = system_msgs + [summary_msg] + recent_msgs
            print(f"  [context] Summarized {len(old_msgs)} old messages into 1 summary message.")
            return result

        return self._sliding.trim(messages, max_tokens)


if __name__ == "__main__":
    counter = TokenCounter()

    print("=== Token Counting ===")
    samples = [
        "Hello, world!",
        "This is a longer sentence with more tokens in it.",
        "The quick brown fox jumps over the lazy dog." * 10,
    ]
    for s in samples:
        print(f"  {len(s):4d} chars → {counter.count(s):4d} tokens: {s[:50]!r}")

    print("\n=== Context Window Check ===")
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        *[
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"Message number {i} " * 20}
            for i in range(20)
        ],
    ]
    window = ContextWindow(max_tokens=500)
    print(f"  Total tokens: {window.token_count(messages)}")
    print(f"  Fits in 500 tokens: {window.fits(messages)}")

    print("\n=== Sliding Window Trim ===")
    strategy = SlidingWindowStrategy()
    trimmed = strategy.trim(messages, max_tokens=500)
    print(f"  Before: {len(messages)} messages, {counter.count_messages(messages)} tokens")
    print(f"  After:  {len(trimmed)} messages, {counter.count_messages(trimmed)} tokens")

    print("\n=== Summarization Strategy (fallback) ===")
    summ_strategy = SummarizationStrategy()
    trimmed2 = summ_strategy.trim(messages, max_tokens=500)
    print(f"  After:  {len(trimmed2)} messages, {counter.count_messages(trimmed2)} tokens")
