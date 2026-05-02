# 任务分配记录 — P1-T03: Tool Set 增强

> **分配时间**: 2026-04-12
> **分配者**: 项目经理（PM）
> **任务优先级**: P0
> **依赖**: 无（可立即开始，与 P1-T01 并行）

---

## 任务分配

### 子任务 P1-T03-A: edit_file 工具实现

**分配角色**: 👨‍💻 开发者（dev_1）
**任务类型**: `implement_feature`

**最小上下文**:
- 项目名称: HarnessGenJ-dev
- 已有文件: `src/harnessgenj_dev/tools/file_ops.py`（已有 ReadFileTool, WriteFileTool, ListDirectoryTool）
- 缺失功能: edit_file — 精确文本替换（类似 Claude Code 的 Edit 工具）

**具体要求**:
1. 实现 `EditFileTool` 类，继承 `BaseTool`
2. 参数: `path`（文件路径）、`old_string`（查找文本）、`new_string`（替换文本）、`replace_all`（是否全部替换）
3. 使用精确字符串匹配，不支持正则
4. 如果 `old_string` 不唯一或不存在，返回错误
5. 编辑前读取文件内容确认 `old_string` 存在
6. 编辑后返回编辑结果预览（前后各 3 行）

**产物**: 在 `src/harnessgenj_dev/tools/file_ops.py` 中添加 `EditFileTool` 类
**验收标准**:
- [ ] 精确替换成功（唯一匹配）
- [ ] 不匹配时返回明确错误
- [ ] 多处匹配时提示用户选择 replace_all
- [ ] 测试用例覆盖正常/异常场景

---

### 子任务 P1-T03-B: ripgrep 集成增强

**分配角色**: 👨‍💻 开发者（dev_1）
**任务类型**: `implement_feature`

**最小上下文**:
- 已有文件: `src/harnessgenj_dev/tools/code_ops.py`（已有 SearchCodeTool）
- 目标: 增强搜索功能，支持更多 ripgrep 选项

**具体要求**:
1. 添加 `--context` 参数（显示匹配行前后 N 行）
2. 添加 `--case_sensitive` 参数
3. 添加 `--word_boundary` 参数
4. 输出截断处理（最大 20KB）
5. 如果 ripgrep 未安装，降级到 Python 内置搜索

**产物**: 增强 `SearchCodeTool` 类
**验收标准**:
- [ ] context 参数生效
- [ ] 大小写敏感生效
- [ ] ripgrep 缺失时降级到 Python re 搜索

---

### 子任务 P1-T03-C: 工具注册完善

**分配角色**: 👨‍💻 开发者（dev_1）
**任务类型**: `implement_feature`

**最小上下文**:
- 已有文件: `src/harnessgenj_dev/tools/registry.py`
- 目标: 实现工具自动注册和批量获取 schema

**具体要求**:
1. 实现 `auto_register()` 函数，扫描 tools 目录并注册所有工具
2. 实现 `get_tool_list()` 返回所有已注册工具的名称和描述
3. 实现工具执行日志（记录每次调用的参数和结果）

**产物**: 增强 `registry.py`
**验收标准**:
- [ ] 自动注册发现所有工具
- [ ] 工具列表返回正确
- [ ] 执行日志记录完整

---

## 任务状态

| 子任务 | 分配角色 | 状态 | 完成时间 |
|--------|---------|------|---------|
| P1-T03-A | 开发者 | 🔄 进行中 | — |
| P1-T03-B | 开发者 | 🔄 进行中 | — |
| P1-T03-C | 开发者 | 🔄 进行中 | — |

---

*创建时间: 2026-04-12 | 状态: 任务已分配，开始执行*
