# 用户指南

> **文档**: USER_GUIDE.md
> **作者**: 文档管理员（DocWriter）
> **日期**: 2026-04-12
> **版本**: 1.0

---

## 快速开始

### 1. 安装

```bash
# 克隆项目
git clone <repo-url>
cd HarnessGenJ-dev

# 安装开发依赖
pip install -e ".[dev]"

# 安装可选依赖（推荐）
pip install pyyaml textual
```

### 2. 初始化

```bash
hgj-dev init
```

这会在 `~/.hgj-dev/config.yaml` 创建默认配置文件。

### 3. 设置 API Key

```bash
# Anthropic (推荐)
export ANTHROPIC_API_KEY="sk-ant-..."

# 或 OpenAI
export OPENAI_API_KEY="sk-..."
```

### 4. 开始使用

```bash
# 交互式模式
hgj-dev develop

# 一次性执行
hgj-dev develop "为项目添加一个 REST API 用户端点"

# 代码审查
hgj-dev develop "审查 src/main.py 的安全性" --role code_reviewer

# Bug 查找
hgj-dev develop "找出所有潜在的内存泄漏" --role bug_hunter
```

---

## 使用场景

### 场景 1: 开发新功能

```
hgj-dev develop

hgj-dev> 实现一个用户注册 API，包含邮箱验证和密码哈希
```

Agent 会：
1. 分析现有项目结构
2. 读取相关文件
3. 编写代码
4. 运行测试
5. 返回完整实现

### 场景 2: 代码审查

```
hgj-dev develop --role code_reviewer

hgj-dev> 审查 src/auth/ 目录下的所有代码
```

Agent 会：
1. 列出目录内容
2. 逐个读取文件
3. 分析安全问题、性能瓶颈、代码风格
4. 给出审查报告

### 场景 3: 修复 Bug

```
hgj-dev develop --role bug_hunter

hgj-dev> 查找并修复用户登录模块中的竞态条件
```

### 场景 4: 运行测试

```
hgj-dev develop

hgj-dev> 运行所有测试并修复失败的用例
```

### 场景 5: Git 操作

```
hgj-dev develop

hgj-dev> 查看当前 Git 状态和最近的提交
hgj-dev> 比较 HEAD~3 和 HEAD 的差异
```

---

## 配置指南

### 配置文件位置

`~/.hgj-dev/config.yaml`

### 常用配置项

```yaml
llm:
  provider: anthropic          # 提供商: anthropic, openai, openrouter, local
  model: claude-sonnet-4-6     # 模型 ID
  api_key: ""                  # 留空则使用环境变量
  max_tokens: 4096             # 最大输出 token
  temperature: 0.1             # 温度 (0.0-1.0)

tools:
  default_timeout: 30          # 工具执行超时 (秒)

workflow:
  max_iterations: 20           # Agent 最大迭代次数
```

### 使用 OpenAI

```yaml
llm:
  provider: openai
  model: gpt-4o
  api_key: ""                  # 设置 OPENAI_API_KEY 环境变量
```

### 使用 OpenRouter

```yaml
llm:
  provider: openrouter
  model: anthropic/claude-sonnet-4-6
  api_key: ""                  # 设置 OPENROUTER_API_KEY 环境变量
```

### 使用本地模型 (Ollama)

```yaml
llm:
  provider: local
  model: codellama             # Ollama 模型名
  base_url: http://localhost:11434/v1
  api_key: "not-needed"
```

---

## 命令行参考

| 命令 | 说明 | 示例 |
|------|------|------|
| `hgj-dev init` | 初始化配置 | `hgj-dev init --path /project` |
| `hgj-dev develop "prompt"` | 一次性执行 | `hgj-dev develop "修复登录 bug"` |
| `hgj-dev develop` | 交互模式 | 进入 REPL |
| `hgj-dev develop --role bug_hunter` | 指定角色 | 以 Bug 猎人模式运行 |
| `hgj-dev develop --model gpt-4o` | 指定模型 | 使用 GPT-4o |
| `hgj-dev develop --provider openai` | 指定提供商 | 使用 OpenAI |
| `hgj-dev status` | 查看状态 | 显示配置和工具信息 |
| `hgj-dev help` | 查看帮助 | 显示所有命令 |

### REPL 命令

在交互模式下：

| 输入 | 说明 |
|------|------|
| `quit` | 退出 |
| `help` | 显示帮助 |
| `tools` | 列出工具 |
| `clear` | 清空历史 |
| `role developer` | 切换角色 |

---

## 故障排除

### "No API key provided"

设置环境变量：
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```
或使用 `--api-key` 参数。

### 测试跳过

```
3 skipped (pyyaml x2, textual x1)
```

安装缺失的依赖：
```bash
pip install pyyaml textual
```

### tiktoken 编译失败

Windows 上 tiktoken 编译可能需要 Visual Studio Build Tools。项目已实现降级方案，会自动回退到基于字符数的估算。

### 命令执行超时

增加超时或 max-iterations：
```bash
hgj-dev develop "复杂任务" --max-iterations 50
```

### 工具未注册

确保调用了 `auto_register()`。在 CLI 模式下会自动执行。

---

## 架构概览

```
用户输入 (CLI/TUI)
    │
    ▼
Agent (ReAct 循环)
    │
    ├── LLM Gateway ──→ Anthropic / OpenAI / OpenRouter / Local
    │
    └── Tool Registry
            ├── 文件操作 (read/write/edit/list)
            ├── Shell 命令
            ├── 代码搜索
            ├── 测试执行
            └── Git 操作
```

---

*文档版本: 1.0 | 如需帮助，请查看 docs/ 目录下的其他文档*
