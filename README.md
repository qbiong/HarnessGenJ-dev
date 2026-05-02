# HarnessGenJ-dev

AI-driven multi-role development assistant — a standalone development tool similar to Claude Code and OpenClaw, providing a web-based chat interface for project development with advanced AI collaboration capabilities.

## Features

- **Web Dashboard**: Browser-based chat interface with project management, file browser, and settings
- **Multi-Role Team**: Product Manager, Developer, Code Reviewer, Bug Hunter, Architect, Doc Writer
- **Adversarial Review**: Multi-role adversarial review to find bugs and improve code quality
- **Workspace Management**: Auto-create projects in `~/.hgj-dev/workspace/` or open external projects
- **Project Onboarding**: Auto-detection of empty projects with guided requirements discovery
- **Session Memory**: Persistent conversation history with session management
- **Multi-Provider LLM**: DeepSeek V4 (default), Anthropic Claude, OpenAI, and more
- **1M Context Window**: Optimized for DeepSeek V4's 1M token context window

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Initialize config
hgj-dev init

# Start web dashboard
hgj-dev web

# Or use CLI directly
hgj-dev develop "your prompt"
```

Open http://localhost:8000 in your browser.

## Configuration

Set up your LLM provider in the Settings page:
1. Choose Provider (DeepSeek recommended)
2. Enter API Key
3. Click "Test Connection" to verify

Settings stored in `~/.hgj-dev/web_settings.json`.

## Core Capabilities

| Capability | Description |
|-----------|-------------|
| Project Onboarding | Detects empty projects, guides requirements discovery, auto-generates PROJECT.md |
| Multi-Agent Dev | @mentions to dispatch tasks to specialized agent roles |
| Adversarial Review | Developer -> Reviewer -> BugHunter loop for code quality |
| Session Memory | Conversations persist across sessions, switch between sessions |
| Context Management | Three-tier compaction for large context windows (up to 1M tokens) |
| Workspace Isolation | Framework separated from user projects, clear boundary enforcement |

## Architecture

```
src/harnessgenj_dev/
├── core/              # Agent ReAct loop, system prompts, context manager
├── llm/               # LLM Gateway (DeepSeek/Claude/OpenAI + degradation + retry)
├── web/               # FastAPI + WebSocket dashboard (SPA frontend)
├── tools/             # File/shell/search/test/git tools
├── memory/            # Role memory & shared knowledge
├── scanner/           # Project scanning & AST analysis
├── executor/          # Code execution sandbox with security
├── plugins/           # Plugin system with hooks
├── projects.py        # Multi-project management
├── cli.py             # CLI entry point (init/develop/status/web)
└── config.py          # YAML-based configuration
```

## Development

```bash
pip install -e ".[dev]"
ruff check .              # Code lint
pytest                    # Run tests (768 tests)
```

## License

MIT
