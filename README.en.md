<p align="center">
  <img src="https://img.shields.io/badge/version-0.1.0--dev-blue" alt="version">
  <img src="https://img.shields.io/badge/python-3.11+-green" alt="python">
  <img src="https://img.shields.io/badge/license-MIT-brightgreen" alt="license">
  <img src="https://img.shields.io/badge/context-1M%20tokens-orange" alt="context">
</p>

<h1 align="center">HarnessGenJ-dev</h1>
<p align="center">
  <strong>Adversarial Review &times; Progressive Disclosure &times; Harness Self-Improvement</strong><br>
  A purpose-built AI multi-role development framework<br>
  Inspired by OpenClaw · Claude Code · MetaGPT
</p>

<p align="center">
  <a href="#three-core-principles">Core Principles</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#role-system">Role System</a> •
  <a href="#configuration">Configuration</a>
</p>

---

## What Is This?

HarnessGenJ-dev is a **purpose-built AI development framework** — not a general-purpose chatbot. It assembles a team of specialized AI agents that collaborate around your project to complete development tasks.

**You describe the goal. The framework assembles the team, assigns roles, coordinates work, and accumulates experience.**

- 🎯 **Project Manager** — judges task type, dispatches to appropriate roles
- 🏗️ **Architect** — designs system architecture, produces ADR decision records
- 💻 **Developer** — writes code, runs tests, documents implementation experience
- 🔍 **Code Reviewer** — audits security, performance, and maintainability
- 🐛 **Bug Hunter** — boundary testing, race conditions, security vulnerabilities
- 📝 **Doc Writer** — maintains README, API docs, deployment guides

---

## Three Core Principles

<table>
  <tr>
    <td align="center" width="33%">
      <h3>⚔️ Adversarial Review</h3>
    </td>
    <td align="center" width="33%">
      <h3>📐 Progressive Disclosure</h3>
    </td>
    <td align="center" width="33%">
      <h3>🔄 Harness Self-Improvement</h3>
    </td>
  </tr>
  <tr>
    <td valign="top">
      Code is neither written nor reviewed by a single agent.<br><br>
      Developer writes → Reviewer audits → Bug Hunter attacks → Developer fixes.<br><br>
      <strong>Every line of code passes through multiple adversarial eyes.</strong><br><br>
      <em>A single agent reviewing its own code? That's not review — that's self-deception.</em>
    </td>
    <td valign="top">
      Context is not dumped into the model all at once.<br><br>
      L1 metadata (50 tokens) → L2 knowledge base (500 tokens) → L3 references (on demand).<br><br>
      <strong>Agents pull information as needed, rather than receiving it passively.</strong><br><br>
      <em>1M context window ≠ should fill 1M context window.</em>
    </td>
    <td valign="top">
      After every task, lessons learned are persisted to knowledge bases.<br><br>
      On the next dispatch, agents read the knowledge base first — understanding past decisions and pitfalls.<br><br>
      <strong>The team gets smarter with every task.</strong><br><br>
      <em>Traditional tools start from scratch each time. Harness carries experience across sessions.</em>
    </td>
  </tr>
</table>

---

### Why HarnessGenJ-dev?

| Dimension | Single Agent | HarnessGenJ-dev |
|-----------|:---------:|:---------------:|
| Code Generation | ✅ Can write | ✅ **Dedicated writer** + audit + test |
| Architecture | ⚠️ Mixed with code | ✅ **Dedicated designer** + ADR traceability |
| Code Review | ❌ Self-review | ✅ **Adversarial review** (Reviewer vs Developer) |
| Bug Hunting | ❌ Misses edge cases | ✅ **Dedicated attacker** finding hidden defects |
| Knowledge Accumulation | ❌ Re-scans each time | ✅ **Harness self-improvement** across sessions |
| Context Management | ❌ Dump everything in | ✅ **Progressive disclosure**, load on demand |
| Team Collaboration | ❌ Single role | ✅ **7 roles**, clear boundaries |

---

## Quick Start

### Prerequisites

- Python 3.11+
- LLM API Key (Anthropic Claude / OpenAI / DeepSeek)

### One-Command Bootstrap

```bash
git clone https://github.com/qbiong/HarnessGenJ-dev.git
cd HarnessGenJ-dev && python bootstrap.py
```

`bootstrap.py` handles: Python version check → virtual environment → dependency install → API key detection → dashboard launch.

### Manual Install

```bash
git clone https://github.com/qbiong/HarnessGenJ-dev.git
cd HarnessGenJ-dev
pip install -e .

# Set API Key (choose one)
export ANTHROPIC_API_KEY="sk-ant-..."   # Anthropic Claude
export OPENAI_API_KEY="sk-..."          # OpenAI / DeepSeek

# Start
hgj-dev web
```

Open http://localhost:8000 — first message auto-creates a project.

### First Experience

```
You: "Build me a TODO app"

PM:   "Got it! This is a full-stack project. Dispatching team:
       @architect Design the system architecture
       @developer Implement based on the design
       @code_reviewer Audit code quality"

Architect:  [Outputs ADR + module design]
Developer:  [Writes code + runs tests]
Reviewer:   [Finds 3 issues → Developer fixes → Review passes]
Bug Hunter: [5 boundary tests → All pass]

PM:   "✅ All done. TODO app is ready.
       141 tests, 100% pass rate, docs updated."
```

---

## Core Concepts

### Harness Knowledge Management

Each role maintains a **6-section knowledge base** as its Single Source of Truth:

```
.project-knowledge/
├── project_status.md          ← PM global progress index
├── product_manager/
│   └── requirements.md        ← Requirements (What/Why)
├── architect/
│   ├── design.md              ← Architecture (How)
│   └── adrs/                  ← Architecture Decision Records
├── developer/
│   └── notes.md               ← Implementation experience & gotchas ⭐
├── code_reviewer/
│   └── reports.md             ← Review findings & quality trends
├── bug_hunter/
│   └── findings.md            ← Bug patterns & test strategies
└── doc_writer/
    └── docs.md                ← Documentation coverage & history
```

**6-section template**: Project Context → Completed Work → Decision Records → Lessons Learned → Cross-role Alignment → Todos/Blockers

**Progressive accumulation**: After each task, lessons are appended to the knowledge base. On the next dispatch, agents read the knowledge base first — the team grows smarter over time.

### 3-Layer Progressive Disclosure

| Layer | Content | Token Cost |
|:----:|---------|:---------:|
| L1 | Role metadata (id + description) | ~50 |
| L2 | Full knowledge base (6-section template) | ~500 |
| L3 | Reference files (ADRs / review reports / test results) | On demand |

### Role System

Every role has a defined **Domain** and **Hard Boundaries (must_not)**:

```
PM ──dispatches──→ Product Manager (defines What/Why)
    │              ├─ Architect (designs How)
    │              ├─ Developer (implements)
    │              ├─ Code Reviewer (audits)
    │              ├─ Bug Hunter (attacks)
    │              └─ Doc Writer (documents)
```

| Role | Domain | Knowledge Base | Never Does |
|------|--------|:-------------:|------------|
| PM | Team coordination, dispatch, progress | `project_status.md` | Write code, design, requirements |
| Product Manager | Requirements (What/Why) | `requirements.md` | Write code, design How, dispatch |
| Architect | System design (How), tech selection | `design.md` | Write implementation code |
| Developer | Implementation, tests, bug fixes | `notes.md` | Architecture decisions, requirements |
| Reviewer | Code quality, security, performance | `reports.md` | Modify code |
| Bug Hunter | Boundary testing, security flaws | `findings.md` | Fix bugs |
| Doc Writer | README, API docs, deployment guides | `docs.md` | Modify business logic |

Product Manager defines What/Why, Architect designs How, Developer implements — **these three never cross.**

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Web Dashboard                    │
│         FastAPI + WebSocket · SPA frontend        │
├─────────────────────────────────────────────────┤
│                Agent ReAct Loop                   │
│     Thought → Action → Observation → Repeat      │
├─────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ LLM      │ │ Tool     │ │ Role Registry &  │ │
│  │ Gateway  │ │ Registry │ │ Knowledge Base   │ │
│  │ DeepSeek │ │ File ops │ │ PM/PDM/AR/DV/RV/ │ │
│  │ Claude   │ │ Shell    │ │ BH/DW · 6-section│ │
│  │ OpenAI   │ │ Search   │ │ Harness template │ │
│  └──────────┘ └──────────┘ └──────────────────┘ │
├─────────────────────────────────────────────────┤
│      Plugin System · Hooks · Sessions · MCP      │
└─────────────────────────────────────────────────┘
```

### Project Structure

```
src/harnessgenj_dev/
├── core/              # Agent ReAct loop & system prompts
├── llm/               # Multi-provider LLM gateway
├── web/               # Web Dashboard (FastAPI + WebSocket SPA)
├── tools/             # File/Shell/Search/Test/Git tools
├── memory/            # Role registry & Harness knowledge
├── scanner/           # Project scanning & AST analysis
├── executor/          # Secure sandboxed code execution
└── plugins/           # Hooks plugin system
```

---

## Configuration

Settings are stored in `~/.hgj-dev/web_settings.json` and can be modified from the Settings tab:

| Setting | Description | Default |
|---------|-------------|---------|
| `provider` | LLM provider | deepseek |
| `model` | Model name | deepseek-v4-flash |
| `api_key` | API key | From environment variable |
| `base_url` | Custom API endpoint | Provider default |
| `user_title` | How agents address the user | 用户 |

### Supported LLM Providers

| Provider | Environment Variable | Notes |
|----------|---------------------|-------|
| DeepSeek | `OPENAI_API_KEY` | Default, 1M context window |
| Anthropic Claude | `ANTHROPIC_API_KEY` | Claude Opus/Sonnet/Haiku |
| OpenAI | `OPENAI_API_KEY` | GPT-4o series |
| OpenRouter | `OPENAI_API_KEY` | Unified API gateway |
| Qwen | `OPENAI_API_KEY` | Via compatible endpoint |
| Zhipu GLM | `OPENAI_API_KEY` | Via compatible endpoint |

---

## Development

```bash
pip install -e ".[dev]"
ruff check .              # Code lint
pytest                    # Run tests
```

---

## Inspired By

- [OpenClaw](https://github.com/openclaw/openclaw) — Gateway routing & progressive disclosure
- [Claude Code](https://claude.ai/code) — SKILL.md pattern & agent tool use
- [MetaGPT](https://github.com/geekan/MetaGPT) — Multi-role SOP-based collaboration

---

## License

MIT
