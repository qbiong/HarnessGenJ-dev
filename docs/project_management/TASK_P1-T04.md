# 任务分配记录 — P1-T04: Code Executor 完善 + 测试

> **分配时间**: 2026-04-12
> **分配者**: 项目经理（PM）
> **任务优先级**: P0
> **依赖**: P1-T03 基础可用（已满足）

---

## 任务分配

### 子任务 P1-T04-A: Python 执行器增强

**分配角色**: 👨‍💻 开发者（dev_1）
**任务类型**: `implement_feature`

**最小上下文**:
- 已有文件: `src/harnessgenj_dev/executor/python_executor.py`
- 当前实现: 使用临时文件 + subprocess 执行
- 目标: 增强安全性和功能

**具体要求**:
1. 添加内存限制（subprocess 最大内存 256MB）
2. 添加 stdin 输入支持
3. 添加环境变量隔离（不继承父进程环境）
4. 执行前运行安全检查（复用 security.py）
5. 返回执行时间统计

**产物**: 增强 `python_executor.py`
**验收标准**:
- [ ] 内存超限被正确终止
- [ ] 环境变量隔离生效
- [ ] 危险代码被 security.py 拦截

---

### 子任务 P1-T04-B: 安全策略增强

**分配角色**: 👨‍💻 开发者（dev_1）
**任务类型**: `implement_feature`

**最小上下文**:
- 已有文件: `src/harnessgenj_dev/executor/security.py`
- 当前实现: 基于正则的危险模式匹配
- 目标: 增加更多安全检查

**具体要求**:
1. 添加网络访问检测（urllib, httpx, requests, socket）
2. 添加文件系统访问检测（pathlib, os.path 遍历）
3. 添加进程创建检测（subprocess, os.system）
4. 添加动态代码执行检测（eval, exec, compile）
5. 实现安全检查级别配置（strict / moderate / permissive）

**产物**: 增强 `security.py`
**验收标准**:
- [ ] 各类型危险操作被正确检测
- [ ] 安全级别配置生效
- [ ] 误报率低（正常代码不应被误判）

---

### 子任务 P1-T04-C: 执行器测试补充

**分配角色**: 🧪 测试员（tester_1）
**任务类型**: `write_test`

**最小上下文**:
- 已有文件: `tests/executor/test_executor.py`（已有 4 个测试）
- 当前覆盖: 基础执行、超时、安全检测
- 目标: 增加更多边界和异常场景测试

**具体要求**:
1. 测试大输出截断（>10KB）
2. 测试非零退出码
3. 测试 Unicode 编码错误
4. 测试并发执行（两个 PythonExecutor 同时运行）
5. 测试 security.py 各危险模式检测
6. 测试安全级别配置

**产物**: 在 `tests/executor/test_executor.py` 中补充测试用例
**验收标准**:
- [ ] 新增 >= 6 个测试用例
- [ ] 所有测试通过
- [ ] 覆盖 executor 模块 >80%

---

## 任务状态

| 子任务 | 分配角色 | 状态 | 完成时间 |
|--------|---------|------|---------|
| P1-T04-A | 开发者 | 🔄 进行中 | — |
| P1-T04-B | 开发者 | 🔄 进行中 | — |
| P1-T04-C | 测试员 | 🔄 进行中 | — |

---

*创建时间: 2026-04-12 | 状态: 任务已分配，开始执行*
