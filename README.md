<p align="center">
  <img src="https://img.shields.io/badge/version-0.1.0--dev-blue" alt="version">
  <img src="https://img.shields.io/badge/python-3.11+-green" alt="python">
  <img src="https://img.shields.io/badge/license-MIT-brightgreen" alt="license">
  <img src="https://img.shields.io/badge/context-1M%20tokens-orange" alt="context">
</p>

<h1 align="center">HarnessGenJ-dev</h1>
<p align="center"><strong>你的 AI 开发团队，一个命令即可启动</strong></p>
<p align="center">项目经理自动调度架构师、开发者、审查员、Bug猎人协同工作<br>
参考 OpenClaw · Claude Code · MetaGPT 架构设计</p>

<p align="center">
  <a href="#快速开始">快速开始</a> •
  <a href="#核心概念">核心概念</a> •
  <a href="#架构">架构</a> •
  <a href="#english">English</a>
</p>

---

## 这是什么？

你给一个需求，HarnessGenJ-dev 自动组建一个 **AI 开发团队**帮你完成——

- 🎯 **项目经理** 判断任务类型，自动派发给合适的角色
- 🏗️ **架构师** 设计系统架构，输出 ADR 决策记录
- 💻 **开发者** 编写代码、跑测试、记录踩坑经验
- 🔍 **代码审查员** 检查安全、性能、可维护性
- 🐛 **Bug猎人** 边界测试、并发竞争、安全漏洞
- 📝 **文档编写者** 维护 README、API 文档、部署指南

**你只需要描述目标，团队自动协作。** 不需要手动分配任务，不需要管理上下文，不需要跟踪进度——框架帮你搞定一切。

### 为什么选择 HarnessGenJ-dev？

| 对比维度 | 单 Agent 工具 | HarnessGenJ-dev |
|----------|:-----------:|:---------------:|
| 代码生成 | ✅ 能写 | ✅ **专人写**（Developer） |
| 架构设计 | ⚠️ 混在代码里 | ✅ **专人设计**（Architect）+ ADR |
| 代码审查 | ❌ 自己审自己 | ✅ **专人审查**（Reviewer） |
| Bug 挖掘 | ❌ 测不到 | ✅ **专人破坏**（Bug Hunter） |
| 知识积累 | ❌ 每次重新扫 | ✅ **6 段式渐进知识库**，越用越聪明 |
| 团队协作 | ❌ 单人 | ✅ **7 角色协作**，各司其职 |

---

## 快速开始

```bash
# 一条命令启动
git clone https://github.com/qbiong/HarnessGenJ-dev.git
cd HarnessGenJ-dev && python bootstrap.py
```

`bootstrap.py` 自动完成：检测 Python → 创建虚拟环境 → 安装依赖 → 检测 API Key → 启动 Dashboard。

```bash
# 设置 API Key（二选一）
export ANTHROPIC_API_KEY="sk-ant-..."   # Claude
export OPENAI_API_KEY="sk-..."          # OpenAI / DeepSeek

# 启动后打开 http://localhost:8000
# 输入第一条消息 → 自动创建项目 → 开始开发
```

### 第一次体验

```
你: "帮我做一个 TODO 应用"

项目经理: "收到！这是一个全栈项目，我来调度团队：
         @architect 请设计系统架构
         @developer 根据架构实现代码
         @code_reviewer 审查代码质量"

架构师:   [输出 ADR + 模块设计]
开发者:   [编写代码 + 跑测试]
审查员:   [发现 3 个问题 → 开发者修复 → 审查通过]
Bug猎人:  [5 个边界测试 → 全部通过]

项目经理: "✅ 全部完成。TODO 应用已就绪，
         141 个测试 100% 通过，文档已更新。"
```

---

## 核心概念

### Harness 知识管理

参考 OpenClaw 的渐进式知识加载和 Claude Code 的 SKILL.md 模式，每个角色拥有一个 **6 段式知识库**，作为该角色领域的唯一真实来源（Single Source of Truth）：

```
.project-knowledge/
├── project_status.md          ← PM 全局进度索引
├── product_manager/
│   └── requirements.md        ← 需求定义（What/Why）
├── architect/
│   ├── design.md              ← 架构设计（How）
│   └── adrs/                  ← 架构决策记录
├── developer/
│   └── notes.md               ← 实现经验 & 踩坑记录 ⭐
├── code_reviewer/
│   └── reports.md             ← 审查报告 & 质量趋势
├── bug_hunter/
│   └── findings.md            ← 缺陷模式 & 测试策略
└── doc_writer/
    └── docs.md                ← 文档覆盖率 & 更新历史
```

**渐进积累**：每次任务完成后，经验教训自动追加到知识库。下次派发时，Agent 先读知识库了解历史，避免重复踩坑。**用得越多，团队越聪明。**

### 3 层渐进式加载

| 层级 | 内容 | Token 消耗 |
|:----:|------|:---------:|
| L1 | 角色元数据（id + description） | ~50 |
| L2 | 知识库全文（6 段式模板） | ~500 |
| L3 | 引用文件（ADR / 审查报告 / 测试结果） | 按需 |

### 角色边界

每个角色有明确的 **领域（Domain）** 和 **硬边界（must_not）**：

```
项目经理 ──派发──→ 架构师（设计 How）
    │                 │
    ├───────派发──→ 开发者（实现 Implementation）
    │                 │
    ├───────派发──→ 审查员（审查 Review）
    │                 │
    ├───────派发──→ Bug猎人（破坏 Testing）
    │                 │
    └───────派发──→ 文档编写者（文档 Docs）
```

产品经理定义 What/Why，架构师设计 How，开发者实现 Implementation——**三者永不混淆。**

---

## 架构

```
┌─────────────────────────────────────────────────┐
│                  Web Dashboard                    │
│         FastAPI + WebSocket · SPA 前端            │
├─────────────────────────────────────────────────┤
│                Agent ReAct Loop                   │
│     Thought → Action → Observation → Repeat      │
├─────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ LLM 网关 │ │ 工具注册 │ │ 角色注册 & 知识库 │ │
│  │ DeepSeek │ │ 文件操作 │ │ PM/PDM/AR/DV/RV/ │ │
│  │ Claude   │ │ Shell   │ │ BH/DW · 6 段式    │ │
│  │ OpenAI   │ │ 搜索/测试│ │ Harness 模板      │ │
│  └──────────┘ └──────────┘ └──────────────────┘ │
├─────────────────────────────────────────────────┤
│         插件系统 · Hooks · 会话管理 · MCP         │
└─────────────────────────────────────────────────┘
```

### 项目结构

```
src/harnessgenj_dev/
├── core/              # Agent ReAct 循环 & 系统提示词
├── llm/               # 多提供商 LLM 网关
├── web/               # Web Dashboard（FastAPI + WebSocket）
├── tools/             # 文件/Shell/搜索/测试/Git
├── memory/            # 角色注册 & Harness 知识管理
├── scanner/           # 项目扫描 & AST 分析
├── executor/          # 安全沙箱代码执行
└── plugins/           # Hooks 插件系统
```

---

## 配置

所有配置存储在 `~/.hgj-dev/web_settings.json`：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `provider` | LLM 提供商 | deepseek |
| `model` | 模型名称 | deepseek-v4-flash |
| `api_key` | API 密钥 | 从环境变量读取 |
| `base_url` | 自定义 API 地址 | 提供商默认 |
| `user_title` | Agent 对用户的称呼 | 用户 |

---

## 开发

```bash
pip install -e ".[dev]"
ruff check .              # 代码检查
pytest                    # 运行测试
```

---

## 许可

MIT

---

<a name="english"></a>
## English

<h3 align="center">Your AI Dev Team — One Command Away</h3>

HarnessGenJ-dev is an **AI-powered multi-role development framework**. Give it a requirement, and it assembles a team of specialized AI agents — Project Manager, Architect, Developer, Reviewer, Bug Hunter, and Doc Writer — to collaborate and deliver.

**You describe the goal. The team self-organizes.**

### Why Multi-Role?

Single-agent tools mix architecture, coding, review, and testing in one model — leading to biased reviews, missed edge cases, and lost context. HarnessGenJ-dev separates concerns:

- **Project Manager** orchestrates — never writes code
- **Architect** designs — never implements
- **Developer** codes — never makes architecture decisions
- **Reviewer** audits — never fixes bugs
- **Bug Hunter** breaks things — never patches them
- **Doc Writer** documents — never modifies logic

Each role has a **hard boundary** (must_not rules) enforced by the system prompt. Knowledge accumulates across sessions via a **6-section Harness knowledge base** — the team gets smarter with every task.

### Quick Start

```bash
git clone https://github.com/qbiong/HarnessGenJ-dev.git
cd HarnessGenJ-dev && python bootstrap.py
# Open http://localhost:8000 → start developing
```

### Inspired By

- [OpenClaw](https://github.com/openclaw/openclaw) — Gateway routing & progressive disclosure
- [Claude Code](https://claude.ai/code) — SKILL.md pattern & agent tool use
- [MetaGPT](https://github.com/geekan/MetaGPT) — Multi-role SOP-based collaboration

### License

MIT
