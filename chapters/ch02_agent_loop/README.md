# Chapter 2: The Agent Loop (ReAct Pattern)

## What You'll Learn

This chapter implements the core of any agent: the reasoning loop. We implement the **ReAct** (Reasoning + Acting) pattern—the backbone of most production agents.

## The ReAct Pattern

```
User Input
    │
    ▼
┌─────────────────────────────────────┐
│  REASON: Call LLM, get response     │
│                                     │
│  PARSE:  Extract tool calls         │
│                                     │
│  ACT:    Execute tools              │
│                                     │
│  OBSERVE: Add results to history    │
│                                     │
│  → Repeat until no tool calls       │
│    or max_iterations reached        │
└─────────────────────────────────────┘
    │
    ▼
Final Response
```

## Tool Call Format

The agent expects the LLM to output tool calls in this format anywhere in its response:

```
TOOL_CALL: {"name": "calculator", "args": {"expression": "2 + 2"}}
```

Multiple tool calls can appear in one response. The agent parses all of them, executes them in order, and feeds results back to the LLM as new messages.

## Stopping Conditions

The loop stops when **any** of these is true:
1. The LLM response contains no tool calls → final answer reached
2. `max_iterations` has been exceeded → safety cutoff

## Code Walkthrough

```python
class AgentLoop:
    def run(self, user_input: str) -> str:
        self.history.append(Message("user", user_input))
        
        for iteration in range(self.max_iterations):
            response = self.llm.complete(self.history)
            tool_calls = self.parse_tool_calls(response.content)
            
            if not tool_calls:
                return response.content  # Done!
            
            # Execute tools, add results to history, loop back
            for tc in tool_calls:
                result = self._execute_tool(tc)
                self.history.append(Message("user", f"Tool result: {result}"))
        
        return "Max iterations reached."
```

## How to Run

```bash
cd chapters/ch02_agent_loop
python agent_loop.py
```

The demo uses a `MockLLMClient` so no API key is needed. You'll see the full ReAct loop printed step by step.
