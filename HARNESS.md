# HarnessGenJ-dev

AI 驱动的多角色开发助手，将 HGJ 从 Claude Code 插件改造为独立运行工具。

## 项目概况

- **定位**: 独立 AI 开发工具（类似 Claude Code、Cursor、GitHub Copilot CLI）
- **核心**: 内置 LLM Gateway + Agent ReAct 循环 + 工具集 + Scanner
- **依赖**: 通过 pip 依赖 `harnessgenj>=1.4.6`（不复制代码）
- **Phase 状态**: Phase 1 ✅ | Phase 2 ✅ | Phase 3 ✅ | 测试 752 个 100% 通过 (另有 24 个端到端测试需 API Key 运行)

## 架构

```
src/harnessgenj_dev/
├── core/          # Agent 主循环 (ReAct)、系统提示词、上下文管理
│   ├── agent.py           # ReAct 循环 + 工具执行 + 6 角色
│   ├── context_manager.py # 上下文窗口 + 压缩策略
│   └── system_prompt.py   # 系统提示词构建
├── llm/           # LLM 网关 (多提供商)、token 计数、流式处理、速率限制重试
│   ├── gateway.py         # 统一入口 + 5 模型降级链 + 指数退避重试 + 使用统计
│   ├── providers/         # 4 个提供商实现
│   │   ├── base.py        # BaseProvider 抽象基类
│   │   ├── anthropic.py   # Claude API
│   │   ├── openai.py      # OpenAI API
│   │   ├── openrouter.py  # OpenRouter 统一网关
│   │   └── local.py       # Ollama/vLLM/LM Studio
│   ├── models.py          # LLMResponse / UsageReport / StreamChunk
│   ├── model_router.py    # 按任务类型选择模型
│   └── token_counter.py   # tiktoken + 降级方案
├── tools/         # 内置工具集 (文件/Shell/代码搜索/测试/Git)
├── executor/      # 代码执行沙箱 (Python/Shell + 安全策略)
├── scanner/       # 项目扫描与索引
│   ├── project_index.py   # 文件树 + 语言检测
│   ├── ast_analyzer.py    # Python AST 分析
│   ├── symbol_table.py    # 全局符号索引
│   └── code_search.py     # ripgrep + 符号搜索
├── hgj/           # HGJ 框架集成
│   ├── roles.py           # HGJ 角色定义 + 角色管理器
│   ├── workflows.py       # HGJ 工作流定义 + 编排器
│   └── integration.py     # HGJ 桥接适配器 (Harness ↔ Agent)
├── plugins/       # 插件系统
│   ├── base.py            # 插件基类 + PluginInfo
│   ├── registry.py        # 插件注册表
│   ├── hook_manager.py    # Hook 管理器
│   ├── manager.py         # 插件管理器 (Registry + Hooks)
│   └── builtins/          # 内置插件
│       ├── __init__.py    # 自动注册
│       └── github_plugin.py # GitHub 集成插件
├── web/           # Web Dashboard
│   └── dashboard.py       # FastAPI + WebSocket + 文件浏览器 + 项目管理
├── projects.py    # 多项目管理 + 切换 + JSON 持久化
├── tui/           # Textual 终端界面
├── utils/         # 日志、异常
├── cli.py         # CLI 入口 (init/develop/status/review + REPL)
└── config.py      # 配置管理 (Pydantic + YAML)
```

## 技术栈

- **构建**: hatchling | **测试**: pytest + pytest-asyncio + pytest-cov
- **代码质量**: ruff + mypy | **TUI**: textual
- **LLM**: anthropic + openai + httpx
- **AST**: tree-sitter + Python ast 内置模块 | **Token**: tiktoken

## 开发命令

```bash
pip install -e ".[dev]"   # 安装开发依赖
pip install pyyaml textual  # 可选依赖
ruff check .              # 代码检查
ruff format .             # 代码格式化
mypy src/                 # 类型检查
pytest                    # 运行测试 (752 tests, 100% pass + 24 e2e skipped)
hgj-dev                   # CLI 入口
hgj-dev develop "prompt"  # 一次性执行
hgj-dev develop           # 交互式 REPL
hgj-dev web               # 启动 Web Dashboard
hgj-dev web --reload      # 开发模式（自动重载）
hgj-dev web --host 0.0.0.0 --port 9000  # 自定义地址和端口
```

## 开发计划

详见 [docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md)

### Phase 1: 独立运行基础 (✅ 完成)
- [x] 项目骨架初始化
- [x] LLM Gateway (P0) — 4 提供商 + 降级链
- [x] Agent Core (P0) — ReAct 循环 + 工具集成
- [x] Tool Set (P0) — 7 工具 + 自动注册
- [x] Code Executor (P0) — 14 个测试
- [x] Interactive CLI (P1) — argparse + REPL
- [x] Integration Tests (P1) — 84 个测试
- [x] P1-T07: 工具集需求定义
- [x] P1-T08: API 参考文档 + 用户指南

### Phase 2: 开发体验提升 (✅ 完成)
- [x] AST 分析器 (Python ast + tree-sitter)
- [x] SymbolTable + CodeSearch
- [x] 速率限制自动重试 (指数退避 + Retry-After + 42 测试)
- [x] HGJ 集成 (桥接适配器 + 开发/修复/审查/对抗 + 13 测试)
- [x] 端到端测试 (24 个测试，配置 API Key 后自动运行)

### Phase 3: 生态建设 (✅ 完成)
- [x] Plugin System (base + registry + hook_manager + manager + 66 测试)
- [x] 内置插件 (GitHub Plugin + 生命周期 + 命令 + 钩子 + 20 测试)
- [x] Web Dashboard (FastAPI + WebSocket + Agent 集成 + Settings 页面 + 文件浏览器 + 30 测试)
- [x] 多项目管理 (ProjectManager + 持久化 + 20 测试)

## 重要约定

- 测试使用 `PYTHONPATH=src pytest` 运行（不依赖 pip install -e）
- tree-sitter-languages 不支持 Python 3.13，AST 分析使用 Python 内置 ast 模块
- Agent ReAct 循环需要 API Key 才能实际调用 LLM
- 所有文档在 docs/ 目录下
