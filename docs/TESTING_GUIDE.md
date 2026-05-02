# Core Feature Testing Guide

本文档指导如何验证 HarnessGenJ-dev 的各项核心功能是否生效。

## 前置准备

1. 启动 Web Dashboard: `hgj-dev web`
2. 打开 http://localhost:8000
3. 在 Settings 页面配置 DeepSeek V4 API Key（推荐）或其他 LLM

---

## 1. 项目引导 (Project Onboarding)

**验证功能**: 空项目自动检测 + 需求引导

### 测试步骤

1. 打开「项目」标签页
2. 点击「新建」，输入项目名称（不填路径），如 `test-onboarding`
3. 切换到「对话」页面，在左上角项目下拉框中切换到 `test-onboarding`
4. 选择角色为 `Product Manager`
5. 发送消息："你好"

### 预期结果

Agent 应自动识别空项目，引导你：

> 我注意到这是一个新项目。请告诉我：
> - 你想开发什么类型的项目？
> - 目标用户是谁？
> - 你偏好什么技术栈？
> - MVP 需要包含哪些核心功能？

然后 Agent 会：
- 总结你的需求并确认
- 询问是否生成 PROJECT.md
- 生成后展示项目结构和开发计划

---

## 2. 多角色协作 (Multi-Agent Development)

**验证功能**: @mention 分发任务到不同角色

### 测试步骤

1. 在对话页面选择角色为 `Product Manager`
2. 发送消息："我需要开发一个简单的待办事项列表应用，请协调团队完成。"

### 预期结果

PM 角色应通过 @mentions 分配任务：
- `@architect` — 设计应用架构
- `@developer` — 实现具体代码
- `@code_reviewer` — 审查代码质量

---

## 3. 对抗审查 (Adversarial Review)

**验证功能**: 多角色代码审查 + 缺陷发现

### 测试步骤

1. 开发一小段代码文件（如 `app.py`）
2. 发送消息："请审查 app.py 的安全性"

### 预期结果

- Code Reviewer 角色分析代码，指出问题
- Bug Hunter 角色寻找边界条件、竞态条件
- 输出按轮次结构展示

---

## 4. 对话记忆 (Session Memory)

**验证功能**: 跨对话会话持久化

### 测试步骤

1. 发送消息："我叫张三"
2. 点击「会话」→「新建」创建新会话
3. 在新会话中发送："我的名字是什么？"

### 预期结果

Agent 应记住你之前说过的名字（跨会话记忆通过 SharedMemory 实现）。

---

## 5. 上下文管理 (Context Management)

**验证功能**: 大型对话的渐进式压缩

### 测试步骤

1. 连续发送 20+ 条消息，每条包含大量文本或代码文件内容
2. 在后续对话中询问之前的内容

### 预期结果

- 最早的消息内容会被压缩（Tier 1 清理旧 tool results）
- Agent 仍能回忆起关键信息（用户意图、重要概念）
- 不会出现 "上下文过长" 错误

---

## 6. 工作区隔离 (Workspace Isolation)

**验证功能**: 框架与项目代码边界清晰

### 测试步骤

1. 创建一个新的工作区项目
2. 切换到该项目
3. 发送消息："请列出当前目录下的所有文件"

### 预期结果

- Agent 应操作 `~/.hgj-dev/workspace/<project-name>/` 目录
- 不应修改框架自身的任何文件
- 不应把 HarnessGenJ-dev 当作开发目标

---

## 单元测试

```bash
# 运行全部测试
pytest

# 运行特定模块
pytest tests/core/          # Agent 核心测试
pytest tests/llm/           # LLM 网关测试
pytest tests/tools/         # 工具集测试
pytest tests/web/           # Web Dashboard 测试
pytest tests/memory/        # 记忆系统测试
pytest tests/test_projects.py  # 项目管理测试
```

预期: **768 passed, 24 skipped** (24 个端到端测试需配置 API Key)

---

## 关键诊断命令

```bash
# API 状态
curl http://localhost:8000/api/status

# 测试 LLM 连接
curl -X POST http://localhost:8000/api/settings/test

# 查看项目列表
curl http://localhost:8000/api/projects
```
