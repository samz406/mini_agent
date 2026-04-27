"""mini_agent.core.loop — The main agent ReAct loop."""

from __future__ import annotations

import json
from enum import Enum, auto
from typing import Callable, Optional

from mini_agent.config import AgentConfig
from mini_agent.core.context import ContextManager
from mini_agent.core.llm import BaseLLMClient, LLMMessage, LLMResponse, ToolCall
from mini_agent.core.prompt import PromptBuilder
from mini_agent.memory.conversation import ConversationMemory
from mini_agent.tools.base import ToolRegistry


class AgentEvent(Enum):
    """Events emitted during an agent run."""

    THINKING = auto()
    TOOL_CALL = auto()
    TOOL_RESULT = auto()
    RESPONSE = auto()
    ERROR = auto()


class AgentLoop:
    """Implements the ReAct (Reason + Act) agent loop.

    Flow per iteration:
    1. Build messages (system prompt + conversation history).
    2. Trim to fit context window.
    3. Call LLM with tool schemas.
    4. If response has tool calls: execute each, add results, continue.
    5. If no tool calls: final answer — return content.
    6. If max_iterations exceeded: return last content.
    """

    def __init__(
        self,
        config: AgentConfig,
        llm_client: BaseLLMClient,
        tool_registry: ToolRegistry,
        memory: ConversationMemory,
        context_manager: ContextManager,
        prompt_builder: PromptBuilder,
        on_event: Optional[Callable[[AgentEvent, dict], None]] = None,
    ) -> None:
        self._config = config
        self._llm = llm_client
        self._tools = tool_registry
        self._memory = memory
        self._ctx = context_manager
        self._prompt = prompt_builder
        self.on_event = on_event

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, user_input: str) -> str:
        """Process *user_input* and return the agent's final response."""
        self._memory.add("user", user_input)

        tool_schemas = self._tools.to_openai_schemas()
        self._prompt.set_tools(tool_schemas)

        for iteration in range(self._config.max_iterations):
            self._emit(AgentEvent.THINKING, {"iteration": iteration + 1})

            # Build and trim the message list
            system_msg = self._prompt.get_system_message()
            history_dicts = self._memory.to_messages()
            all_messages_dicts = [system_msg] + history_dicts
            trimmed_dicts = self._ctx.trim(all_messages_dicts)

            messages = [LLMMessage(role=m["role"], content=m["content"]) for m in trimmed_dicts]

            # Call LLM
            response: LLMResponse = self._llm.complete(messages, tools=tool_schemas or None)

            # Handle tool calls
            if response.tool_calls:
                # Record assistant message with tool calls (content may be None)
                assistant_content = response.content or ""
                self._memory.add("assistant", assistant_content)

                for tc in response.tool_calls:
                    self._emit(AgentEvent.TOOL_CALL, {"name": tc.function.name, "arguments": tc.function.arguments})
                    result_str = self._execute_tool(tc)
                    self._emit(AgentEvent.TOOL_RESULT, {"name": tc.function.name, "result": result_str})

                    # Feed result back as a tool message
                    tool_result_content = json.dumps({"result": result_str})
                    self._memory.add("tool", tool_result_content)

                continue  # Next iteration: LLM processes tool results

            # No tool calls → final answer
            final_content = response.content or ""
            self._memory.add("assistant", final_content)
            self._emit(AgentEvent.RESPONSE, {"content": final_content})
            return final_content

        # Exhausted iterations
        last = "I've reached my maximum number of reasoning steps. Please try a simpler request."
        self._emit(AgentEvent.ERROR, {"message": "max_iterations exceeded"})
        return last

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _execute_tool(self, tool_call: ToolCall) -> str:
        """Look up and execute a tool, returning the result as a string."""
        name = tool_call.function.name
        tool = self._tools.get(name)
        if tool is None:
            return f"Error: Tool '{name}' not found."
        try:
            args: dict = json.loads(tool_call.function.arguments)
            result = tool.execute(**args)
            if result.success:
                return result.result
            return f"Tool error: {result.error}"
        except json.JSONDecodeError as exc:
            return f"Error parsing tool arguments: {exc}"
        except Exception as exc:
            return f"Tool execution error: {exc}"

    def _emit(self, event: AgentEvent, data: dict) -> None:
        """Fire the on_event callback if one is registered."""
        if self.on_event is not None:
            try:
                self.on_event(event, data)
            except Exception:
                pass
