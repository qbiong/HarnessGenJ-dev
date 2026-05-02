# ADR-001: LLM Gateway 接口设计

> **状态**: ✅ 已批准
> **作者**: 架构师（arch_1）
> **日期**: 2026-04-12
> **阶段**: Phase 1
> **关联任务**: P1-T01

---

## 1. 上下文

HarnessGenJ-dev 需要支持多个 LLM 提供商（Anthropic、OpenAI、OpenRouter、Ollama），
同时为 Agent 层提供统一的调用接口。当前 `gateway.py` 仅有骨架，需要完整设计
可扩展的多提供商 LLM 网关接口。

## 2. 决策

### 2.1 架构风格

**决策**: 策略模式（Strategy Pattern）+ 适配器（Adapter）

```
LLMGateway (统一入口)
    │
    └── BaseProvider (抽象基类)
            ├── AnthropicProvider  (anthropic SDK)
            ├── OpenAIProvider     (openai SDK)
            ├── OpenRouterProvider (openai SDK + proxy)
            └── LocalProvider      (httpx → ollama/vLLM)
```

**理由**: 新增提供商只需继承 `BaseProvider` 并实现 3 个方法，不修改已有代码（OCP 原则）。

### 2.2 数据模型

#### LLMResponse（已有，增强）

```python
@dataclass
class LLMResponse:
    content: str              # 响应文本
    usage: UsageReport        # token 使用量
    model: str                # 实际使用的模型
    finish_reason: str        # "stop" | "tool_calls" | "length" | "error"
    raw_response: Any         # 原始响应（调试用）
    tool_calls: list[dict]    # 工具调用列表（如果有）
    error: str | None         # 错误信息（如果有）
```

#### UsageReport（已有，增强）

```python
@dataclass
class UsageReport:
    input_tokens: int         # 输入 token 数
    output_tokens: int        # 输出 token 数
    total_tokens: int         # 总 token 数
    estimated_cost: float     # 估算费用（美元）
    cache_creation_tokens: int = 0   # 缓存创建 token（Anthropic prompt caching）
    cache_read_tokens: int = 0       # 缓存读取 token
```

#### StreamChunk（新增）

```python
@dataclass
class StreamChunk:
    content: str | None       # 增量文本
    done: bool                # 是否完成
    usage: UsageReport | None # 完成时返回使用量
    error: str | None         # 错误信息
```

### 2.3 BaseProvider 抽象接口

```python
class BaseProvider(ABC):
    """所有 LLM 提供商的抽象基类。"""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """返回提供商名称（如 "anthropic", "openai"）。"""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        tools: list[dict] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """发送非流式聊天请求。"""

    @abstractmethod
    async def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        tools: list[dict] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
        """发送流式聊天请求，逐 chunk 产出响应。"""
```

### 2.4 LLMGateway 公共 API

```python
class LLMGateway:
    """统一网关 — Agent 层的唯一入口。"""

    # 构造
    def __init__(self, provider: str = "anthropic", model: str = "claude-sonnet-4-6", api_key: str = "")

    # 核心方法
    async def chat(messages, tools=None, model=None, stream=False, temperature=None, max_tokens=None) -> LLMResponse
    async def stream(messages, tools=None, model=None, temperature=None, max_tokens=None) -> AsyncIterator[StreamChunk]

    # 配置
    def set_provider(provider, model, api_key)      # 切换提供商
    def register_provider(name, provider_instance)   # 注册自定义提供商

    # 统计
    def get_usage_stats() -> UsageReport              # 累计使用量
    def estimate_cost(input_tokens, output_tokens) -> float  # 费用估算
    def reset_usage_stats()                           # 重置累计
```

### 2.5 提供商注册表

```python
# 内置提供商自动注册
_PROVIDER_REGISTRY: dict[str, type[BaseProvider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "openrouter": OpenRouterProvider,
    "ollama": LocalProvider,
}
```

### 2.6 错误处理策略

| 异常类型 | 触发条件 | 处理方式 |
|---------|---------|---------|
| `LLMError` | 所有 LLM 相关错误 | 基类异常 |
| `RateLimitError` | 429 / rate limit | 自动重试（指数退避，最多 3 次） |
| `AuthenticationError` | 401 / 无效 API Key | 立即抛出，不重试 |
| `ModelUnavailable` | 404 / 模型不存在 | 触发降级到次优模型 |
| `TimeoutError` | 请求超时（默认 60s） | 可配置 timeout 参数 |
| `ContextLengthError` | 超过模型上下文窗口 | 触发上下文压缩 |

### 2.7 降级策略

```
请求 claude-sonnet-4-6
    │
    ├── 成功 → 返回结果
    │
    └── 失败（RateLimit / 不可用）
            │
            ├── 降级到 claude-haiku-4-5
            │       │
            │       ├── 成功 → 返回结果（标记为降级）
            │       │
            │       └── 失败 → 降级到 gpt-4o-mini
            │                       │
            │                       └── 成功/失败
            │
            └── 降级到 gpt-4o
                    │
                    └── 成功/失败
```

### 2.8 流式输出设计

**统一 StreamChunk 格式**:
- 所有提供商的流式响应统一转换为 `StreamChunk`
- `content=None, done=False` → 心跳/元数据
- `content="text", done=False` → 增量文本
- `content=None, done=True, usage=...` → 完成信号

**Anthropic SDK**: 使用 `message_stream` API，事件类型为 `content_block_delta`
**OpenAI SDK**: 使用 `chat.completions.create(stream=True)`，chunk 的 `delta.content`

## 3. 提供商实现指南

### 3.1 Anthropic Provider

```python
class AnthropicProvider(BaseProvider):
    """Anthropic Claude API 适配器。"""

    # SDK: anthropic.Anthropic(async=True)
    # 消息格式: messages = [{"role": "user", "content": "..."}, ...]
    # Tool 格式: tools = [{"name": "...", "description": "...", "input_schema": {...}}, ...]
    # 流式: client.messages.stream(model=..., messages=..., tools=...)
    # Token 统计: message.usage.input_tokens, output_tokens
    # Prompt Caching: cache_control={"type": "ephemeral"} on system message
```

### 3.2 OpenAI Provider

```python
class OpenAIProvider(BaseProvider):
    """OpenAI API 适配器。"""

    # SDK: openai.AsyncOpenAI()
    # 消息格式: messages = [{"role": "user", "content": "..."}, ...]
    # Tool 格式: tools = [{"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}, ...]
    # 流式: client.chat.completions.create(model=..., messages=..., tools=..., stream=True)
    # Token 统计: choice.usage.prompt_tokens, completion_tokens
```

### 3.3 接口转换规则

| 概念 | Anthropic | OpenAI | 统一格式 |
|------|-----------|--------|---------|
| 系统消息 | `system` 参数 | `{"role": "system"}` | 内部统一为 system 参数 |
| 工具调用 | `tool_use` block | `function_call` | `{"type": "tool_call", "id": ..., "name": ..., "args": {...}}` |
| 工具结果 | `tool_result` block | `{"role": "tool", "tool_call_id": ...}` | `{"role": "tool", "tool_call_id": ..., "content": "..."}` |

## 4. 后果

- **正面**: 新增提供商只需实现 `BaseProvider` 的 3 个抽象方法
- **正面**: 统一的错误处理和降级策略，调用方不需要关心提供商差异
- **正面**: 流式输出统一为 `StreamChunk`，Agent 层只需处理一种格式
- **风险**: Anthropic 的 tool_use 和 OpenAI 的 function_call 格式不同，转换层需要仔细测试
- **风险**: 不同提供商的 rate limit 策略不同，需要分别处理

---

*状态: ✅ 已完成 | 下一步: 开发者根据此 ADR 实现 Anthropic 和 OpenAI 提供商*
