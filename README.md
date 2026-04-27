# Mini Agent 🤖

> **从零构建生产级 AI Agent** — A hands-on teaching project for building real, production-quality AI agents in Python.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What Is This?

Mini Agent is a **progressive teaching curriculum** that walks you through building a complete AI agent framework from first principles. Each chapter is a self-contained lesson that introduces one core concept, with working code you can run immediately.

By the end, you'll have built the same kind of architecture that powers production agents — and you'll understand every component.

---

## What You'll Learn

| Chapter | Topic | Key Concepts |
|---------|-------|--------------|
| 01 | LLM Client | ABC pattern, retry + exponential backoff, streaming |
| 02 | Agent Loop | ReAct pattern, tool call parsing, iteration control |
| 03 | Tool System | Decorator factory, JSON Schema, tool registry |
| 04 | Memory | Sliding window (deque), JSON persistence, search |
| 05 | Context Window | Token counting (tiktoken), trim strategies |
| 06 | Prompt Engineering | Builder pattern, templates, few-shot prompting |
| 07 | Skill System | Plugin architecture, auto-registration, composition |

---

## Project Structure

```
mini_agent/
├── SYLLABUS.md              # Full curriculum in Chinese (中文大纲)
├── requirements.txt
├── pyproject.toml
│
├── chapters/                # 📚 Teaching chapters (start here!)
│   ├── ch01_llm_client/     # LLM abstraction layer
│   ├── ch02_agent_loop/     # ReAct agent loop
│   ├── ch03_tools/          # Tool system with decorator
│   ├── ch04_memory/         # Conversation + persistent memory
│   ├── ch05_context/        # Context window management
│   ├── ch06_prompt/         # Prompt builder patterns
│   └── ch07_skills/         # Skill plugin system
│
└── mini_agent/              # 🚀 Complete production package
    ├── config.py            # Centralised config (env-driven)
    ├── main.py              # Rich CLI entry point
    ├── core/
    │   ├── llm.py           # OpenAI-compatible client
    │   ├── loop.py          # Full ReAct agent loop
    │   ├── context.py       # Token counting + trim
    │   └── prompt.py        # System prompt builder
    ├── tools/
    │   ├── base.py          # Tool + registry abstractions
    │   └── builtins.py      # Built-in tools (calc, files, memory…)
    ├── memory/
    │   ├── conversation.py  # Short-term memory
    │   └── persistent.py    # JSON-backed long-term memory
    └── skills/
        └── base.py          # Skill abstraction + registry
```

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/samz406/mini_agent.git
cd mini_agent
pip install -e .
```

### 2. Set Your API Key

```bash
export OPENAI_API_KEY=sk-your-key-here
# or create a .env file:
echo "OPENAI_API_KEY=sk-your-key-here" > .env
```

### 3. Run the Agent

```bash
mini-agent
```

Or with options:

```bash
mini-agent --model gpt-4o --system-prompt "You are a Python tutor."
```

---

## Interactive Commands

Once the agent is running, use these slash commands:

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/tools` | List available tools |
| `/memory` | Show persistent memory |
| `/clear` | Clear conversation history |
| `/quit` | Exit |

---

## Built-in Tools

The agent comes with these tools out of the box:

| Tool | Description |
|------|-------------|
| `calculate` | Safe math evaluator (AST-based, no `eval`) |
| `get_current_time` | Current time |
| `get_current_date` | Current date |
| `read_file` | Read a text file (max 10k chars) |
| `write_file` | Write/create a file |
| `list_directory` | List directory contents |
| `search_memory` | Search persistent memory |
| `save_memory` | Save a fact to persistent memory |

---

## Chapter-by-Chapter Guide

Each chapter is **self-contained** — you can run its code independently.

```bash
# Chapter 1: LLM Client
cd chapters/ch01_llm_client
python llm_client.py

# Chapter 2: Agent Loop (no API key needed — uses mock LLM)
cd chapters/ch02_agent_loop
python agent_loop.py

# Chapter 3: Tool System
cd chapters/ch03_tools
python example_tools.py

# Chapter 4: Memory
cd chapters/ch04_memory
python memory.py

# Chapter 5: Context Management
cd chapters/ch05_context
python context_manager.py

# Chapter 6: Prompt Builder
cd chapters/ch06_prompt
python prompt_builder.py

# Chapter 7: Skill System
cd chapters/ch07_skills
python skill_system.py
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *(required)* | Your OpenAI API key |
| `MINI_AGENT_MODEL` | `gpt-4o-mini` | LLM model to use |
| `MINI_AGENT_API_BASE` | OpenAI default | Custom API base URL |
| `MINI_AGENT_MAX_ITERATIONS` | `10` | Max ReAct loop iterations |
| `MINI_AGENT_MAX_TOKENS` | `8000` | Context window token budget |
| `MINI_AGENT_TEMPERATURE` | `0.7` | LLM temperature |
| `MINI_AGENT_SYSTEM_PROMPT` | *(default persona)* | Custom system prompt |
| `MINI_AGENT_MEMORY_FILE` | `.mini_agent_memory.json` | Persistent memory file |

---

## License

MIT — see [LICENSE](LICENSE).
