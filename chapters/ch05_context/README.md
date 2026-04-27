# Chapter 5: Context Window Management

## What You'll Learn

Every LLM has a finite context window. When your conversation exceeds it, the API returns an error or silently truncates. This chapter builds the machinery to manage context proactively.

## Why Context Management Matters

- GPT-4o has ~128k tokens; smaller/cheaper models have 4k–8k
- Each token costs money — wasteful context = higher bills
- Without trimming, a long conversation eventually crashes

## Token Counting

`TokenCounter` wraps tiktoken:

```python
counter = TokenCounter()
counter.count("Hello, world!")  # → 4 tokens
counter.count_messages([{"role": "user", "content": "Hi"}])  # → ~8 tokens
```

If tiktoken isn't installed, falls back to `len(text) // 4` (a reasonable approximation since the average English word is ~4 chars and ~1 token).

## Trim Strategies

### Sliding Window Strategy
Keep the **system message** (it defines the agent's persona) and as many **recent messages** as fit within the token budget. Oldest messages are dropped first.

```
[system] [old1] [old2] [recent3] [recent4] [recent5]
                 ↑ dropped to fit token limit
```

### Summarization Strategy (Advanced)
Instead of dropping old messages, summarize them into one compressed message. Requires an LLM call to generate the summary.

```
[system] [SUMMARY: old1+old2 summarized] [recent3] [recent4] [recent5]
```

The stub implementation falls back to sliding window if no `summarize_fn` is provided.

## How to Run

```bash
cd chapters/ch05_context
python context_manager.py
```

You'll see token counts and trimmed message lists demonstrated with sample data.
