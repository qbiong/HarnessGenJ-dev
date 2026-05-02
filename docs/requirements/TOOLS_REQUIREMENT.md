# 工具集需求定义

> **文档**: TOOLS_REQUIREMENT.md
> **作者**: 产品经理（PM）
> **日期**: 2026-04-12
> **阶段**: Phase 1
> **版本**: 1.0

---

## 1. 概述

HarnessGenJ-dev 工具集为 AI Agent 提供操作外部系统的能力。每个工具遵循统一接口：`BaseTool` 定义 `name`、`description`、`parameters`、`execute()` 和 `schema()`。

工具通过 `@register("name")` 装饰器或 `auto_register()` 自动发现注册到全局注册表。

---

## 2. 工具分类

### 2.1 文件操作类 (file_ops.py)

| 工具名 | 功能 | 优先级 | 状态 |
|--------|------|--------|------|
| `read_file` | 读取文件内容，支持行范围选择 | P0 | ✅ 完成 |
| `write_file` | 写入文件内容（覆盖创建） | P0 | ✅ 完成 |
| `edit_file` | 精确替换文件中的文本片段 | P0 | ✅ 完成 |
| `list_directory` | 列出目录内容，支持递归 | P0 | ✅ 完成 |

**参数规范**:
```
read_file:  path (required), start_line (int, optional), end_line (int, optional)
write_file: path (required), content (required)
edit_file:  path (required), old_string (required), new_string (required), replace_all (bool, optional)
list_directory: path (required, default="."), recursive (bool, optional, default=false)
```

### 2.2 命令执行类 (shell_ops.py)

| 工具名 | 功能 | 优先级 | 状态 |
|--------|------|--------|------|
| `run_command` | 执行 Shell 命令，支持超时和 stdin | P0 | ✅ 完成 |

**参数规范**:
```
run_command: command (required), timeout (int, optional, default=30), stdin (string, optional)
```

**安全约束**:
- 命令经过 `security.py` 模式检查（destructive/dynamic_code/network/process 级别）
- 超时自动终止进程
- 输出截断到 10KB

### 2.3 代码搜索类 (code_ops.py)

| 工具名 | 功能 | 优先级 | 状态 |
|--------|------|--------|------|
| `search_code` | 全文代码搜索（ripgrep 优先） | P0 | ✅ 完成 |

**参数规范**:
```
search_code: pattern (required), path (string, optional), case_sensitive (bool, optional), word (bool, optional), context_lines (int, optional)
```

**回退策略**:
- 优先使用 `rg` (ripgrep) 二进制
- 未安装时回退到 Python `re` 模块遍历文件

### 2.4 测试执行类 (test_ops.py)

| 工具名 | 功能 | 优先级 | 状态 |
|--------|------|--------|------|
| `run_tests` | 运行 pytest，支持过滤和覆盖率 | P0 | ✅ 完成 |

**参数规范**:
```
run_tests: test_path (string, optional), keyword (string, optional), markers (string, optional), coverage (bool, optional)
```

### 2.5 Git 操作类 (git_ops.py)

| 工具名 | 功能 | 优先级 | 状态 |
|--------|------|--------|------|
| `git_status` | 查看 Git 工作区状态 | P1 | ✅ 完成 |
| `git_diff` | 查看 Git 差异（暂存/未暂存/指定提交） | P1 | ✅ 完成 |
| `git_log` | 查看 Git 提交历史 | P1 | ✅ 完成 |

**参数规范**:
```
git_status: 无
git_diff:   target (string, optional), staged (bool, optional)
git_log:    n_commits (int, optional, default=10), format (string, optional)
```

### 2.6 代码执行类 (executor/)

| 工具名 | 功能 | 优先级 | 状态 |
|--------|------|--------|------|
| Python Executor | 在隔离子进程中执行 Python 代码 | P0 | ✅ 完成 |
| Shell Executor | 在安全沙箱中执行 Shell 命令 | P0 | ✅ 完成 |

**安全约束**:
- 执行前通过 `security.py` 检查（STRICT/MODERATE/PERMISSIVE 三级）
- 环境变量隔离（不继承父进程 PYTHONPATH）
- 超时自动终止
- 输出截断到 10KB

---

## 3. 工具注册协议

### 3.1 注册方式

```python
# 方式 1: 装饰器注册
@register("tool_name")
class MyTool(BaseTool):
    name = "tool_name"
    description = "Do something useful"
    parameters = {...}

# 方式 2: 自动发现
from harnessgenj_dev.tools.registry import auto_register
auto_register()  # 扫描 tools/*_ops.py 并注册所有 BaseTool 子类
```

### 3.2 执行方式

```python
from harnessgenj_dev.tools.registry import execute_tool, get_schemas, get_tool_list

# 执行工具
result = await execute_tool("read_file", path="src/main.py")

# 获取所有工具 schema（用于 LLM 函数调用）
schemas = get_schemas()

# 获取工具列表（名称 + 描述）
tools = get_tool_list()
```

### 3.3 工具结果格式

```python
@dataclass
class ToolResult:
    success: bool           # 是否成功
    content: str            # 成功时的输出内容
    error: str              # 失败时的错误信息
    metadata: dict | None   # 可选元数据（执行时间、文件行数等）
```

---

## 4. 安全策略

### 4.1 安全级别

| 级别 | 适用场景 | 阻断内容 |
|------|---------|---------|
| STRICT | 不受信任的代码 | destructive + dynamic_code + network + process + filesystem |
| MODERATE | 一般代码生成 | destructive + dynamic_code |
| PERMISSIVE | 受信任的代码 | destructive only |

### 4.2 始终阻断的模式

- `rm -rf /` — 递归强制删除根目录
- `format C:` — Windows 格式化磁盘
- `sudo ... (rm|mkfs|dd)` — 危险 sudo 命令
- `os.system(...rm -rf)` — Python 调用系统删除命令
- `shutil.rmtree(...'/')` — 从根目录删除
- `dd of=` — 磁盘写入
- `chmod 777` — 过度开放的文件权限

---

## 5. 未来规划 (Phase 2+)

| 工具名 | 功能 | 优先级 |
|--------|------|--------|
| `search_symbol` | 跨文件符号搜索（基于 AST） | P0 |
| `analyze_ast` | AST 分析（函数/类/导入提取） | P0 |
| `build_project` | 构建项目（支持多种构建系统） | P1 |
| `docker_run` | 在 Docker 容器中执行代码 | P1 |
| `browser_test` | 浏览器端对端测试 | P2 |
| `deploy` | 部署到目标环境 | P2 |

---

*文档版本: 1.0 | 审核状态: 待审核*
