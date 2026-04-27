# Chapter 4: Memory System

## What You'll Learn

Agents need memory to be useful across multiple turns. This chapter builds two complementary memory systems and a unified manager that combines them.

## Two Types of Memory

### Conversation Memory (Short-term)
Stores the current session's message history. It uses Python's `collections.deque` with `maxlen` to automatically discard the oldest messages when the conversation grows too long.

```
[user: hi] [assistant: hello] [user: calc?] [assistant: result] ... → oldest dropped
```

### Persistent Memory (Long-term)
A simple key-value store backed by a JSON file. Survives between sessions. The agent can store facts like `"user_name": "Alice"` and retrieve them in future conversations.

## Key Implementation Details

### `deque(maxlen=N)` for Sliding Window
When you append to a full deque, it automatically removes from the left. Zero manual management needed:

```python
from collections import deque
buf = deque(maxlen=3)
buf.extend([1, 2, 3])
buf.append(4)  # → deque([2, 3, 4], maxlen=3)
```

### JSON Persistence
`PersistentMemory` reads from and writes to a `.json` file atomically on each `set()` / `delete()`. Simple, portable, no database required.

### String-based Search
`search(query)` scans all keys and string-represented values for the query substring. Good enough for small memory stores; replace with vector search for production scale.

## The `MemoryManager` Facade

Combines both memory types behind a single interface:

```python
manager = MemoryManager()
manager.add_message("user", "Hello")            # → conversation memory
manager.remember("user_name", "Alice")          # → persistent memory
manager.recall("user_name")                     # → "Alice"
messages = manager.get_conversation()           # → list of dicts
```

## How to Run

```bash
cd chapters/ch04_memory
python memory.py
```

A `.memory_demo.json` file will be created, demonstrating persistent storage across calls.
