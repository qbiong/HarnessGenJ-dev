<p align="center">
  <img src="https://img.shields.io/badge/version-0.1.0--dev-blue" alt="version">
  <img src="https://img.shields.io/badge/python-3.11+-green" alt="python">
  <img src="https://img.shields.io/badge/license-MIT-brightgreen" alt="license">
  <img src="https://img.shields.io/badge/context-1M%20tokens-orange" alt="context">
</p>

<h1 align="center">HarnessGenJ-dev</h1>
<p align="center">
  <strong>对抗式审查 &times; 渐进式披露 &times; Harness 自我完善</strong><br>
  一个专门用于软件开发的 AI 多角色协作框架<br>
  参考 OpenClaw · Claude Code · MetaGPT 架构设计
</p>

<p align="center">
  <a href="#三大核心理念">核心理念</a> •
  <a href="#快速开始">快速开始</a> •
  <a href="#架构">架构</a> •
  <a href="#角色体系">角色体系</a> •
  <a href="#配置">配置</a>
</p>

---

## 这是什么？

HarnessGenJ-dev 是一个**专门用于软件开发的 AI 多角色协作框架**。它不是你日常聊天的 AI 助手——它是一支围绕你的项目组建的 AI 开发团队。

**只需描述目标，框架自动组建团队、分配角色、协调工作、积累经验。**

你给一个需求，HarnessGenJ-dev 自动组建团队帮你完成——

- 🎯 **项目经理** 判断任务类型，自动派发给合适的角色
- 🏗️ **架构师** 设计系统架构，输出 ADR 决策记录
- 💻 **开发者** 编写代码、跑测试、记录踩坑经验
- 🔍 **代码审查员** 检查安全、性能、可维护性
- 🐛 **Bug猎人** 边界测试、并发竞争、安全漏洞
- 📝 **文档编写者** 维护 README、API 文档、部署指南

---

## 三大核心理念

<table>
  <tr>
    <td align="center" width="33%">
      <h3>⚔️ 对抗式审查</h3>
      <p><em>Adversarial Review</em></p>
    </td>
    <td align="center" width="33%">
      <h3>📐 渐进式披露</h3>
      <p><em>Progressive Disclosure</em></p>
    </td>
    <td align="center" width="33%">
      <h3>🔄 Harness 自我完善</h3>
      <p><em>Harness Self-Improvement</em></p>
    </td>
  </tr>
  <tr>
    <td valign="top">
      代码不是一个人写的，也不是一个人审的。<br><br>
      开发者写完 → 审查员挑刺 → Bug猎人破坏 → 开发者修复。<br><br>
      <strong>多角色对抗确保每一行代码都经过多双眼睛的审视。</strong><br><br>
      <em>单 Agent 自己审自己的代码？那不是审查，那是自我安慰。</em>
    </td>
    <td valign="top">
      不是一次性把全部上下文塞给模型。<br><br>
      L1 元数据 (50 tokens) → L2 知识库 (500 tokens) → L3 引用文件 (按需)。<br><br>
      <strong>Agent 按需拉取信息，而不是被动接收信息。</strong><br><br>
      <em>1M 上下文 ≠ 应该填满 1M 上下文。</em>
    </td>
    <td valign="top">
      每次任务完成，经验教训自动沉淀到知识库。<br><br>
      下一个任务开始时，Agent 先读知识库，了解历史决策和踩过的坑。<br><br>
      <strong>项目越做越顺，团队越用越聪明。</strong><br><br>
      <em>传统工具每次从零开始；Harness 让经验跨会话传承。</em>
    </td>
  </tr>
</table>

---

### 为什么选择 HarnessGenJ-dev？

| 对比维度 | 单 Agent 工具 | HarnessGenJ-dev |
|----------|:-----------:|:---------------:|
| 代码生成 | ✅ 能写 | ✅ **专人写** + 专人审 + 专人测 |
| 架构设计 | ⚠️ 混在代码里 | ✅ **专人设计**（Architect）+ ADR 追溯 |
| 代码审查 | ❌ 自己审自己 | ✅ **对抗式审查**（Reviewer vs Developer） |
| Bug 挖掘 | ❌ 测不到边界 | ✅ **专人破坏**（Bug Hunter）找隐藏缺陷 |
| 知识积累 | ❌ 每次重新扫项目 | ✅ **Harness 自我完善**，越用越聪明 |
| 上下文管理 | ❌ 全量塞入 | ✅ **渐进式披露**，按需加载 |
| 团队协作 | ❌ 单人 | ✅ **7 角色协作**，各司其职，边界清晰 |

---

## 快速开始

### 环境要求

- Python 3.11+
- LLM API Key（Anthropic Claude / OpenAI / DeepSeek）

### 一键启动

```bash
git clone https://github.com/qbiong/HarnessGenJ-dev.git
cd HarnessGenJ-dev && python bootstrap.py
```

`bootstrap.py` 自动完成：检测 Python 版本 → 创建虚拟环境 → 安装依赖 → 检测 API Key → 启动 Web Dashboard。

### 手动安装

```bash
git clone https://github.com/qbiong/HarnessGenJ-dev.git
cd HarnessGenJ-dev
pip install -e .

# 设置 API Key（二选一）
export ANTHROPIC_API_KEY="sk-ant-..."   # Anthropic Claude
export OPENAI_API_KEY="sk-..."          # OpenAI / DeepSeek

# 启动
hgj-dev web
```

打开 http://localhost:8000，输入第一条消息即可开始——项目会自动创建。

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

每个角色拥有一个 **6 段式知识库**，作为该角色领域的唯一真实来源（Single Source of Truth）：

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

**6 段式模板**：项目上下文 → 已完成工作 → 决策记录 → 经验教训 → 角色对齐 → 待办/阻塞

**渐进积累**：每次任务完成后，经验教训自动追加到知识库。下次派发时，Agent 先读知识库了解历史，避免重复踩坑。

### 3 层渐进式加载

| 层级 | 内容 | Token 消耗 |
|:----:|------|:---------:|
| L1 | 角色元数据（id + description） | ~50 |
| L2 | 知识库全文（6 段式模板） | ~500 |
| L3 | 引用文件（ADR / 审查报告 / 测试结果） | 按需 |

### 角色体系

每个角色有明确的 **领域（Domain）** 和 **硬边界（must_not）**：

```
项目经理（PM）──派发──→ 产品经理（定义 What/Why）
    │                   ├─ 架构师（设计 How）
    │                   ├─ 开发者（实现 Implementation）
    │                   ├─ 代码审查员（审查 Review）
    │                   ├─ Bug猎人（破坏 Testing）
    │                   └─ 文档编写者（文档 Docs）
```

| 角色 | 领域 | 拥有的知识库 | 绝对不做 |
|------|------|:----------:|----------|
| 项目经理 | 团队协调、任务派发、进度跟踪 | `project_status.md` | 写代码、设计、需求 |
| 产品经理 | 需求定义（What/Why） | `requirements.md` | 写代码、设计 How、调度 |
| 架构师 | 系统设计（How）、技术选型 | `design.md` | 写实现代码 |
| 开发者 | 代码实现、测试、Bug 修复 | `notes.md` | 架构决策、需求定义 |
| 审查员 | 代码质量、安全、性能 | `reports.md` | 修改代码 |
| Bug猎人 | 边界测试、安全漏洞 | `findings.md` | 修复 Bug |
| 文档编写者 | README、API 文档、部署指南 | `docs.md` | 修改业务逻辑 |

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
├── llm/               # 多提供商 LLM 网关（DeepSeek/Claude/OpenAI）
├── web/               # Web Dashboard（FastAPI + WebSocket SPA）
├── tools/             # 文件/Shell/搜索/测试/Git 工具集
├── memory/            # 角色注册 & Harness 知识管理
├── scanner/           # 项目扫描 & AST 分析
├── executor/          # 安全沙箱代码执行
└── plugins/           # Hooks 插件系统
```

---

## 配置

所有配置存储在 `~/.hgj-dev/web_settings.json`，也可在 Web Dashboard 的设置页修改：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `provider` | LLM 提供商 | deepseek |
| `model` | 模型名称 | deepseek-v4-flash |
| `api_key` | API 密钥 | 从环境变量读取 |
| `base_url` | 自定义 API 地址 | 提供商默认 |
| `user_title` | Agent 对用户的称呼 | 用户 |

### 支持的 LLM 提供商

| 提供商 | 环境变量 | 说明 |
|--------|----------|------|
| DeepSeek | `OPENAI_API_KEY` | 默认，1M 上下文窗口 |
| Anthropic Claude | `ANTHROPIC_API_KEY` | Claude Opus/Sonnet/Haiku |
| OpenAI | `OPENAI_API_KEY` | GPT-4o 系列 |
| OpenRouter | `OPENAI_API_KEY` | 统一 API 网关 |
| 通义千问 | `OPENAI_API_KEY` | 通过兼容接口 |
| 智谱 GLM | `OPENAI_API_KEY` | 通过兼容接口 |

---

## 开发

```bash
pip install -e ".[dev]"
ruff check .              # 代码检查
pytest                    # 运行测试
```

---

## 参考项目

- [OpenClaw](https://github.com/openclaw/openclaw) — Gateway 路由 & 渐进式披露
- [Claude Code](https://claude.ai/code) — SKILL.md 模式 & Agent 工具使用
- [MetaGPT](https://github.com/geekan/MetaGPT) — 多角色 SOP 协作

---

## 许可

MIT
