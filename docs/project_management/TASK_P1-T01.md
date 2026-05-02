# 任务分配记录 — P1-T01: LLM Gateway 实现

> **分配时间**: 2026-04-12
> **分配者**: 项目经理（PM）
> **任务优先级**: P0（最高优先级，关键路径）
> **依赖**: 无

---

## 任务分配

### 子任务 P1-T01-A: LLM Gateway 接口契约设计

**分配角色**: 🏗️ 架构师（arch_1）
**任务类型**: `design_system`

**最小上下文**:
- 项目名称: HarnessGenJ-dev
- 技术栈: Python 3.11+, httpx, anthropic, openai
- 已有文件: `src/harnessgenj_dev/llm/gateway.py`（骨架）
- 目标: 设计可扩展的多提供商 LLM 网关接口

**具体要求**:
1. 定义 `LLMGateway` 类的完整公共 API
2. 定义 `LLMResponse`、`UsageReport` 等数据模型
3. 定义提供商适配器的抽象接口
4. 定义模型选择/降级策略接口
5. 输出为 ADR（Architecture Decision Record）文档

**产物**: `docs/architecture/ADR-001-llm-gateway.md`
**验收标准**:
- [ ] API 设计清晰，调用方能方便使用
- [ ] 支持多提供商扩展（新增提供商只需实现适配器）
- [ ] 包含流式和非流式两种调用方式
- [ ] 定义错误处理策略
- [ ] 不包含代码实现细节（只做接口定义）

**交付后回调**: 开发者（dev_1）

---

### 子任务 P1-T01-B: Anthropic 提供商实现

**分配角色**: 👨‍💻 开发者（dev_1）
**任务类型**: `implement_feature`

**前置依赖**: P1-T01-A（架构师的 ADR）
**最小上下文**:
- 项目名称: HarnessGenJ-dev
- 技术栈: `anthropic>=0.18.0` SDK
- 已有文件: `src/harnessgenj_dev/llm/gateway.py`（骨架）
- 目标文件: `src/harnessgenj_dev/llm/providers/anthropic.py`

**具体要求**:
1. 实现 `AnthropicProvider` 类，遵循 ADR 定义的适配器接口
2. 支持 `claude-opus-4-6`、`claude-sonnet-4-6`、`claude-haiku-4-5-20251001`
3. 实现 `chat()` 和 `stream()` 方法
4. 正确处理 tool use（Anthropic 的 tool 格式）
5. 返回标准化的 `LLMResponse` 格式
6. 处理 API 错误（rate limit, invalid key, etc.）

**产物**: `src/harnessgenj_dev/llm/providers/anthropic.py` + 测试
**验收标准**:
- [ ] 能成功调用 Anthropic API（需 API Key）
- [ ] 支持流式输出
- [ ] Token 使用量正确返回
- [ ] 错误处理完善

---

### 子任务 P1-T01-C: OpenAI 提供商实现

**分配角色**: 👨‍💻 开发者（dev_1）
**任务类型**: `implement_feature`

**前置依赖**: P1-T01-A 完成
**目标文件**: `src/harnessgenj_dev/llm/providers/openai.py`

**具体要求**:
1. 实现 `OpenAIProvider` 类
2. 支持 `gpt-4o`、`gpt-4o-mini` 模型
3. 实现 `chat()` 和 `stream()` 方法
4. 正确处理 tool use（OpenAI 的 function calling 格式）
5. 返回标准化的 `LLMResponse` 格式

---

### 子任务 P1-T01-D: 模型路由与降级

**分配角色**: 👨‍💻 开发者（dev_1）
**任务类型**: `implement_feature`

**前置依赖**: P1-T01-A 完成
**目标文件**: `src/harnessgenj_dev/llm/model_router.py`（增强现有骨架）

**具体要求**:
1. 实现自动模型选择逻辑（根据任务类型选择最优模型）
2. 实现降级策略（API 不可用时自动降级到次优模型）
3. 集成成本估算功能

---

## 任务状态

| 子任务 | 分配角色 | 状态 | 完成时间 |
|--------|---------|------|---------|
| P1-T01-A | 架构师 | 🔄 进行中 | — |
| P1-T01-B | 开发者 | ⏳ 等待依赖 | — |
| P1-T01-C | 开发者 | ⏳ 等待依赖 | — |
| P1-T01-D | 开发者 | ⏳ 等待依赖 | — |

---

*创建时间: 2026-04-12 | 状态: 任务已分配，等待执行*
