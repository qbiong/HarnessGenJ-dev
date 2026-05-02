# HGJ-dev 架构优化方案

> 基于 Claude Code 架构分析的系统性优化指南
> 参考版本：Claude Code v1.0+
> 生成日期：2026-04-24

---

## 1. 背景与目标

本项目（HarnessGenJ-dev）定位为独立 AI 开发工具，类似 Claude Code、Cursor、GitHub Copilot CLI。经过与 Claude Code 架构的对比分析，发现若干关键优化点。本文档系统性梳理这些优化项，为后续迭代提供路线图。

### 1.1 参考架构：Claude Code

Claude Code 是 Anthropic 推出的终端 AI 编程助手，其核心架构特征：

| 维度 | Claude Code 模式 |
|------|------------------|
| 会话存储 | JSONL + 路径编码 + Fork/Continue/Resume |
| Agent 循环 | ReAct + max_turns/budget/effort 控制 |
| 工具系统 | 只读并行 + readOnly 标记 + MCP 支持 |
| 上下文管理 | Auto-compaction + 压缩保留策略 |
| 流式协议 | Anthropic 标准事件 + usage 统计 |
| 记忆系统 | CLAUDE.md (用户) + Auto Memory (自动) |
| 错误恢复 | 23 种 Hook + 标准化终止类型 |
| 安全沙箱 | Seatbelt (macOS) / bubblewrap (Linux) |

---

## 2. 优化项清单

### P0 - 阻断性���题（必须修复）

#### P0-1: 上下文自动压缩（Auto-compaction）

**问题描述**：
当前系统没有上下文压缩机制。当对话历史接近模型上下文窗口限制时，会导致：
- API 返回上下文溢出错误
- Agent 循环失败，无法完成请求
- 用户体验完全中断

**Claude Code 方案**：
- 接近上下文窗口限制时自动触发压缩
- 用结构化摘要替换旧消息
- 压缩保留：用户意图、关键技术概念、文件路径、错误修复、待办
- 支持手动 `/compact` 触发和 `/rewind` 回退
- 支持在 CLAUDE.md 中自定义压缩指令

**实现建议**：
```python
# 新增 context_manager.py
class ContextManager:
    def __init__(self, max_tokens: int = 100000):
        self.max_tokens = max_tokens
    
    async def compress_if_needed(self, messages: list) -> list:
        # 计算当前 token 数
        # 如果超过阈值，调用 compress()
        pass
    
    def compress(self, messages: list) -> list:
        # 保留策略：意图、概念、路径、错误、待办
        pass
```

---

#### P0-2: 工具并行执行

**问题描述**：
当前 Agent 执行工具时采用完全顺序执行。当用户请求涉及多个只读操作（如读取多个文件、���索多个模式）时，效率低下。

**Claude Code 方案**：
- 只读工具（Read/Glob/Grep）自动并行执行
- 写操作工具（Edit/Write/Bash）顺序执行
- 通过 `readOnly` / `readOnlyHint` 标记工具属性

**实现建议**：
```python
# 工具元数据标记
class ReadFileTool(BaseTool):
    read_only = True  # 添加此属性
    
# Agent 执行层
async def _execute_tools_parallel(tool_calls: list) -> list:
    read_only_calls = [tc for tc in tool_calls if tc.is_readonly]
    write_calls = [tc for tc in tool_calls if not tc.is_readonly]
    
    # 只读工具并行
    read_results = await asyncio.gather(*[
        execute_tool(tc) for tc in read_only_calls
    ])
    
    # 写操作工具顺序
    write_results = []
    for tc in write_calls:
        write_results.append(await execute_tool(tc))
    
    return read_results + write_results
```

---

### P1 - 高优先级（强烈建议实现）

#### P1-1: HARNESS.md 加载机制 ✅ 已完成

**状态**: 2026-04-25 已实现
- 文件: `src/harnessgenj_dev/utils/harness_md.py`
- 功能: 递归向上查找 HARNESS.md/HARNESS.local.md/.harness/HARNESS.md
- 支持: YAML frontmatter 解析, @import 语法
- 集成: Agent._build_system_prompt() 包含项目指令

---

#### P1-2: Hook 系统 ✅ 已完成

**状态**: 2026-04-25 已实现
- 文件: `src/harnessgenj_dev/plugins/hook_manager.py` (已存在基础实现)
- 新增: `src/harnessgenj_dev/plugins/__init__.py` 全局 get_hook_manager()
- Agent 集成: session_start, user_prompt_submit, pre_tool_use, post_tool_use, post_tool_use_failure, error, stop
- 事件定义: 参考 Claude Code 23种事件

---

#### P1-3: 会话 Fork/Branch 功能 ✅ 已完成

**状态**: 2026-04-25 已实现
- 文件: `src/harnessgenj_dev/web/session_manager.py`
- 新增方法: fork_session(), get_fork_tree()
- 功能: 从原会话复制历史创建分支, 支持角色切换

---

#### P1-2: Hook 系统

**问题描述**：
当前系统缺少可扩展的钩子机制，无法在关键事件发生时插入自定义逻辑。限制了：
- 权限控制（PreToolUse）
- 自动化流水线（PostToolUse）
- 审计日志
- 自定义压缩前后处理

**Claude Code 方案**：
- 23 种 Hook 事件：SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, PreCompact, PostCompact, Stop, FileChanged 等
- 支持 matchers 和条件执行
- 可挂载命令、Webhook、Python 函数

**实现建议**：
```python
# hook_system.py
class HookManager:
    HOOK_EVENTS = [
        "session_start", "session_end",
        "pre_tool_use", "post_tool_use", "post_tool_use_failure",
        "pre_compact", "post_compact",
        "stop", "stop_failure",
    ]
    
    def register(self, event: str, handler: Callable):
        pass
    
    async def fire(self, event: str, context: dict) -> list:
        pass
```

---

#### P1-3: 会话 Fork/Branch 功能

**问题描述**：
当前 SessionManager 只支持单线会话。无法：
- 从某个历史点创建分支进行探索性修改
- 并行尝试多种方案
- 保留实验性对话历史

**Claude Code 方案**：
- Fork：复制原会话历史，生成新会话 ID，原始会话不变
- Continue：查找当前目录下最近会话
- Resume：传入具体 session_id 恢复特定会话

**实现建议**：
```python
class SessionManager:
    def fork_session(self, project: str, session_id: str) -> Session:
        """创建分支会话"""
        original = self.get_session(project, session_id)
        forked = Session(
            id=str(uuid.uuid4())[:8],
            project=project,
            role=original.role,
            messages=original.messages.copy(),  # 复制历史
            metadata={**original.metadata, "forked_from": session_id}
        )
        self.save(forked)
        return forked
```

---

### P2 - 中优先级

#### P2-1: MCP 工具支持 ✅ 已完成

**状态**: 2026-04-25 已实现
- 文件: `src/harnessgenj_dev/tools/mcp_ops.py`, `src/harnessgenj_dev/tools/mcp_wrapper.py`
- MCP Client Manager: 支持 stdio 传输连接 MCP 服务器
- 工具发现: list_tools(), list_all_tools()
- 工具调用: call_tool() 返回结构化结果
- MCP 工具封装: MCPToolWrapper 将 MCP 工具转换为 HGJ 工具
- 依赖: 已添加到 pyproject.toml (mcp>=1.0.0)

---

#### P2-2: 沙箱安全隔离 ✅ 已完成

**状态**: 2026-04-25 已实现
- 文件: `src/harnessgenj_dev/executor/sandbox.py`
- 新增 SandboxConfig: allowed_dirs, read_only_dirs, block_paths
- 网络隔离: allow_network, allowed_hosts, proxy_url
- 资源限制: max_memory_mb, max_cpu_percent, max_execution_time
- check_path_access(): 文件系统访问控制
- get_env_with_network_restriction(): 网络环境隔离
- 已有安全检查: security.py 中的模式匹配

---

#### P2-3: WebSocket 协议增强 ✅ 已完成

**状态**: 2026-04-25 已实现
- 文件: `src/harnessgenj_dev/web/dashboard.py`
- Token 使用统计: _total_input_tokens, _total_output_tokens, _total_cost_usd
- final_answer 消息增加 usage 字段:
  ```json
  {"type": "final_answer", "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_usd": 0.0}}
  ```
- stop_reason 字段可扩展 (需要 LLM provider 支持)

---

#### P2-3: WebSocket 协议增强

**问题描述**：
当前 WebSocket 消息协议缺少：
- token 使用量实时统计
- 标准的 stop_reason 通知
- 流式 token 计数

**Claude Code 方案**：
- 使用 Anthropic API 标准流事件
- `message_delta` 事件包含 usage 和 stop_reason

---

### P3 - 低优先级（可选优化）

#### P3-1: Budget 控制参数

**实现目标**：支持 `max_budget_usd` 基于花费的限制

#### P3-2: Effort 控制参数

**实现目标**：支持 `effort: low/medium/high/xhigh/max` 推理深度

#### P3-3: Thinking Tokens

**实现目标**：支持 `max_thinking_tokens` 深度思考模式

#### P3-4: Checkpoint 回退 UI

**实现目标**：Web UI 上提供回退检查点选择界面

---

## 3. 实施路线图

### Phase 1: 基础能力补齐（1-2周）

| 任务 | 预估工作量 | 依赖 |
|------|-----------|------|
| P0-1 上下文自动压缩 | 3天 | TokenCounter |
| P0-2 工具并行执行 | 2天 | - |
| P1-3 会话 Fork | 2天 | SessionManager |

### Phase 2: 用户指令系统（1周）

| 任务 | 预估工作量 | 依赖 |
|------|-----------|------|
| P1-1 CLAUDE.md 加载 | 3天 | - |
| P1-2 Hook 系统 | 4天 | - |

### Phase 3: 生态扩展（2周）

| 任务 | 预估工作量 | 依赖 |
|------|-----------|------|
| P2-1 MCP 支持 | 5天 | - |
| P2-2 沙箱隔离 | 5天 | - |

### Phase 4: 精细控制（1周）

| 任务 | 预估工作量 | 依赖 |
|------|-----------|------|
| P3-1 Budget 控制 | 1天 | - |
| P3-2 Effort 控制 | 1天 | - |
| P3-3 Thinking Tokens | 2天 | LLM Provider |

---

## 4. 文件结构对应

当前项目文件结构与优化项的对应关系：

```
src/harnessgenj_dev/
├── core/
│   ├── agent.py              # P0-2 (并行工具), P3-1/2/3 (控制参数)
│   └── context_manager.py    # P0-1 (新增 - 自动压缩)
├── tools/
│   └── registry.py           # P0-2 (readOnly 标记)
├── web/
│   ├── dashboard.py          # P2-3 (协议增强)
│   └── session_manager.py    # P1-3 (Fork 功能)
├── memory/
│   ├── memory_manager.py     # P1-1 (CLAUDE.md 加载)
│   └── injector.py           # (Auto Memory 基础)
├── hooks/                    # P1-2 (新增 - Hook 系统)
│   └── __init__.py
├── executor/
│   └── sandbox.py            # P2-2 (新增 - 沙箱隔离)
└── config/
    └── claude_md.py          # P1-1 (新增 - CLAUDE.md 加载器)
```

---

## 5. 验收标准

每个优化项完成后，需满足：

| 优化项 | 验收条件 |
|--------|----------|
| P0-1 上下文压缩 | 100 轮对话后不报错，上下文 token 维持稳定 |
| P0-2 工具并行 | 3 个 Read 操作总耗时 < 最慢单次 × 1.5 |
| P1-1 CLAUDE.md | 项目根目录 CLAUDE.md 内容被注入 system prompt |
| P1-2 Hook 系统 | PreToolUse 钩子可阻止危险命令执行 |
| P1-3 会话 Fork | Fork 后新会话包含原历史，独立演进 |

---

## 6. 参考资料

- Claude Code 文档：`https://code.claude.com/docs/`
- Agent Loop：`https://code.claude.com/docs/en/agent-sdk/agent-loop.md`
- Context Window：`https://code.claude.com/docs/en/context-window.md`
- Memory：`https://code.claude.com/docs/en/memory.md`
- Hooks：`https://code.claude.com/docs/en/hooks.md`
- Checkpointing：`https://code.claude.com/docs/en/checkpointing.md`