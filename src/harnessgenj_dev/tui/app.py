"""Textual-based TUI application."""

from __future__ import annotations

import asyncio
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Input, Label, RichLog, Static

from ..config import AppConfig


class HGJDevApp(App):
    """HarnessGenJ-dev TUI application.

    Provides an interactive chat interface with the AI agent.
    """

    CSS = """
    Screen {
        layout: vertical;
    }

    #title-bar {
        dock: top;
        height: 1;
        background: $primary;
        color: $text;
        text-align: center;
    }

    #status-bar {
        dock: top;
        height: 1;
        background: $surface;
    }

    #output-log {
        flex: 1;
        background: $boost;
    }

    #input-area {
        dock: bottom;
        height: 3;
        background: $surface;
    }

    #prompt-label {
        dock: left;
        width: auto;
        content-align: left middle;
        padding: 0 1;
        color: $primary;
    }

    Input {
        width: 1fr;
    }
    """

    def __init__(self, config: AppConfig | None = None) -> None:
        super().__init__()
        self.config = config or AppConfig()
        self.role = "developer"
        self.agent: Any = None
        self._task: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        """Build the UI layout."""
        yield Header()
        yield Static("HarnessGenJ-dev v0.1.0-dev", id="title-bar")
        yield Static(f"Role: {self.role} | Model: {self.config.llm.model}", id="status-bar")
        yield RichLog(id="output-log", highlight=True, markup=True)
        with Horizontal(id="input-area"):
            yield Label("hgj-dev> ", id="prompt-label")
            yield Input(placeholder="Type your prompt... (quit to exit)", id="prompt-input")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize on mount."""
        log = self.query_one("#output-log", RichLog)
        log.write("[bold green]Welcome to HarnessGenJ-dev![/]\n")
        log.write("Type your prompt and press Enter.\n")
        log.write("Commands: quit, help, tools, role <name>, clear\n")
        log.write("[dim]─" * 50 + "[/]\n")

        # Initialize agent
        self._init_agent()

        self.query_one("#prompt-input", Input).focus()

    def _init_agent(self) -> None:
        """Initialize the agent and tools."""
        from ..core.agent import Agent
        from ..llm.gateway import LLMGateway
        from ..tools.registry import auto_register

        auto_register()

        gateway = LLMGateway(
            provider=self.config.llm.provider,
            model=self.config.llm.model,
            api_key=self.config.llm.api_key,
        )

        self.agent = Agent(llm_gateway=gateway, config=self.config)

        log = self.query_one("#output-log", RichLog)
        from ..tools.registry import get_tool_list

        tools = get_tool_list()
        if tools:
            log.write(f"[bold]Tools available:[/bold] {len(tools)}")
            for t in tools:
                log.write(f"  • {t['name']}: {t['description']}")
            log.write("")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        user_input = event.value.strip()
        input_widget = self.query_one("#prompt-input", Input)
        input_widget.value = ""

        if not user_input:
            return

        log = self.query_one("#output-log", RichLog)

        # Handle commands
        if user_input.lower() in ("quit", "exit", "q"):
            log.write("\n[dim]Bye![/]\n")
            self.exit()
            return

        if user_input.lower() in ("help", "h"):
            log.write("\n[bold]Commands:[/bold]")
            log.write("  quit/exit/q  - Exit")
            log.write("  help/h       - Show this help")
            log.write("  tools        - List available tools")
            log.write("  clear        - Clear conversation")
            log.write("  role <name>  - Switch role")
            log.write("  status       - Show agent status")
            log.write("")
            return

        if user_input.lower() == "tools":
            from ..tools.registry import get_tool_list

            tools = get_tool_list()
            log.write(f"\n[bold]Available tools ({len(tools)}):[/bold]")
            for t in tools:
                log.write(f"  • {t['name']}: {t['description']}")
            log.write("")
            return

        if user_input.lower() == "clear":
            self.agent.state.conversation_history.clear()
            self.agent.state.iteration_count = 0
            log.clear()
            log.write("[dim]Conversation cleared.[/]\n")
            return

        if user_input.lower().startswith("role "):
            new_role = user_input.split(" ", 1)[1].strip()
            self.role = new_role
            status = self.query_one("#status-bar", Static)
            status.update(f"Role: {self.role} | Model: {self.config.llm.model}")
            log.write(f"[dim]Role switched to: {self.role}[/]\n")
            return

        if user_input.lower() == "status":
            log.write("\n[bold]Status:[/bold]")
            log.write(f"  Iterations: {self.agent.state.iteration_count}")
            log.write(f"  Messages: {len(self.agent.state.conversation_history)}")
            log.write(f"  Running: {self.agent.state.is_running}")
            stats = self.agent.llm_gateway.get_usage_stats()
            if stats.total_tokens > 0:
                log.write(f"  Tokens: {stats.total_tokens} (${stats.estimated_cost:.4f})")
            log.write("")
            return

        # Send to agent
        log.write(f"\n[bold cyan]You:[/bold cyan] {user_input}\n")
        log.write("[dim]Thinking...[/dim]\n")

        try:
            result = await self.agent.run(user_input, role=self.role)
            log.write(f"\n[bold green]Agent:[/bold green] {result}\n")
            log.write("[dim]─" * 50 + "[/]\n")

            # Show usage stats
            stats = self.agent.llm_gateway.get_usage_stats()
            if stats.total_tokens > 0:
                log.write(
                    f"[dim]Tokens: {stats.total_tokens} | "
                    f"Cost: ${stats.estimated_cost:.4f} | "
                    f"Iterations: {self.agent.state.iteration_count}[/dim]\n"
                )
        except Exception as exc:
            log.write(f"\n[bold red]Error:[/bold red] {exc}\n")

        input_widget.focus()


def run_app() -> None:
    """Launch the interactive TUI."""
    config = AppConfig.load()
    app = HGJDevApp(config=config)
    app.run()
