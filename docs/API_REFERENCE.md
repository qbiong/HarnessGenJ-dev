# API 参考文档

> **文档**: API_REFERENCE.md
> **作者**: 文档管理员（DocWriter）
> **日期**: 2026-04-12
> **版本**: 1.0

---

## 目录

- [CLI 接口](#cli-接口)
- [LLM Gateway](#llm-gateway)
- [Agent Core](#agent-core)
- [Tool Registry](#tool-registry)
- [Code Executor](#code-executor)
- [Configuration](#configuration)
- [数据模型](#数据模型)

---

## CLI 接口

### 命令格式

```bash
hgj-dev [command] [options]
```

### 子命令

#### `hgj-dev init`

初始化项目配置文件到 `~/.hgj-dev/config.yaml`。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--path` | string | `.` | 项目根目录路径 |

**示例**:
```bash
hgj-dev init --path /path/to/project
```

#### `hgj-dev develop`

启动开发会话。可传入一次性 prompt 或进入交互 REPL。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `prompt` | string | - | 一次性 prompt（省略则进入 REPL） |
| `--role` | string | `developer` | 角色: developer, code_reviewer, bug_hunter, architect, product_manager, doc_writer |
| `--model` | string | - | 覆盖默认模型 |
| `--provider` | string | - | 覆盖默认提供商 (anthropic, openai) |
| `--api-key` | string | - | API Key（也可通过环境变量设置） |
| `--max-iterations` | int | 20 | ReAct 循环最大迭代次数 |

**示例**:
```bash
hgj-dev develop "添加一个用户认证模块"
hgj-dev develop --role bug_hunter --max-iterations 30
hgj-dev develop --provider openai --model gpt-4o
```

#### `hgj-dev status`

显示项目状态（配置、工具数量、测试概要）。

#### `hgj-dev review`

代码审查模式（等同于 `develop --role code_reviewer`）。

#### `hgj-dev help`

显示帮助信息。

### REPL 内置命令

在交互式模式下可用：

| 命令 | 说明 |
|------|------|
| `quit` / `exit` / `q` | 退出 |
| `help` / `h` | 显示帮助 |
| `tools` | 列出可用工具 |
| `clear` | 清空对话历史 |
| `role <name>` | 切换角色 |

---

## LLM Gateway

### LLMGateway

统一入口，Agent 层调用 LLM 的唯一接口。

```python
from harnessgenj_dev.llm.gateway import LLMGateway

gateway = LLMGateway(
    provider="anthropic",    # 提供商: anthropic, openai, openrouter, local
    model="claude-sonnet-4-6",
    api_key="",              # 也可设置 ANTHROPIC_API_KEY / OPENAI_API_KEY 环境变量
    base_url=None,           # 可选: 自定义 API 端点
)
```

#### `chat()`

非流式聊天完成。

```python
response = await gateway.chat(
    messages=[{"role": "user", "content": "Hello"}],
    tools=None,              # 可选: 工具 schema 列表
    model=None,              # 可选: 覆盖默认模型
    stream=False,
    temperature=0.1,
    max_tokens=4096,
)
# 返回: LLMResponse
```

#### `stream()`

流式聊天完成，逐 chunk 产出。

```python
async for chunk in gateway.stream(
    messages=[{"role": "user", "content": "Hello"}],
    tools=None,
    model=None,
    temperature=0.1,
    max_tokens=4096,
):
    if chunk.content:
        print(chunk.content, end="")
    if chunk.done:
        print(f"\nTokens: {chunk.usage.total_tokens}")
```

#### `set_provider()`

切换默认提供商。

```python
gateway.set_provider("openai", "gpt-4o")
```

#### `register_provider()`

注册自定义提供商实例。

```python
from harnessgenj_dev.llm.providers import OpenRouterProvider

gateway.register_provider("custom", OpenRouterProvider(api_key="..."))
```

#### `get_usage_stats()`

获取累计使用量。

```python
stats = gateway.get_usage_stats()
print(f"Tokens: {stats.total_tokens}, Cost: ${stats.estimated_cost:.4f}")
```

#### `estimate_cost()`

估算费用。

```python
cost = gateway.estimate_cost(input_tokens=1000, output_tokens=500)
```

#### `reset_usage_stats()`

重置累计使用量。

---

### Provider 基类

```python
from harnessgenj_dev.llm.providers import BaseProvider

class MyProvider(BaseProvider):
    @property
    def provider_name(self) -> str:
        return "my_provider"

    async def chat(self, messages, model, system=None, tools=None, temperature=0.1, max_tokens=4096) -> LLMResponse:
        ...

    async def stream(self, messages, model, system=None, tools=None, temperature=0.1, max_tokens=4096):
        yield StreamChunk(...)
```

### 内置 Provider

| Provider | 类 | 说明 |
|----------|-----|------|
| `anthropic` | `AnthropicProvider` | Claude API (anthropic SDK) |
| `openai` | `OpenAIProvider` | OpenAI API (openai SDK) |
| `openrouter` | `OpenRouterProvider` | OpenRouter 统一网关 |
| `local` | `LocalProvider` | Ollama/vLLM/LM Studio (OpenAI 兼容) |

---

## Agent Core

### Agent

```python
from harnessgenj_dev.core.agent import Agent
from harnessgenj_dev.llm.gateway import LLMGateway

gateway = LLMGateway(provider="anthropic", api_key="...")
agent = Agent(llm_gateway=gateway)
```

#### `run()`

同步执行。

```python
result = await agent.run("添加用户认证功能", role="developer")
print(result)  # 最终响应文本
```

#### `run_stream()`

流式执行。

```python
async for chunk in agent.run_stream("添加用户认证功能"):
    print(chunk, end="")
```

#### `interrupt()`

中断当前执行。

```python
agent.interrupt()
```

### 支持的角色

| 角色 | 说明 |
|------|------|
| `developer` | 编写代码，遵循 SOLID/KISS/DRY/YAGNI |
| `code_reviewer` | 代码审查，关注 bug/安全/性能 |
| `bug_hunter` | 激进 bug 查找（边缘情况/竞态/内存泄漏） |
| `architect` | 架构设计，关注分离原则和接口 |
| `product_manager` | 产品策略和需求优先级 |
| `doc_writer` | 文档编写，清晰准确 |

---

## Tool Registry

### 注册工具

```python
from harnessgenj_dev.tools.registry import register, auto_register

# 装饰器注册
@register("my_tool")
class MyTool(BaseTool):
    name = "my_tool"
    description = "Does something"
    parameters = {"type": "object", "properties": {}}

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, content="Done!")

# 自动发现
registered = auto_register()  # 扫描 tools/*_ops.py
```

### 执行工具

```python
from harnessgenj_dev.tools.registry import execute_tool, get_schemas, get_tool_list

result = await execute_tool("read_file", path="src/main.py")
schemas = get_schemas()        # LLM 函数调用 schema
tools = get_tool_list()        # 名称 + 描述列表
```

### 内置工具

| 工具名 | 模块 | 说明 |
|--------|------|------|
| `read_file` | file_ops | 读取文件内容 |
| `write_file` | file_ops | 写入文件 |
| `edit_file` | file_ops | 精确替换文本 |
| `list_directory` | file_ops | 列出目录 |
| `run_command` | shell_ops | 执行 Shell 命令 |
| `search_code` | code_ops | 全文代码搜索 |
| `run_tests` | test_ops | 运行 pytest |
| `git_status` | git_ops | Git 工作区状态 |
| `git_diff` | git_ops | Git 差异查看 |
| `git_log` | git_ops | Git 提交历史 |

---

## Code Executor

### PythonExecutor

```python
from harnessgenj_dev.executor.python_executor import PythonExecutor

executor = PythonExecutor()
result = await executor.execute('print("hello")', timeout=30, stdin="input data")
print(result.stdout)
print(result.metadata["elapsed_seconds"])
```

### ShellExecutor

```python
from harnessgenj_dev.executor.shell_executor import ShellExecutor

executor = ShellExecutor()
result = await executor.execute("ls -la", timeout=10)
```

### 安全策略

```python
from harnessgenj_dev.executor.security import is_safe_to_run, SecurityLevel

safe, reason = is_safe_to_run("eval(input())", level=SecurityLevel.STRICT)
if not safe:
    print(f"Blocked: {reason}")
```

---

## Configuration

### AppConfig

```python
from harnessgenj_dev.config import AppConfig

# 默认配置
config = AppConfig()

# 从 YAML 加载
config = AppConfig.load()           # 从 ~/.hgj-dev/config.yaml
config = AppConfig.load("config.yaml")  # 从指定路径

# 保存配置
config.save("config.yaml")
```

### 配置结构

```yaml
llm:
  provider: anthropic
  model: claude-sonnet-4-6
  api_key: ""
  base_url: null
  max_tokens: 4096
  temperature: 0.1

tools:
  enabled_tools:
    - read_file
    - write_file
    - edit_file
    - search_code
    - run_command
    - run_test
    - git_ops
  default_timeout: 30

workflow:
  default_pipeline: develop
  max_iterations: 20
  adversarial_cycles: 3

project_root: "."
```

---

## 数据模型

### LLMResponse

```python
@dataclass
class LLMResponse:
    content: str                  # 响应文本
    usage: UsageReport            # Token 使用量
    model: str                    # 实际使用的模型
    finish_reason: str            # "stop" | "tool_calls" | "length" | "error"
    raw_response: Any             # 原始响应
    tool_calls: list[dict]        # 工具调用列表
    error: str | None             # 错误信息
```

### UsageReport

```python
@dataclass
class UsageReport:
    input_tokens: int             # 输入 token
    output_tokens: int            # 输出 token
    total_tokens: int             # 总 token
    estimated_cost: float         # 估算费用 (USD)
    cache_creation_tokens: int    # 缓存创建 token (Anthropic)
    cache_read_tokens: int        # 缓存读取 token (Anthropic)
```

### StreamChunk

```python
@dataclass
class StreamChunk:
    content: str | None           # 增量文本
    done: bool                    # 是否完成
    usage: UsageReport | None     # 完成时使用量
    error: str | None             # 错误信息
```

### ToolResult

```python
@dataclass
class ToolResult:
    success: bool                 # 是否成功
    content: str                  # 输出内容
    error: str                    # 错误信息
    metadata: dict | None         # 元数据
```

### ExecutionResult

```python
@dataclass
class ExecutionResult:
    success: bool                 # 是否成功
    stdout: str                   # 标准输出
    stderr: str                   # 标准错误
    exit_code: int                # 退出码
    timed_out: bool               # 是否超时
    metadata: dict                # 元数据 (如 elapsed_seconds)
```

---

*文档版本: 1.0 | 更新频率: 随 API 变更同步更新*
