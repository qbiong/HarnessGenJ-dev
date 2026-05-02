# HarnessGenJ-dev Phase 1 任务分配表

> **创建时间**: 2026-04-12
> **分配者**: 项目经理（PM）
> **阶段**: Phase 1 — 独立运行基础
> **目标**: 能独立运行，调用 LLM，执行基本开发任务

---

## 任务总览

| # | 任务ID | 任务名称 | 分配角色 | 优先级 | 状态 | 依赖 |
|---|--------|---------|---------|--------|------|------|
| 1 | P1-T01-A | LLM Gateway ADR 设计 | 架构师 | P0 | 🔄 进行中 | — |
| 2 | P1-T01-B | Anthropic 提供商 | 开发者 | P0 | ⏳ 等待依赖 | P1-T01-A |
| 3 | P1-T01-C | OpenAI 提供商 | 开发者 | P0 | ⏳ 等待依赖 | P1-T01-A |
| 4 | P1-T01-D | 模型路由与降级 | 开发者 | P0 | ⏳ 等待依赖 | P1-T01-A |
| 5 | P1-T03-A | edit_file 工具 | 开发者 | P0 | 🔄 进行中 | — |
| 6 | P1-T03-B | ripgrep 增强 | 开发者 | P0 | 🔄 进行中 | — |
| 7 | P1-T03-C | 工具注册完善 | 开发者 | P0 | 🔄 进行中 | — |
| 8 | P1-T04-A | Python 执行器增强 | 开发者 | P0 | 🔄 进行中 | — |
| 9 | P1-T04-B | 安全策略增强 | 开发者 | P0 | 🔄 进行中 | — |
| 10 | P1-T04-C | 执行器测试补充 | 测试员 | P0 | 🔄 进行中 | — |
| 11 | P1-T02 | Agent Core 完善 | 架构师 + 开发者 | P0 | 📋 待分配 | P1-T01 |
| 12 | P1-T05 | Interactive CLI | 开发者 | P1 | 📋 待分配 | P1-T02, P1-T03 |
| 13 | P1-T06 | 集成测试 | 测试员 | P1 | 📋 待分配 | P1-T02 ~ P1-T05 |
| 14 | P1-T07 | 工具集需求定义 | 产品经理 | P1 | 🔄 进行中 | — |
| 15 | P1-T08 | API 参考文档 | 文档管理员 | P1 | 🔄 进行中 | — |

---

## 任务详情

### P1-T01: LLM Gateway 实现

**任务类型**: `implement_feature`
**负责角色**:
- 🏗️ 架构师: 定义 API 接口契约
- 👨‍💻 开发者: 实现提供商适配器

**前置条件**: 无
**验收标准**:
- [ ] 能成功调用 Claude/OpenAI 并返回结果
- [ ] 支持流式输出
- [ ] Token 计数准确（tiktoken 或降级方案）
- [ ] 模型切换正常
- [ ] 成本估算正确

**文件清单**:
- `src/harnessgenj_dev/llm/gateway.py` — 统一网关（已有骨架）
- `src/harnessgenj_dev/llm/providers/anthropic.py` — **待实现**
- `src/harnessgenj_dev/llm/providers/openai.py` — **待实现**
- `src/harnessgenj_dev/llm/providers/openrouter.py` — **待实现**
- `src/harnessgenj_dev/llm/providers/local.py` — **待实现**
- `src/harnessgenj_dev/llm/token_counter.py` — 已有降级方案
- `src/harnessgenj_dev/llm/model_router.py` — 已有基础
- `src/harnessgenj_dev/llm/streaming.py` — **待实现**

---

### P1-T02: Agent Core 完善

**任务类型**: `implement_feature`
**负责角色**:
- 🏗️ 架构师: 定义 Agent 循环接口设计
- 👨‍💻 开发者: 实现 ReAct 循环

**前置条件**: P1-T01 完成
**验收标准**:
- [ ] 能完成多轮工具调用对话
- [ ] 流式输出正常
- [ ] 中断后可恢复（Ctrl+C）
- [ ] 上下文压缩触发正常

**文件清单**:
- `src/harnessgenj_dev/core/agent.py` — ReAct 循环（已有骨架）
- `src/harnessgenj_dev/core/system_prompt.py` — 提示词构建（已有骨架）
- `src/harnessgenj_dev/core/context_manager.py` — 上下文管理（已有骨架）

---

### P1-T03: Tool Set 完善

**任务类型**: `implement_feature`
**负责角色**:
- 👨‍💻 开发者: 完善工具实现

**前置条件**: P1-T01 完成（Agent 需要调用工具）
**验收标准**:
- [ ] 所有工具可注册、可调用
- [ ] 文件操作正确读写
- [ ] Shell 命令带超时
- [ ] 搜索结果准确

**文件清单**:
- `src/harnessgenj_dev/tools/base.py` — 工具基类（已完成）
- `src/harnessgenj_dev/tools/registry.py` — 注册表（已完成）
- `src/harnessgenj_dev/tools/file_ops.py` — 文件操作（已有基础）
- `src/harnessgenj_dev/tools/shell_ops.py` — Shell 命令（已有基础）
- `src/harnessgenj_dev/tools/code_ops.py` — 代码搜索（已有基础）
- `src/harnessgenj_dev/tools/test_ops.py` — 测试执行（已有基础）
- `src/harnessgenj_dev/tools/git_ops.py` — Git 操作（已有基础）

---

### P1-T04: Code Executor 完善

**任务类型**: `implement_feature`
**负责角色**:
- 👨‍💻 开发者: 完善执行器实现
- 🧪 测试员: 执行安全测试

**前置条件**: P1-T03 完成
**验收标准**:
- [ ] Python 代码安全执行
- [ ] 无限循环被超时终止
- [ ] 危险命令被拦截
- [ ] 输出正确捕获

**文件清单**:
- `src/harnessgenj_dev/executor/sandbox.py` — 沙箱基类（已完成）
- `src/harnessgenj_dev/executor/python_executor.py` — Python 执行（已有基础）
- `src/harnessgenj_dev/executor/shell_executor.py` — Shell 执行（已有基础）
- `src/harnessgenj_dev/executor/security.py` — 安全策略（已有基础）

---

### P1-T05: Interactive CLI

**任务类型**: `implement_feature`
**负责角色**:
- 👨‍💻 开发者: 实现 Textual TUI

**前置条件**: P1-T02, P1-T03 完成
**验收标准**:
- [ ] 应用正常启动
- [ ] 用户可输入对话
- [ ] AI 流式响应
- [ ] 斜杠命令正常工作

**文件清单**:
- `src/harnessgenj_dev/tui/app.py` — TUI 主应用（**待实现**）
- `src/harnessgenj_dev/tui/chat_view.py` — **待创建**
- `src/harnessgenj_dev/tui/status_bar.py` — **待创建**
- `src/harnessgenj_dev/tui/commands.py` — **待创建**

---

### P1-T06: 集成测试

**任务类型**: `write_test`
**负责角色**:
- 🧪 测试员: 编写端到端测试

**前置条件**: P1-T02 ~ P1-T05 完成
**验收标准**:
- [ ] 完整流程端到端测试
- [ ] Mock LLM 响应测试
- [ ] 错误处理测试

---

## 任务执行顺序（依赖图）

```
P1-T01-A [架构师: ADR-001] ──→ P1-T01-B/C/D [开发者: 提供商实现]
        │                              ↓
P1-T03 [开发者: Tool Set (3项)] ───→ P1-T05 [CLI]
        │                              ↓
P1-T04 [开发者+测试: Executor] ─────→ P1-T06 [集成测试]
        │
P1-T07 [产品经理: 需求] ──→ P1-T02 [Agent Core]
        │
P1-T08 [文档: API参考]
```

**关键路径**: P1-T01-A → P1-T01-B → P1-T02 → P1-T05 → P1-T06
**并行路径**: P1-T03, P1-T04, P1-T07, P1-T08（可独立推进）

---

## 任务状态追踪

| 任务 | 创建时间 | 分配时间 | 计划完成 | 实际完成 | 积分变化 |
|------|---------|---------|---------|---------|---------|
| P1-T01-A | 2026-04-12 | 2026-04-12 | — | — | — |
| P1-T01-B | 2026-04-12 | — | — | — | — |
| P1-T01-C | 2026-04-12 | — | — | — | — |
| P1-T01-D | 2026-04-12 | — | — | — | — |
| P1-T02 | 2026-04-12 | — | — | — | — |
| P1-T03 | 2026-04-12 | 2026-04-12 | — | — | — |
| P1-T04 | 2026-04-12 | 2026-04-12 | — | — | — |
| P1-T05 | 2026-04-12 | — | — | — | — |
| P1-T06 | 2026-04-12 | — | — | — | — |
| P1-T07 | 2026-04-12 | 2026-04-12 | — | — | — |
| P1-T08 | 2026-04-12 | 2026-04-12 | — | — | — |

---

## 变更记录

| 日期 | 变更内容 | 变更人 |
|------|---------|--------|
| 2026-04-12 | 初始创建，拆解6个任务 | PM |

---

*最后更新: 2026-04-12 | 总任务: 6 | 待启动: 6 | 进行中: 0 | 已完成: 0*
