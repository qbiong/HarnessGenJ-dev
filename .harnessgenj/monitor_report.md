
# HGJ 框架状态监控报告

**生成时间**: 2026-04-17 00:19:48
**工作目录**: .harnessgenj
**总体通过率**: 26%

---

## 详细状态

### [hooks] (50%)

- [OK] hooks_configured
- [FAIL] hooks_triggered
- [FAIL] hooks_blocked
- [OK] security_check_active

### [hybrid] (33%)

- [FAIL] active_mode_detected
- [OK] builtin_fallback_active
- [FAIL] events_recorded

### [quality] (50%)

- [FAIL] adversarial_records
- [OK] metrics_calculated
- [OK] score_changes
- [FAIL] patterns_analyzed

### [task_state] (0%)

- [FAIL] tasks_created
- [FAIL] state_transitions
- [FAIL] reviewing_state_used

### [intent_router] (0%)

- [FAIL] intents_identified
- [FAIL] workflow_routed

### [memory] (0%)

- [FAIL] knowledge_stored
- [FAIL] documents_updated
- [FAIL] hotspots_detected

---

## 改进建议

- **Hooks未触发**: 检查 settings.json 配置，确保通过 Write/Edit 工具操作文件
- **意图未识别**: 使用 `harness.chat()` 或框架已自动记录意图到 intents.json
- **知识未存储**: 任务完成时会自动提取知识，或使用 `harness.remember()` 手动存储
- **失败模式未分析**: 需积累多次对抗记录，或调整模式分析阈值

---

> 使用 `python -m harnessgenj.monitor --watch` 进行持续监控
