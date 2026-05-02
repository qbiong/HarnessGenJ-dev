"""CLI entry point for HarnessGenJ-dev."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from .config import AppConfig

if TYPE_CHECKING:
    from .core.agent import Agent


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="hgj-dev",
        description="HarnessGenJ-dev - AI-driven multi-role development assistant",
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s 0.1.0-dev"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug mode with full tracebacks"
    )

    subparsers = parser.add_subparsers(dest="command")

    # init
    init_parser = subparsers.add_parser("init", help="Initialize project configuration")
    init_parser.add_argument(
        "--path", default=".", help="Project root path (default: current directory)"
    )

    # develop
    dev_parser = subparsers.add_parser("develop", help="Start development session")
    dev_parser.add_argument("prompt", nargs="?", help="One-shot prompt (omit for interactive mode)")
    dev_parser.add_argument(
        "--role",
        default="developer",
        help="Role: developer/code_reviewer/bug_hunter/architect/product_manager/doc_writer",
    )
    dev_parser.add_argument("--model", help="Override default model")
    dev_parser.add_argument("--provider", help="Override default provider (anthropic, openai)")
    dev_parser.add_argument("--api-key", help="API key (or set env var)")
    dev_parser.add_argument(
        "--effort",
        default="medium",
        choices=["low", "medium", "high", "xhigh", "max"],
        help="Effort level (affects iterations, temperature)",
    )
    dev_parser.add_argument("--max-iterations", type=int, default=None, help="Max ReAct iterations (overrides effort)")

    # review
    review_parser = subparsers.add_parser("review", help="Review code")
    review_parser.add_argument("target", nargs="?", help="File or directory to review")

    # status
    subparsers.add_parser("status", help="Show project status")

    # web
    web_parser = subparsers.add_parser("web", help="Start Web Dashboard")
    web_parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    web_parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    web_parser.add_argument("--reload", action="store_true", help="Enable auto-reload on code changes")

    # help
    subparsers.add_parser("help", help="Show this help message")

    # session
    session_parser = subparsers.add_parser("session", help="Manage sessions")
    session_sub = session_parser.add_subparsers(dest="session_cmd")
    session_sub.add_parser("list", help="List all sessions")
    session_sub.add_parser("current", help="Show current session")
    session_delete = session_sub.add_parser("delete", help="Delete a session")
    session_delete.add_argument("session_id", help="Session ID to delete")
    session_restore = session_sub.add_parser("restore", help="Restore a session")
    session_restore.add_argument("session_id", help="Session ID to restore")

    # tools
    tools_parser = subparsers.add_parser("tools", help="List and query tools")
    tools_parser.add_argument("--name", help="Show details for specific tool")
    tools_parser.add_argument("--category", help="Filter by category (git, file, test, search, edit)")

    # config
    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_parser.add_argument("--show", action="store_true", help="Show current config")
    config_parser.add_argument("--validate", action="store_true", help="Validate config file")

    return parser


def _print_banner() -> None:
    """Print startup banner."""
    print("=" * 50)
    print("  HarnessGenJ-dev v0.1.0-dev")
    print("  AI-driven multi-role development assistant")
    print("=" * 50)
    print()


def _cmd_init(args: argparse.Namespace) -> int:
    """Initialize project configuration.

    Args:
        args: Parsed arguments with 'path'.

    Returns:
        Exit code (0 = success).
    """
    project_path = Path(args.path).resolve()
    config_dir = Path.home() / ".hgj-dev"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.yaml"

    if config_file.exists():
        print(f"Config already exists at: {config_file}")
        print("Delete it first to re-initialize.")
        return 1

    # Create default config
    config = AppConfig()
    try:
        config.save(str(config_file))
        print(f"Initialized HarnessGenJ-dev config at: {config_file}")
        print(f"Project path: {project_path}")
        print()
        print("Edit the config file to customize settings, then run:")
        print("  hgj-dev develop 'your prompt'")
        return 0
    except Exception as exc:
        print(f"Error creating config: {exc}", file=sys.stderr)
        return 1


def _cmd_develop(args: argparse.Namespace) -> int:
    """Run development session (one-shot or interactive).

    Args:
        args: Parsed arguments.

    Returns:
        Exit code.
    """
    _print_banner()

    # Load config
    config = AppConfig.load()

    # Override from CLI args
    provider = args.provider or config.llm.provider
    model = args.model or config.llm.model
    api_key = args.api_key or config.llm.api_key

    if not api_key:
        # Try env vars
        if provider == "anthropic":
            import os
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        elif provider == "openai":
            import os
            api_key = os.environ.get("OPENAI_API_KEY", "")

    # Initialize components
    from .core.agent import Agent
    from .llm.gateway import LLMGateway
    from .tools.registry import auto_register

    # Auto-register all tools
    auto_register()

    # Initialize LLM Gateway
    gateway = LLMGateway(
        provider=provider,
        model=model,
        api_key=api_key,
        max_retries=config.llm.max_retries,
        retry_base_delay=config.llm.retry_base_delay,
        retry_max_delay=config.llm.retry_max_delay,
    )

    # Initialize Agent
    agent = Agent(
        llm_gateway=gateway,
        config=config,
    )
    agent.state.max_iterations = args.max_iterations

    if args.prompt:
        # One-shot mode
        return asyncio.run(_run_oneshot(agent, args.prompt, args.role))
    else:
        # Interactive REPL mode
        return asyncio.run(_run_repl(agent, args.role))


async def _run_oneshot(agent: Agent, prompt: str, role: str) -> int:
    """Run agent with a single prompt.

    Args:
        agent: Initialized agent instance.
        prompt: User prompt.
        role: Role for this session.

    Returns:
        Exit code.
    """

    # If no API key, use mock mode for testing
    if not agent.llm_gateway.api_key:
        print("Warning: No API key provided. Running in mock mode.")
        print(f"Role: {role}")
        print(f"Prompt: {prompt}")
        print()

        # Show available tools
        from .tools.registry import get_tool_list
        tools = get_tool_list()
        if tools:
            print(f"Available tools ({len(tools)}):")
            for t in tools:
                print(f"  - {t['name']}: {t['description']}")
        print()
        print("To use real LLM, set ANTHROPIC_API_KEY or OPENAI_API_KEY env var,")
        print("or use --api-key flag.")
        return 0

    print(f"Role: {role}")
    print(f"Prompt: {prompt}")
    print()
    print("Thinking...")
    print("-" * 40)

    try:
        result = await agent.run(prompt, role=role)
        print(result)
        return 0
    except KeyboardInterrupt:
        agent.interrupt()
        print("\nInterrupted.")
        return 130
    except Exception as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        return 1


async def _run_repl(agent: Agent, role: str) -> int:
    """Run interactive REPL loop.

    Args:
        agent: Initialized agent instance.
        role: Role for this session.

    Returns:
        Exit code.
    """
    from .tools.registry import get_tool_list

    # Show available tools
    tools = get_tool_list()
    if tools:
        print(f"Available tools ({len(tools)}):")
        for t in tools:
            print(f"  - {t['name']}: {t['description']}")
        print()

    print("Enter your prompt (or 'quit' to exit, 'help' for commands):")
    print()

    while True:
        try:
            # Use asyncio.to_thread for blocking input
            user_input = await asyncio.to_thread(input, "hgj-dev> ")
        except EOFError:
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        # Built-in commands
        if user_input.lower() in ("quit", "exit", "q"):
            print("Bye!")
            break
        elif user_input.lower() in ("help", "h"):
            print("Commands:")
            print("  quit/exit/q  - Exit")
            print("  help/h       - Show this help")
            print("  tools        - List available tools")
            print("  clear        - Clear conversation history")
            print("  role <name>  - Switch role")
            print()
            continue
        elif user_input.lower() == "tools":
            tools = get_tool_list()
            for t in tools:
                print(f"  - {t['name']}: {t['description']}")
            print()
            continue
        elif user_input.lower() == "clear":
            agent.state.conversation_history.clear()
            agent.state.iteration_count = 0
            print("Conversation cleared.")
            print()
            continue
        elif user_input.lower().startswith("role "):
            new_role = user_input.split(" ", 1)[1].strip()
            role = new_role
            print(f"Role switched to: {role}")
            print()
            continue

        # Send to agent
        try:
            result = await agent.run(user_input, role=role)
            print()
            print(result)
            print()
            print("-" * 40)
        except KeyboardInterrupt:
            agent.interrupt()
            print("\nInterrupted.")
        except Exception as exc:
            print(f"\nError: {exc}", file=sys.stderr)
        print()

    return 0


def _cmd_web(args: argparse.Namespace) -> int:
    """Start Web Dashboard.

    Args:
        args: Parsed arguments with 'host', 'port', 'reload'.

    Returns:
        Exit code.
    """
    import uvicorn

    _print_banner()
    print(f"Starting Web Dashboard on {args.host}:{args.port}")
    if args.reload:
        print("Auto-reload: enabled")
    print()
    print(f"Open http://{args.host}:{args.port} in your browser")
    print()

    if args.reload:
        # reload mode requires import string
        uvicorn.run(
            "harnessgenj_dev.web.dashboard:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level="info",
        )
    else:
        from .web.dashboard import app

        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            reload=False,
            log_level="info",
        )
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    """Show project status.

    Args:
        args: Parsed arguments.

    Returns:
        Exit code.
    """
    print("HarnessGenJ-dev Status")
    print("=" * 30)

    # Show config status
    config_file = Path.home() / ".hgj-dev" / "config.yaml"
    if config_file.exists():
        print(f"Config: {config_file} (exists)")
    else:
        print("Config: Not initialized (run 'hgj-dev init')")

    # Show tool count
    from .tools.registry import auto_register, get_tool_list
    auto_register()
    tools = get_tool_list()
    print(f"Tools registered: {len(tools)}")

    # Show test summary (discover actual test count)
    test_count = 0
    test_root = Path(__file__).parent.parent / "tests"
    if test_root.exists():
        test_count = len(list(test_root.rglob("test_*.py")))
    print(f"Test files: {test_count} (run 'pytest' for details)")
    return 0


def _cmd_session(args: argparse.Namespace) -> int:
    """Manage sessions (list, delete, restore).

    Args:
        args: Parsed arguments with session_cmd.

    Returns:
        Exit code.
    """
    from .web.session_manager import SessionManager

    manager = SessionManager()
    project = "default"

    if args.session_cmd == "list":
        sessions = manager.list_sessions(project)
        if not sessions:
            print("No sessions found.")
            return 0
        print(f"Sessions ({len(sessions)}):")
        print("-" * 60)
        for s in sessions:
            active = " [ACTIVE]" if s.get('active') else ""
            created = s.get('created_at', 'N/A')
            print(f"  {s['id'][:8]}... | {s['role']} | {created[:16]}{active}")
            if s.get('title'):
                print(f"    Title: {s['title']}")
        return 0

    elif args.session_cmd == "current":
        session = manager.get_active_session(project)
        if not session:
            print("No active session.")
            return 1
        print(f"Session ID: {session.id}")
        print(f"Role: {session.role}")
        print(f"Created: {session.created_at}")
        print(f"Title: {session.title or '(no title)'}")
        print(f"Messages: {len(session.messages)}")
        return 0

    elif args.session_cmd == "delete":
        success = manager.delete_session(project, args.session_id)
        if success:
            print(f"Deleted session: {args.session_id[:8]}...")
            return 0
        else:
            print(f"Session not found: {args.session_id[:8]}...")
            return 1

    return 0


def _cmd_tools(args: argparse.Namespace) -> int:
    """List and query tools.

    Args:
        args: Parsed arguments with --name and --category.

    Returns:
        Exit code.
    """
    from .tools.registry import auto_register, get_tool, get_tool_list

    # Register tools first
    auto_register()

    # Show specific tool details
    if args.name:
        tool = get_tool(args.name)
        if tool:
            print(f"Tool: {tool.name}")
            print(f"Description: {tool.description}")
            print(f"Category: {getattr(tool, 'category', 'N/A')}")
            schema = tool.schema()
            params = schema.get('parameters', {}).get('properties', {})
            required = schema.get('parameters', {}).get('required', [])
            if params:
                print("Parameters:")
                for name, spec in params.items():
                    req = " (required)" if name in required else ""
                    print(f"  - {name}: {spec.get('type', 'any')}{req}")
            else:
                print("Parameters: None")
            return 0
        else:
            print(f"Tool not found: {args.name}")
            return 1

    # List all tools
    tools = get_tool_list()

    # Filter by category
    if args.category:
        tools = [t for t in tools if t.get('category', '').lower() == args.category.lower()]

    if not tools:
        print("No tools found.")
        return 0

    print(f"Tools ({len(tools)}):")
    if args.category:
        print(f"Category: {args.category}")
    print("-" * 60)
    for t in tools:
        cat = t.get('category', 'N/A')
        print(f"  {t['name']:<20} [{cat:<8}] {t['description'][:50]}")
    return 0


def _cmd_config(args: argparse.Namespace) -> int:
    """Manage configuration.

    Args:
        args: Parsed arguments with --show and --validate.

    Returns:
        Exit code.
    """
    config_file = Path.home() / ".hgj-dev" / "config.yaml"

    if args.show:
        if not config_file.exists():
            print("No config file found. Run 'hgj-dev init' first.")
            return 1
        print(f"Config file: {config_file}")
        print("-" * 40)
        with open(config_file) as f:
            print(f.read())
        return 0

    if args.validate:
        if not config_file.exists():
            print("No config file found.")
            return 1
        try:
            config = AppConfig.load()
            print("Config is valid.")
            print(f"  Provider: {config.llm.provider}")
            print(f"  Model: {config.llm.model}")
            print(f"  Max retries: {config.llm.max_retries}")
            return 0
        except Exception as exc:
            print(f"Config validation failed: {exc}")
            return 1

    # Default: show help
    print("Config commands:")
    print("  --show       Show current config")
    print("  --validate   Validate config file")
    return 0


def main() -> None:
    """Main entry point for hgj-dev CLI."""
    parser = _build_parser()
    args = parser.parse_args()

    # Handle global debug flags
    if args.debug:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    elif args.verbose:
        import logging
        logging.basicConfig(level=logging.INFO)

    if not args.command or args.command == "help":
        parser.print_help()
        return

    command_map = {
        "init": _cmd_init,
        "develop": _cmd_develop,
        "status": _cmd_status,
        "review": _cmd_develop,  # review uses same logic as develop with review role
        "web": _cmd_web,
        "session": _cmd_session,
        "tools": _cmd_tools,
        "config": _cmd_config,
    }

    handler = command_map.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    exit_code = handler(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
