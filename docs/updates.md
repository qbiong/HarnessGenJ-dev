# HarnessGenJ-dev 优化更新文档

> 更新日期：2026-05-30
> 参考项目：OpenClaw · ClawTeam · Claude Code

---

## 目录

1. [核心问题回顾](#1-核心问题回顾)
2. [反幻觉体系（3 层防护）](#2-反幻觉体系3-层防护)
3. [渐进式披露（OpenClaw 3 层加载）](#3-渐进式披露openclaw-3-层加载)
4. [并行子 Agent 派发](#4-并行子-agent-派发)
5. [SprintContract + 证据闭环（ClawTeam）](#5-sprintcontract--证据闭环clawteam)
6. [Phase State Machine + Gate（ClawTeam）](#6-phase-state-machine--gateclawteam)
7. [Event Bus / Hook 系统](#7-event-bus--hook-系统)
8. [Conductor 确定性编排](#8-conductor-确定性编排)
9. [热加载角色](#9-热加载角色)
10. [其他修复](#10-其他修复)

---

## 1. 核心问题回顾

### 问题症状

```
用户: "开始修复所有问题"
PM:    "好的老板！我来全面诊断并修复所有测试失败。
       先读取所有相关文件。先看看测试文件和源文件..."
       [没有调用任何工具，纯文本描述]
用户: "你一直在幻觉中，没有执行任何操作"
PM:    "老板，我理解您的怀疑。让我用实际命令..."
       [继续文本描述，仍然不调用工具]
```

### 根因分析

| 根因 | 说明 | 贡献占比 |
|:-----|------|:-------:|
| **提示词臃肿** | PM 提示词累积到 **13867 字符**，包含 15+ 条互相矛盾的规则 | 50% |
| **ReAct 循环无监督** | 模型生成文本描述工作而不调用工具时，循环直接终止，文本被当作最终答案 | 30% |
| **子 Agent 串行派发** | 多个角色只能逐个派发，总耗时 = 各角色耗时之和 | 10% |
| **无验证闭环** | 子 Agent 说"做完了"就真的算做完了，没有独立验证 | 10% |

### 更新架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                     用户请求                                  │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  ① 反幻觉体系                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ L1 提示词: 简洁的 PM 规则（~700 字）                    │   │
│  │ L2 代码级: >200字无@mention → 自动转为派发             │   │
│  │ L3 引擎级: 描述工作不调用工具 → 注入纠正继续循环        │   │
│  └─────────────────────────────────────────────────────┘   │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  ② Phase State Machine                                      │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐        │
│  │讨论   │→│ 规划  │→│ 执行  │→│ 验证  │→│ 交付  │        │
│  │DISCUSS│ │PLAN  │ │EXECUTE│ │VERIFY│ │SHIP  │        │
│  └──────┘  └──────┘  └──────┘  └──────┘  └──────┘        │
│      ↓         ↓         ↓         ↓         ↓             │
│  产品经理   架构师    开发者    审查员   文档编写           │
│                            +Bug猎人                         │
│  Gate: 无   Gate: Spec  Gate: 代码  Gate: 测试  Gate: 文档  │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  ③ 并行派发 + SprintContract                                 │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ Round 1 (并行)    │  │ Round 2 (并行)    │               │
│  │ 架构师 文档编写    │→│ 开发者 审查员     │               │
│  │ Bug猎人 产品经理  │  │ (依赖Round 1结果) │               │
│  └──────────────────┘  └──────────────────┘                │
│         ↓                      ↓                            │
│  SprintContract        SprintContract                       │
│  ┌────────────────┐    ┌────────────────┐                  │
│  │ ✅ 设计文档存在  │    │ ✅ 测试全部通过  │                 │
│  │ ✅ ADR 已输出   │    │ ✅ 代码已写入   │                  │
│  └────────────────┘    └────────────────┘                  │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  ④ Event Bus / Hook                                         │
│  agent_dispatch → 记录日志                                   │
│  error → 告警                                                │
│  phase_transition → 自动更新 project_status.md              │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 反幻觉体系（3 层防护）

### 流程图

```
模型生成响应
    │
    ▼
┌─────────────────────┐
│  检查是否有 tool_calls │
└─────────┬───────────┘
          │
    ┌─────┴─────┐
    │ 有         │ 无
    ▼           ▼
  执行工具    ┌─────────────────────┐
  继续循环    │ 检查文本长度          │
             │ >200字?              │
             └─────────┬───────────┘
                    ┌──┴──┐
                    │ 是   │ 否
                    ▼     ▼
            ┌────────────┐ ┌────────────┐
            │ 检查 @mention │ │ 短文本     │
            │ 包含?       │ │ → 信息查询 │
            └──────┬─────┘ │ 直接输出   │
               ┌───┴───┐  └────────────┘
               │ 有    │ 无
               ▼      ▼
            ┌────────┐ ┌──────────────┐
            │ 正常   │ │ 反独白拦截    │
            │ 输出   │ │ 自动转为      │
            │        │ │ @developer   │
            │        │ │ 派发指令      │
            └────────┘ └──────────────┘
```

### L1：提示词精简

**之前**（13867 字符）：包含 15+ 条规则，互相冲突

```
信息查询自己做 ←→ 改文件必须调度
派发前最多 3 次 ←→ 反幻觉规则
关键区分表      ←→ 你永远不自己做的事
```

**之后**（7698 字符）：两条清晰规则

```
方式 A（信息查询）：问状态/位置/进度 → 读 1-2 个文件直接回答
方式 B（派发任务）：改文件/写代码/修复/推送 → 第一句就用 @mention

自我检查：超过 100 字还没有 @mention → 你在自己干活，删掉重写
```

### L2：代码级反独白

**位置**：[dashboard.py:2259-2263](src/harnessgenj_dev/web/dashboard.py)

```python
# PM 响应超过 200 字且不含 @mention，自动替换为 @developer 派发
if self.role == "project_manager" and len(accumulated) > 200 and "@" not in accumulated:
    accumulated = "该任务需要执行开发操作，已调度 @developer 处理。\n\n@developer 请执行以下任务：\n" + content[:500]
```

### L3：引擎级反幻觉

**位置**：[agent.py:942-951](src/harnessgenj_dev/core/agent.py)

在 `_react_loop` 和 `_react_loop_stream` 中，当模型生成 >200 字符的文本但没有调用任何工具时，注入系统纠正消息并继续循环，而不是终止。

```python
if len(accumulated_content) > 200:
    self.state.conversation_history.append({
        "role": "user",
        "content": "[系统检测到你在描述工作内容但没有调用任何工具。描述 ≠ 执行。]"
    })
    continue  # 强制重试
```

---

## 3. 渐进式披露（OpenClaw 3 层加载）

### 之前 vs 之后

```
之前: 系统提示词 = 13867 字符
      ┌──────────────────────────────────┐
      │ 角色定义 (6886字符)              │
      │ 团队信息 (742字符)               │
      │ 全局指令 (2722字符)              │
      │ 工具描述 (40字符)                │
      │ 项目上下文 (79字符)              │
      │ ...                              │
      └──────────────────────────────────┘
      所有内容一次性注入，模型无法聚焦

之后: 系统提示词 = 7698 字符
      ┌──────────────────────────────────┐
      │ L1 元数据: 角色名+描述+知识库路径│ ← 始终在提示词中
      │ PM 编排规则                      │
      ├──────────────────────────────────┤
      │ L2 完整指令: 在派发时注入任务提示词│ ← 按需加载
      │ can_do, must_not, SOP            │
      ├──────────────────────────────────┤
      │ L3 知识文件: 按需 read_file       │ ← 按需加载
      │ ADR, 审查报告, 测试结果           │
      └──────────────────────────────────┘
```

### 加载时机对比

| 层级 | OpenClaw | 本框架 |
|:----:|----------|--------|
| L1 | YAML frontmatter，~50 tokens | 角色定义精简版，~300 chars |
| L2 | SKILL.md 正文，命中触发 | `build_role_instructions()`，派发时注入 |
| L3 | `references/` 目录，按需读取 | `.project-knowledge/`，`read_file` |

### 实现代码

**L1 注入**：[agent.py:434-460](src/harnessgenj_dev/core/agent.py)

```python
lines = [
    f"## {display_name}（{role_id}）",
    description,
    f"📁 知识库：`{knowledge_file}`",
    "",
    "### 你的工作方式",
    "方式 A（信息查询）：...",
    "方式 B（派发任务）：...",
]
```

**L2 注入**：[dashboard.py:2318-2320](src/harnessgenj_dev/web/dashboard.py)

```python
from ..memory.role_registry import build_role_instructions
_role_full = build_role_instructions(role)
task_prompt = _role_full + "\n\n" + "You are the " + role_display + "..."
```

---

## 4. 并行子 Agent 派发

### 流程图

```
之前 (串行):
  架构师 ──→ 开发者 ──→ 审查员 ──→ Bug猎人
  总耗时 = 架构师 + 开发者 + 审查员 + Bug猎人

之后 (并行):
  Round 1 (并行):
   架构师 ──┐
   Bug猎人 ─┤ 同时运行
   文档编写 ─┘
   总耗时 = max(架构师, Bug猎人, 文档编写)

  Round 2 (并行, 依赖 Round 1):
   开发者 ←── 架构师结果
   审查员 ←── 开发者结果
   总耗时 = max(开发者, 审查员)
```

### 实现代码

[dashboard.py:2488-2497](src/harnessgenj_dev/web/dashboard.py)

```python
# Round 1: 独立角色并行
if _round1:
    r1 = await asyncio.gather(*[_dispatch_one(r, {}) for r in _round1])
    for r, res in zip(_round1, r1):
        agent_results[r] = res

# Round 2: 依赖角色并行（带 Round 1 结果）
if _round2:
    r2 = await asyncio.gather(*[_dispatch_one(r, agent_results) for r in _round2])
    for r, res in zip(_round2, r2):
        agent_results[r] = res
```

### 效果

| 场景 | 之前（串行） | 之后（并行） | 提升 |
|:-----|:----------:|:----------:|:----:|
| @architect + @doc_writer | 60s + 30s = 90s | max(60s, 30s) = 60s | 33% |
| @developer + @code_reviewer + @bug_hunter | 120s + 40s + 50s = 210s | 120s + max(40s, 50s) = 170s | 19% |
| 全角色 | 300s | 180s | 40% |

---

## 5. SprintContract + 证据闭环（ClawTeam）

### 什么是 SprintContract

ClawTeam 提出的概念：每个工作任务都应该有明确的、可验证的成功标准。

```
┌─────────────────────────────────────────────────┐
│ SprintContract                                   │
│                                                   │
│  title: "实现 LoginDetector"                      │
│  status: "in_progress"                            │
│  success_criteria:                                │
│    ✅ LoginDetector 类存在于 src/detector/ 中       │
│    ❌ 单元测试覆盖率达到 80%                        │
│    ✅ python -c 导入无报错                         │
│                                                   │
│  verify_all(): → 执行每个 criterion 的 test_command │
│                → 更新 verified 状态                │
│                → 生成 summary()                    │
└─────────────────────────────────────────────────┘
```

### 集成流程

```
PM 派发 @developer
    │
    ▼
创建 SprintContract
    │
    ├── criterion 1: "代码文件已创建" → test_command: python -c "from ... import ..."
    ├── criterion 2: "测试全部通过"  → test_command: pytest tests/ -x -q
    ├── criterion 3: "知识库已更新"  → expected_file: .project-knowledge/developer/notes.md
    │
    ▼
注入到任务提示词
    │
    ▼
Developer 执行工作
    │
    ▼
verify_all() → 自动运行 test_command
    │
    ├── 全部通过 → status = "completed"
    ├── 部分通过 → status = "in_progress"
    └── 全部失败 → status = "failed"
    │
    ▼
Contract summary 注入 PM 汇总
```

### 实现代码

**模型**：[contracts.py](src/harnessgenj_dev/core/contracts.py)

```python
@dataclass
class SprintContract:
    id: str
    title: str
    role: str
    success_criteria: list[SuccessCriterion]
    status: str  # pending | in_progress | completed | failed
    
    async def verify_all(self) -> list[SuccessCriterion]:
        for criterion in self.success_criteria:
            if criterion.test_command:
                proc = await asyncio.create_subprocess_shell(
                    criterion.test_command, stdout=PIPE, cwd=self.project_path
                )
                stdout, _ = await proc.communicate()
                criterion.verified = (proc.returncode == 0)
                criterion.evidence = stdout.decode()[:300]
        # Update status based on results
        if all(c.verified for c in self.success_criteria):
            self.status = "completed"
        ...
```

**派发时创建**：[dashboard.py:2369-2390](src/harnessgenj_dev/web/dashboard.py)

```python
_contract = SprintContract(
    title=f"{role_display}: {user_request[:80]}",
    role=role,
    success_criteria=[
        SuccessCriterion(description=f"{role_display} produced working code/files"),
        SuccessCriterion(description="Tests pass",
                         test_command="python -m pytest tests/ -x --tb=short -q 2>&1 | tail -3"),
    ],
)
# 注入验收条件到任务提示词
_criteria_text = "\n".join(f"- ✅ {c.description}" for c in _contract.success_criteria)
task_prompt += f"\n\n### 验收条件（完成后逐条验证）\n{_criteria_text}\n"
```

**完成后验证**：[dashboard.py:2418-2426](src/harnessgenj_dev/web/dashboard.py)

```python
_results = await _contract.verify_all()
_summary = _contract.summary()
sub_result += "\n\n" + _summary
```

---

## 6. Phase State Machine + Gate（ClawTeam）

### 5 阶段流程

```
┌─────────────────────────────────────────────────────────────┐
│  Phase State Machine                                        │
│                                                             │
│  DISCUSS ──Gate──→ PLAN ──Gate──→ EXECUTE ──Gate──→ VERIFY │
│    │                │              │              │         │
│    ▼                ▼              ▼              ▼         │
│  产品经理          架构师         开发者         审查员     │
│  理解需求         输出 ADR       写代码        +Bug猎人   │
│  编写 PRD         设计文档       跑测试         审查报告   │
│                                                             │
│         VERIFY ──Gate──→ SHIP                               │
│           │              │                                  │
│           ▼              ▼                                  │
│        测试通过        文档编写者                           │
│        审查通过        README, API 文档                     │
│                        git push                             │
└─────────────────────────────────────────────────────────────┘
```

### Gate 检查（确定性，无 LLM 参与）

```
Gate ─── conditions
  │
  ├── ArtifactRequiredGate: 检查文件是否存在
  │    如: ".project-knowledge/architect/design.md" 必须存在
  │
  ├── TestPassGate: 运行 pytest 并检查结果
  │    如: "python -m pytest tests/ -x --tb=short -q"
  │
  └── HumanApprovalGate: 需要人工确认
       如: 部署前必须用户点击确认
```

### 实现代码

**模型**：[phases.py](src/harnessgenj_dev/core/phases.py)

```python
class PhaseState:
    current_phase: str  # discuss | plan | execute | verify | ship
    
    async def can_advance(self, context) -> tuple[bool, str]:
        """检查当前阶段的所有 Gate 是否通过"""
        for gate in self.gates.get(self.current_phase, []):
            ok, reason = await gate.check(context)
            if not ok:
                return False, reason
        return True, ""
    
    async def advance(self, context) -> str | None:
        """如果 Gate 通过，推进到下一阶段"""
        ok, reason = await self.can_advance(context)
        if not ok:
            return None
        self.current_phase = next_phase
        return next_phase
```

**集成到派发**：[dashboard.py:2499-2515](src/harnessgenj_dev/web/dashboard.py)

```python
# 子 Agent 完成后，检查 Gate 并推进阶段
if _ps and session:
    _new_phase = await _ps.advance(_ctx)
    if _new_phase:
        session.metadata["phase_state"] = _ps.to_dict()
        self._get_session_mgr().save(session)
```

---

## 7. Event Bus / Hook 系统

### 架构

```
                     Event Bus
                         │
    ┌────────────────────┼────────────────────┐
    │                    │                    │
    ▼                    ▼                    ▼
agent_dispatch         error           phase_transition
    │                    │                    │
    ▼                    ▼                    ▼
记录日志              记录错误栈          更新 project_status.md
通知前端              告警通知            阶段可视化
```

### 注册的事件

| 事件 | 触发时机 | 当前处理 |
|:-----|:---------|:---------|
| `agent_dispatch` | 子 Agent 被派发时 | 记录日志 |
| `error` | LLM 调用失败时 | 记录警告日志 |
| `phase_transition` | 阶段推进时 | 记录日志 |
| `session_start` | Agent 会话开始 | 内置，未注册 handler |
| `user_prompt_submit` | 用户提交消息 | 内置，未注册 handler |
| `pre_tool_use` | 工具调用前 | 内置，未注册 handler |
| `post_tool_use` | 工具调用后 | 内置，未注册 handler |

### 实现代码

**注册**：[dashboard.py:1554-1559](src/harnessgenj_dev/web/dashboard.py)

```python
_hm = get_hook_manager()
_hm.register("agent_dispatch", lambda **kw: logger.info("EVENT: %(role)s %(status)s", kw))
_hm.register("error", lambda **kw: logger.warning("EVENT error: %(error)s", kw))
_hm.register("phase_transition", lambda **kw: logger.info("EVENT: %(from_phase)s -> %(to_phase)s", kw))
```

**触发**：[dashboard.py:2295-2298](src/harnessgenj_dev/web/dashboard.py)

```python
from ..plugins import get_hook_manager
await get_hook_manager().fire("agent_dispatch", role=role, status="started")
```

---

## 8. Conductor 确定性编排

### 什么是 Conductor

ClawTeam 的 `HarnessConductor` 是一个轮询循环，完全不用 LLM 做流程决策。它：

1. 查看当前 PhaseState
2. 根据阶段派发对应角色
3. 等待完成
4. 检查 Gate
5. 推进或阻塞

### 流程图

```
Conductor.run()
    │
    ▼
┌──────────────────────────────────────┐
│ while not last_phase:                │
│     current_phase → dispatch roles   │
│     await agents complete            │
│     check gates                      │
│     if ok → advance                  │
│     if not → report + break          │
└──────────────────────────────────────┘
    │
    ▼
Build summary report
```

### 与 ReAct 循环的对比

| 维度 | 传统 ReAct 循环 | Conductor 循环 |
|:-----|:---------------:|:--------------:|
| 决策者 | LLM | 确定性的 Phase Machine |
| 幻觉风险 | 高 | 无 |
| 可预测性 | 低 | 高 |
| 可恢复性 | 差（卡住就卡住） | 好（超时自动跳过） |
| 门控条件 | 无 | Gate 检查 |

### 实现代码

[conductor.py](src/harnessgenj_dev/core/conductor.py)

```python
class Conductor:
    async def run(self) -> str:
        while not self._phase_state.is_last_phase:
            phase = self._phase_state.current_phase
            # 1. 派发当前阶段的角色
            await self._dispatch_phase_roles(phase)
            # 2. 检查 Gate 并推进
            new_phase = await self._phase_state.advance(context)
            if not new_phase:
                # Gate 检查失败
                break
        # 3. 生成汇总报告
        return summary
```

---

## 9. 热加载角色

### 工作机制

```
用户编辑 JSON 文件 → 点击 "刷新" 按钮
        │
        ▼
POST /api/roles/reload
        │
        ▼
invalidate_cache() → 清除 mtime 缓存
        │
        ▼
list_roles() 重新读取:
  1. _BUILTIN_ROLES (Python dict)
  2. ~/.hgj-dev/roles/*.json (自定义角色)
        │
        ▼
新角色立即可用于 @mention 派发
```

### 自定义角色 JSON 格式

```json
{
  "id": "security_auditor",
  "display_name": "安全审计员",
  "avatar": "SA",
  "color": "pjm",
  "description": "安全审计专家",
  "knowledge_file": ".project-knowledge/security_auditor/audit.md",
  "mission": "审查代码安全性",
  "can_do": ["SQL注入检查", "XSS检查", "权限检查"],
  "must_not": ["修改代码", "调度其他角色"],
  "builtin": false
}
```

### 实现代码

**缓存机制**：[role_registry.py:28-40](src/harnessgenj_dev/memory/role_registry.py)

```python
_cache_mtimes: dict[str, float] = {}
_cache_dirty: bool = True

def invalidate_cache() -> None:
    global _cache_dirty
    _cache_dirty = True
```

**列表，新增按顺序执行**，先输出编号和名称，然后输出详情
---

## 10. 其他修复

### @staticmethod 缺失

**问题**：删除 `_FALLBACK_INSTRUCTIONS` 时误删了 `Agent.__init__` 和 `_compact_sub_session` 的 `@staticmethod` 装饰器，导致 `'AgentSession' object is not iterable` 错误。

**修复**：[dashboard.py:1643](src/harnessgenj_dev/web/dashboard.py)

```python
@staticmethod
def _compact_sub_session(history: list[dict], max_keep: int = 12) -> list[dict]:
```

### 子会话 tool 消息孤立

**问题**：会话压缩时保留了 `tool` 结果消息但丢弃了对应的 `assistant(tool_calls)`，导致 DeepSeek API 报 `"Messages with role 'tool' must be a response to a preceding message with 'tool_calls'"`。

**修复**：[dashboard.py:1619-1641](src/harnessgenj_dev/web/dashboard.py)

```python
def _repair_conversation(history: list[dict]) -> list[dict]:
    """移除孤立的 tool 消息（没有前导 assistant tool_calls 的）"""
    ...
```

### API 超时配置

**问题**：OpenAI 客户端使用默认超时（connect=60s），导致 DeepSeek API 偶发 TCP 无响应时请求挂起。

**修复**：[openai.py:54](src/harnessgenj_dev/llm/providers/openai.py)

```python
"timeout": httpx.Timeout(60.0, connect=15.0, read=120.0, write=30.0)
```

### 知识库维护过滤器

**问题**：子 Agent 更新知识库时的操作信息被展示给用户，造成干扰。

**修复**：[dashboard.py:1563-1570](src/harnessgenj_dev/web/dashboard.py)

```python
_KF_MAINTENANCE_PATTERNS = [
    "更新知识库", "写入知识库", "知识库已更新",
    "update .project-knowledge", "write .project-knowledge",
]
```

---

## 附录：文件变更清单

| 文件 | 变更类型 | 说明 |
|:-----|:---------|:-----|
| `src/harnessgenj_dev/core/agent.py` | 修改 | 提示词精简、反幻觉引擎级检查 |
| `src/harnessgenj_dev/core/contracts.py` | **新增** | SprintContract + SuccessCriterion |
| `src/harnessgenj_dev/core/phases.py` | **新增** | Phase State Machine + Gate |
| `src/harnessgenj_dev/core/conductor.py` | **新增** | 确定性编排 Conductor |
| `src/harnessgenj_dev/web/dashboard.py` | 修改 | 并行派发、反独白、证据闭环、热加载 API、Event Bus |
| `src/harnessgenj_dev/memory/role_registry.py` | 修改 | 热加载缓存、invalidate_cache() |
| `src/harnessgenj_dev/llm/providers/openai.py` | 修改 | httpx.Timeout 超时配置 |
| `src/harnessgenj_dev/projects.py` | 修改 | github_url 字段支持 |
| `scripts/git-push.sh` | **新增** | 确定性 git push 脚本 |
