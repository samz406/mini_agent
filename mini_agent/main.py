"""mini_agent.main — CLI entry point with a rich interactive interface."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.status import Status
from rich.text import Text

from mini_agent.config import AgentConfig
from mini_agent.core.context import ContextManager
from mini_agent.core.llm import OpenAICompatibleClient
from mini_agent.core.loop import AgentEvent, AgentLoop
from mini_agent.core.prompt import PromptBuilder
from mini_agent.memory.conversation import ConversationMemory
from mini_agent.memory.persistent import PersistentMemory
from mini_agent.providers import get_provider, list_providers
from mini_agent.tools.base import GLOBAL_REGISTRY

# Ensure built-in tools are registered
import mini_agent.tools.builtins  # noqa: F401

console = Console()


class MiniAgent:
    """High-level agent facade that wires all components together."""

    def __init__(self, config: Optional[AgentConfig] = None) -> None:
        self.config = config or AgentConfig.from_env()

        # Set up persistent memory file for builtins
        from mini_agent.tools.builtins import init_memory
        init_memory(self.config.memory_file)

        # Core components
        self.llm = OpenAICompatibleClient(self.config)
        self.tool_registry = GLOBAL_REGISTRY
        self.conversation = ConversationMemory(max_size=self.config.max_context_tokens // 100)
        self.persistent_memory = PersistentMemory(filepath=self.config.memory_file)
        self.context_manager = ContextManager(max_tokens=self.config.max_context_tokens)
        self.prompt_builder = PromptBuilder(self.config)

        self.loop = AgentLoop(
            config=self.config,
            llm_client=self.llm,
            tool_registry=self.tool_registry,
            memory=self.conversation,
            context_manager=self.context_manager,
            prompt_builder=self.prompt_builder,
            on_event=self._on_event,
        )

    def _on_event(self, event: AgentEvent, data: dict) -> None:
        """Rich-formatted event handler."""
        if event == AgentEvent.THINKING:
            pass  # Spinner is shown by the caller
        elif event == AgentEvent.TOOL_CALL:
            console.print(
                Panel(
                    f"[bold cyan]{data['name']}[/bold cyan]\n[dim]{data['arguments']}[/dim]",
                    title="[yellow]🔧 Tool Call[/yellow]",
                    border_style="yellow",
                    expand=False,
                )
            )
        elif event == AgentEvent.TOOL_RESULT:
            result_text = data["result"]
            if len(result_text) > 300:
                result_text = result_text[:300] + "…"
            console.print(
                Panel(
                    f"[green]{result_text}[/green]",
                    title=f"[dim]✓ {data['name']} result[/dim]",
                    border_style="dim green",
                    expand=False,
                )
            )
        elif event == AgentEvent.ERROR:
            console.print(f"[red]⚠ {data.get('message', 'Unknown error')}[/red]")

    def run(self, user_input: str) -> str:
        """Process user input and return the agent's response."""
        return self.loop.run(user_input)

    def clear_memory(self) -> None:
        """Clear the conversation history."""
        self.conversation.clear()

    def get_memory_summary(self) -> dict:
        """Return all persistent memory entries."""
        return self.persistent_memory.get_all()

    def list_tools(self) -> list[str]:
        """Return names of all registered tools."""
        return [t.name for t in self.tool_registry.list_tools()]


# ---------------------------------------------------------------------------
# Interactive REPL
# ---------------------------------------------------------------------------

COMMANDS = {
    "/quit": "Exit the agent",
    "/exit": "Exit the agent",
    "/clear": "Clear conversation history",
    "/memory": "Show persistent memory contents",
    "/tools": "List available tools",
    "/provider": "Show current provider or list all providers",
    "/providers": "List all supported LLM providers",
    "/help": "Show this help message",
}


def _print_help() -> None:
    lines = ["[bold]Available commands:[/bold]"]
    for cmd, desc in COMMANDS.items():
        lines.append(f"  [cyan]{cmd:<10}[/cyan] {desc}")
    console.print("\n".join(lines))


def _print_providers(current_config: Optional["AgentConfig"] = None) -> None:
    """Print the supported providers and highlight the active one."""
    lines: list[str] = []
    for p in list_providers():
        active = (
            current_config is not None
            and current_config.provider.lower() == p.name.lower()
        )
        marker = " [bold green]← active[/bold green]" if active else ""
        lines.append(
            f"  [cyan]{p.name:<10}[/cyan]  {p.description}\n"
            f"             api_base=[dim]{p.api_base}[/dim]  key_env=[dim]{p.key_env_var}[/dim]{marker}"
        )
    console.print(Panel("\n".join(lines), title="Supported LLM Providers", border_style="cyan"))


def run_interactive(agent: MiniAgent) -> None:
    """Run the interactive REPL loop."""
    console.print(
        Panel(
            Text.from_markup(
                "[bold blue]Mini Agent[/bold blue]\n"
                "[dim]A production-grade AI agent — built for learning[/dim]\n\n"
                f"[dim]Provider:[/dim] [cyan]{agent.config.provider}[/cyan]   "
                f"[dim]Model:[/dim] [cyan]{agent.config.model}[/cyan]   "
                f"[dim]Tools:[/dim] [cyan]{len(agent.list_tools())}[/cyan]   "
                "[dim]Type[/dim] [cyan]/help[/cyan] [dim]for commands[/dim]"
            ),
            border_style="blue",
            padding=(1, 4),
        )
    )

    while True:
        try:
            user_input = console.input("[bold green]You:[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not user_input:
            continue

        # --- Commands ---
        if user_input.lower() in ("/quit", "/exit"):
            console.print("[dim]Goodbye![/dim]")
            break

        if user_input.lower() == "/clear":
            agent.clear_memory()
            console.print("[green]Conversation memory cleared.[/green]")
            continue

        if user_input.lower() == "/memory":
            data = agent.get_memory_summary()
            if data:
                lines = "\n".join(f"  [cyan]{k}[/cyan]: {v}" for k, v in data.items())
                console.print(Panel(lines, title="Persistent Memory", border_style="cyan"))
            else:
                console.print("[dim]No persistent memory entries.[/dim]")
            continue

        if user_input.lower() == "/tools":
            tool_list = "\n".join(
                f"  [cyan]{t.name}[/cyan]: {t.description}"
                for t in agent.tool_registry.list_tools()
            )
            console.print(Panel(tool_list, title="Available Tools", border_style="cyan"))
            continue

        if user_input.lower() in ("/provider", "/providers"):
            _print_providers(agent.config)
            continue

        if user_input.lower() == "/help":
            _print_help()
            continue

        # --- Agent call ---
        with Status("[bold yellow]Thinking…[/bold yellow]", console=console):
            try:
                response = agent.run(user_input)
            except Exception as exc:
                console.print(f"[red]Error: {exc}[/red]")
                continue

        console.print()
        console.print("[bold blue]Assistant:[/bold blue]")
        console.print(Markdown(response))
        console.print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Parse CLI arguments and launch the interactive agent."""
    parser = argparse.ArgumentParser(
        description="Mini Agent — an interactive AI agent built for learning.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--model", help="LLM model name (overrides MINI_AGENT_MODEL)")
    parser.add_argument("--api-base", dest="api_base", help="API base URL (overrides MINI_AGENT_API_BASE)")
    parser.add_argument(
        "--provider",
        help=(
            "LLM provider name: openai, qwen, kimi, minimax, deepseek, glm "
            "(overrides MINI_AGENT_PROVIDER)"
        ),
    )
    parser.add_argument("--system-prompt", dest="system_prompt", help="Custom system prompt")

    args = parser.parse_args()

    config = AgentConfig.from_env()
    if args.provider:
        provider_cfg = get_provider(args.provider)
        if provider_cfg is None:
            console.print(f"[red]Unknown provider '{args.provider}'. Run /providers to see options.[/red]")
            sys.exit(1)
        config.provider = args.provider.lower()
        # Apply provider defaults only when not already explicitly overridden
        if not args.api_base:
            config.api_base = provider_cfg.api_base
        if not config.api_key:
            config.api_key = os.getenv(provider_cfg.key_env_var, "")
        if not args.model:
            config.model = provider_cfg.default_model
    if args.model:
        config.model = args.model
    if args.api_base:
        config.api_base = args.api_base
    if args.system_prompt:
        config.system_prompt = args.system_prompt

    if not config.api_key:
        p = get_provider(config.provider)
        key_var = p.key_env_var if p else "OPENAI_API_KEY"
        console.print(
            f"[yellow]Warning: API key not set. "
            f"Set it via the [bold]{key_var}[/bold] environment variable or a .env file.[/yellow]"
        )

    agent = MiniAgent(config=config)
    run_interactive(agent)


if __name__ == "__main__":
    main()
