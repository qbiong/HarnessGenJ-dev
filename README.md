# HarnessGenJ-dev

[English](#english) | [中文](#chinese)

---

<a name="chinese"></a>
## 中文

HarnessGenJ-dev 是一个 AI 驱动的多角色开发助手，参考了 OpenClaw 和 Claude Code 的架构设计。提供 Web 聊天界面，项目经理自动调度架构师、开发者、审查员、Bug猎人、文档编写者等角色协作完成开发任务。

### 特性

- **Web Dashboard**：浏览器聊天界面，集成项目管理、文件浏览、设置配置
- **多角色团队**：项目经理、产品经理、架构师、开发者、代码审查员、Bug猎人、文档编写者
- **Harness 知识管理**：6 段式渐进知识库，角色间自动对齐，跨会话经验积累
- **自动项目创建**：首次使用自动创建工作区项目，无需手动配置
- **对抗审查**：多角色对抗审查发现 Bug 并提升代码质量
- **会话持久化**：支持创建、切换、删除会话，历史记录不丢失
- **多 LLM 支持**：DeepSeek V4（默认）、Anthropic Claude、OpenAI 等
- **1M 上下文窗口**：针对 DeepSeek V4 的 1M Token 上下文优化

### 快速开始

```bash
# 方式一：一键启动（推荐）
git clone https://github.com/qbiong/HarnessGenJ-dev.git
cd HarnessGenJ-dev
python bootstrap.py

# 方式二：手动安装
git clone https://github.com/qbiong/HarnessGenJ-dev.git
cd HarnessGenJ-dev
pip install -e .

# 设置 API Key（二选一）
export ANTHROPIC_API_KEY="sk-ant-..."   # Anthropic Claude
export OPENAI_API_KEY="sk-..."          # OpenAI / DeepSeek
# 或启动后在 Web UI 设置页配置

# 启动
hgj-dev web
# 打开 http://localhost:8000 → 输入第一条消息 → 自动创建项目 → 开始工作
```

无需 `hgj-dev init`——项目首次使用时自动创建。API Key 可通过环境变量或 Web UI 设置页配置。

### 配置

所有配置存储在 `~/.hgj-dev/web_settings.json`，也可在 Web Dashboard 的设置页修改：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| Provider | LLM 提供商 | deepseek |
| Model | 模型名称 | deepseek-v4-flash |
| API Key | API 密钥 | 从环境变量读取 |
| Base URL | 自定义 API 地址 | 提供商默认 |
| User Title | Agent 对用户的称呼 | 用户 |

### 核心能力

| 能力 | 说明 |
|------|------|
| 自动项目初始化 | 检测空项目，引导需求发现，自动生成 PROJECT.md |
| @mention 派发 | PM 通过 @角色名 派发任务给专业 Agent |
| 对抗审查 | 开发者 → 审查员 → Bug猎人 质量闭环 |
| 渐进式知识库 | 6 段式 Harness 模板，跨会话经验积累 |
| 上下文管理 | 三级压缩，支持最高 1M Token 上下文 |
| 工作区隔离 | 框架与用户项目分离，路径白名单保护 |

### 架构

```
src/harnessgenj_dev/
├── core/              # Agent ReAct 循环、系统提示词、上下文管理
├── llm/               # LLM 网关（DeepSeek/Claude/OpenAI + 降级 + 重试）
├── web/               # FastAPI + WebSocket Dashboard（SPA 前端）
├── tools/             # 文件/Shell/搜索/测试/Git 工具
├── memory/            # 角色记忆 & 共享知识库
├── scanner/           # 项目扫描 & AST 分析
├── executor/          # 代码执行沙箱 & 安全
├── plugins/           # 插件系统 & Hooks
├── projects.py        # 多项目管理
├── cli.py             # CLI 入口（init/develop/status/web）
└── config.py          # YAML 配置
```

### 开发

```bash
pip install -e ".[dev]"
ruff check .              # 代码检查
pytest                    # 运行测试
```

### 许可

MIT

---

<a name="english"></a>
## English

HarnessGenJ-dev is an AI-driven multi-role development assistant inspired by OpenClaw and Claude Code. It provides a web-based chat interface where a Project Manager agent autonomously orchestrates specialized agents (Architect, Developer, Code Reviewer, Bug Hunter, Doc Writer) to complete development tasks.

### Features

- **Web Dashboard**: Browser-based chat with project management, file browser, and settings
- **Multi-Role Team**: Project Manager, Product Manager, Architect, Developer, Reviewer, Bug Hunter, Doc Writer
- **Harness Knowledge**: 6-section progressive knowledge base with cross-role alignment and cross-session experience accumulation
- **Auto-Project Creation**: Workspace projects auto-created on first use — zero manual configuration
- **Adversarial Review**: Multi-role adversarial review loop for code quality
- **Session Memory**: Persistent conversations with create/switch/delete support
- **Multi-Provider LLM**: DeepSeek V4 (default), Anthropic Claude, OpenAI, and more
- **1M Context Window**: Optimized for DeepSeek V4's 1M token context window

### Quick Start

```bash
# Option 1: One-command bootstrap (recommended)
git clone https://github.com/qbiong/HarnessGenJ-dev.git
cd HarnessGenJ-dev
python bootstrap.py

# Option 2: Manual install
git clone https://github.com/qbiong/HarnessGenJ-dev.git
cd HarnessGenJ-dev
pip install -e .

# Set API Key (choose one)
export ANTHROPIC_API_KEY="sk-ant-..."   # Anthropic Claude
export OPENAI_API_KEY="sk-..."          # OpenAI / DeepSeek
# Or configure in Web UI after startup

# Start
hgj-dev web
# Open http://localhost:8000 → first message auto-creates project → start working
```

No `hgj-dev init` needed. API keys can be set via environment variables or in the Settings page.

### Configuration

Settings are stored in `~/.hgj-dev/web_settings.json` and can be modified from the Settings tab:

| Setting | Description | Default |
|---------|-------------|---------|
| Provider | LLM provider | deepseek |
| Model | Model name | deepseek-v4-flash |
| API Key | Provider API key | From env var |
| Base URL | Custom API endpoint | Provider default |
| User Title | How agents address the user | 用户 |

### Core Capabilities

| Capability | Description |
|------------|-------------|
| Auto Onboarding | Detects empty projects, guides discovery, auto-generates PROJECT.md |
| @mention Dispatch | PM dispatches tasks to specialized agents via @mention |
| Adversarial Review | Developer → Reviewer → BugHunter quality loop |
| Progressive Knowledge | 6-section Harness template with cross-session accumulation |
| Context Management | Three-tier compaction for up to 1M token context |
| Workspace Isolation | Framework separated from user projects with path whitelist |

### Architecture

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

### Development

```bash
pip install -e ".[dev]"
ruff check .              # Code lint
pytest                    # Run tests
```

### License

MIT
