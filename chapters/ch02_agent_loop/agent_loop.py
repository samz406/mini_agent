"""Chapter 2: Agent Loop — ReAct Pattern.

Teaches: ReAct loop, tool call parsing, iteration control, message history.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator


# ---------------------------------------------------------------------------
# Minimal copies of ch01 primitives (kept local so each chapter is self-contained)
# ---------------------------------------------------------------------------

@dataclass
class Message:
    """A single conversation message."""

    role: str
    content: str

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


class BaseLLMClient(ABC):
    @abstractmethod
    def complete(self, messages: list[Message]) -> Message: ...

    @abstractmethod
    def stream(self, messages: list[Message]) -> Iterator[str]: ...


# ---------------------------------------------------------------------------
# Tool call data structure
# ---------------------------------------------------------------------------

@dataclass
class ToolCall:
    """Represents a parsed tool invocation from LLM output."""

    name: str
    args: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Agent Loop
# ---------------------------------------------------------------------------

class AgentLoop:
    """Implements the ReAct (Reason + Act) agent loop.

    Flow:
        1. LLM reasons and may emit TOOL_CALL directives.
        2. We parse and execute each tool call.
        3. We feed results back as new messages.
        4. Repeat until no tool calls or max_iterations reached.
    """

    TOOL_CALL_PREFIX = re.compile(r"TOOL_CALL:\s*")

    def __init__(self, llm_client: BaseLLMClient, max_iterations: int = 10) -> None:
        self.llm = llm_client
        self.max_iterations = max_iterations
        self.history: list[Message] = []

    def parse_tool_calls(self, text: str) -> list[ToolCall]:
        """Extract all TOOL_CALL directives from LLM output text.

        Expected format: TOOL_CALL: {"name": "tool_name", "args": {...}}

        Uses ``json.JSONDecoder.raw_decode`` to correctly handle nested braces.
        """
        calls: list[ToolCall] = []
        decoder = json.JSONDecoder()

        for match in self.TOOL_CALL_PREFIX.finditer(text):
            start = match.end()
            try:
                data, _ = decoder.raw_decode(text, start)
                name = data.get("name", "")
                args = data.get("args", {})
                if name:
                    calls.append(ToolCall(name=name, args=args))
            except json.JSONDecodeError as exc:
                print(f"  [warn] Failed to parse tool call JSON: {exc}")
        return calls

    def _execute_tool(self, tool_call: ToolCall) -> str:
        """Stub tool executor — replace with real tool registry in production."""
        print(f"  [tool] Executing: {tool_call.name}({tool_call.args})")
        # Real implementation would look up a tool registry here.
        return f"(stub result for {tool_call.name})"

    def run(self, user_input: str) -> str:
        """Run the ReAct loop for a user message. Returns the final response."""
        print(f"\n{'='*60}")
        print(f"USER: {user_input}")
        print(f"{'='*60}")

        self.history.append(Message(role="user", content=user_input))

        for iteration in range(1, self.max_iterations + 1):
            print(f"\n--- Iteration {iteration} ---")
            print("[think] Calling LLM...")

            response = self.llm.complete(self.history)
            self.history.append(Message(role="assistant", content=response.content))

            print(f"[llm]   {response.content}")

            tool_calls = self.parse_tool_calls(response.content)

            if not tool_calls:
                print("[done]  No tool calls found — returning final response.")
                return response.content

            print(f"[act]   Found {len(tool_calls)} tool call(s)")
            for tc in tool_calls:
                result = self._execute_tool(tc)
                observation = f"TOOL_RESULT: {tc.name} returned: {result}"
                print(f"[obs]   {observation}")
                self.history.append(Message(role="user", content=observation))

        print(f"[warn]  Reached max_iterations={self.max_iterations}, stopping.")
        return self.history[-1].content if self.history else "No response generated."


# ---------------------------------------------------------------------------
# Mock LLM for demo (no API key needed)
# ---------------------------------------------------------------------------

class MockLLMClient(BaseLLMClient):
    """A scripted mock that simulates a multi-step agent interaction."""

    def __init__(self) -> None:
        self._step = 0
        self._responses = [
            (
                'I need to calculate 2 + 2 first.\n'
                'TOOL_CALL: {"name": "calculator", "args": {"expression": "2 + 2"}}'
            ),
            (
                'The result is 4. Now let me get the current time.\n'
                'TOOL_CALL: {"name": "get_time", "args": {}}'
            ),
            "The calculation result is 4 and I've retrieved the current time. I can now answer your question!",
        ]

    def complete(self, messages: list[Message]) -> Message:
        response = self._responses[min(self._step, len(self._responses) - 1)]
        self._step += 1
        return Message(role="assistant", content=response)

    def stream(self, messages: list[Message]) -> Iterator[str]:
        yield self.complete(messages).content


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mock_llm = MockLLMClient()
    agent = AgentLoop(llm_client=mock_llm, max_iterations=10)

    result = agent.run("What is 2 + 2, and what time is it?")

    print(f"\n{'='*60}")
    print("FINAL ANSWER:")
    print(result)
    print(f"{'='*60}")
