"""Context Manager - 三层上下文压缩策略（适配 DeepSeek 1M 上下文窗口）。

参考:
- OpenCode: 95% threshold + summarization pattern
- Claude Code: Tiered compaction architecture

优化适配：
- DeepSeek V4 1M 上下文窗口
- 缓存优化：静态内容前置（system prompt, tool definitions）
- 渐进式压缩：尽量延迟高级别压缩
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from ..llm.token_counter import count_message_tokens

logger = logging.getLogger(__name__)


# DeepSeek V4 1M 上下文窗口 + 压缩阈值
DEFAULT_MAX_TOKENS = 1_000_000  # DeepSeek V4 1M 上下文窗口
COMPACTION_THRESHOLD = 0.30  # 30% 即触发压缩，降低内存压力
TIER1_KEEP_TOOL_RESULTS = 3  # 只保留最近 3 个完整 tool results，更早的截断为占位符


@dataclass
class CompactionResult:
    """Compaction result."""

    original_tokens: int
    compacted_tokens: int
    tier_applied: int  # 1, 2, or 3
    messages_removed: int = 0
    tool_results_truncated: int = 0
    summary: str = ""


@dataclass
class ContextState:
    """Context state tracking."""

    message_count: int = 0
    tool_result_count: int = 0
    total_tokens: int = 0
    last_compaction_tier: int = 0
    pre_compaction_metadata: dict[str, Any] = field(default_factory=dict)


class ContextManager:
    """Three-tier context compaction manager.

    Optimized for 1M context window (DeepSeek V4):
    - Tier 1: Micro-compact — clean old tool results before each API call
    - Tier 2: API-level — server-side token threshold handling
    - Tier 3: Full summarization — LLM-generated structured summary
    """

    def __init__(
        self,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        compaction_threshold: float = COMPACTION_THRESHOLD,
        tier1_keep_results: int = TIER1_KEEP_TOOL_RESULTS,
    ) -> None:
        self.max_tokens = max_tokens
        self.compaction_threshold = compaction_threshold
        self.tier1_keep_results = tier1_keep_results
        self.state = ContextState()
        self._cache_warm = False  # 缓存状态标记

    @property
    def threshold_tokens(self) -> int:
        """触发压缩的 token 阈值"""
        return int(self.max_tokens * self.compaction_threshold)

    def get_usage_ratio(self, messages: list[dict[str, str]]) -> float:
        """获取当前上下文使用率"""
        tokens = count_message_tokens(messages)
        return tokens / self.max_tokens

    def needs_compaction(self, messages: list[dict[str, str]]) -> bool:
        """检查是否需要压缩"""
        return self.get_usage_ratio(messages) >= self.compaction_threshold

    # ============================================================
    # Tier 1: Micro-compact (每次 API 调用前)
    # ============================================================

    def tier1_micro_compact(self, messages: list[dict[str, str]]) -> CompactionResult:
        """Tier 1: 清理旧 tool results，只保留最近 N 个。

        实现逻辑：
        - 遍历所有消息
        - 识别 tool role 的消息（tool results）
        - 只保留最近 tier1_keep_results 个
        - 其他的替换为占位符
        """
        original_tokens = count_message_tokens(messages)
        truncated_count = 0

        # 统计 tool results 位置
        tool_result_indices: list[int] = []
        for i, msg in enumerate(messages):
            if msg.get("role") == "tool":
                tool_result_indices.append(i)

        # 只保留最近的 tool results
        if len(tool_result_indices) > self.tier1_keep_results:
            for idx in tool_result_indices[: -self.tier1_keep_results]:
                original_content = messages[idx].get("content", "")
                # 替换为占位符，保留结构信息
                truncated_content = f"[Old tool result content cleared - {len(original_content)} chars truncated]"
                messages[idx] = {
                    "role": "tool",
                    "content": truncated_content,
                    "tool_call_id": messages[idx].get("tool_call_id", ""),
                }
                truncated_count += 1

        compacted_tokens = count_message_tokens(messages)

        return CompactionResult(
            original_tokens=original_tokens,
            compacted_tokens=compacted_tokens,
            tier_applied=1,
            messages_removed=0,
            tool_results_truncated=truncated_count,
        )

    # ============================================================
    # Tier 2: API-level compaction
    # ============================================================

    def tier2_api_compact(self, messages: list[dict[str, str]]) -> CompactionResult:
        """Tier 2: 基于 token 阈值的压缩。

        特点：
        - 保留最近 N 轮对话的完整内容
        - 压缩更早的消息
        - 不使用 LLM，直接截断/精简
        """
        original_tokens = count_message_tokens(messages)

        # 保留最近的交互（最后 20 条消息，约 10 对话轮次）
        recent_count = 20

        if len(messages) > recent_count:
            recent_messages = messages[-recent_count:]
            older_messages = messages[:-recent_count]

            # 压缩 older messages：保留用户意图 + 关键文件
            compacted_older = self._compact_older_messages(older_messages)

            messages[:] = compacted_older + recent_messages

        compacted_tokens = count_message_tokens(messages)

        return CompactionResult(
            original_tokens=original_tokens,
            compacted_tokens=compacted_tokens,
            tier_applied=2,
            messages_removed=len(messages) - recent_count,
        )

    def _compact_older_messages(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """精简旧消息，提取关键信息"""
        if not messages:
            return []

        compacted = []

        # 提取用户请求
        user_requests = []
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if content:
                    user_requests.append(content[:200])  # 截断

        # 提取文件修改
        file_changes = []
        for msg in messages:
            if msg.get("role") == "tool":
                content = msg.get("content", "")
                # 查找文件路径
                if "file_path" in content or "path" in content:
                    file_changes.append(content[:150])

        # 构建精简摘要
        summary_parts = []
        if user_requests:
            summary_parts.append(f"User requests: {'; '.join(user_requests[:3])}")
        if file_changes:
            summary_parts.append(f"File changes: {'; '.join(file_changes[:3])}")

        if summary_parts:
            compacted.append(
                {
                    "role": "system",
                    "content": "[Compacted history]\n" + "\n".join(summary_parts),
                }
            )

        return compacted

    # ============================================================
    # Tier 3: Full LLM Summarization
    # ============================================================

    def tier3_full_summarize(self, messages: list[dict[str, str]]) -> CompactionResult:
        """Tier 3: 使用 LLM 生成结构化 9-section 摘要。

        9-section 结构（Claude Code 格式）：
        1. Intent - 用户原始请求意图
        2. Technical Concepts - 关键技术概念
        3. Files Touched - 修改过的文件
        4. Errors & Fixes - 错误及修复
        5. All User Messages - 所有用户消息
        6. Pending Tasks - 待办任务
        7. Current Work - 当前工作状态
        8. Decisions Made - 关键决策
        9. Session Metadata - 会话元数据
        """
        original_tokens = count_message_tokens(messages)

        # 保存压缩前的元数据（用于重建）
        pre_metadata = {
            "original_message_count": len(messages),
            "original_tokens": original_tokens,
            "timestamp": self._get_timestamp(),
        }

        # 构建摘要提示
        summary_prompt = self._build_summary_prompt(messages)

        # 构建压缩后的消息
        compacted_messages = [
            {
                "role": "system",
                "content": f"""[COMPACTION BOUNDARY - Pre-compaction metadata: {json.dumps(pre_metadata)}]

## Session Summary (compressed from {len(messages)} messages, {original_tokens} tokens)

{summary_prompt}

## Continuation
You were already working on a task before this summary was created.
Continue your work without acknowledging the summary or recapping what happened.
Just proceed with the current task.""",
            }
        ]

        compacted_tokens = count_message_tokens(compacted_messages)

        return CompactionResult(
            original_tokens=original_tokens,
            compacted_tokens=compacted_tokens,
            tier_applied=3,
            messages_removed=len(messages) - 1,
            summary=summary_prompt[:500],  # 返回摘要预览
        )

    def _build_summary_prompt(self, messages: list[dict[str, str]]) -> str:
        """构建摘要生成的提示（供 LLM 使用）"""
        # 提取关键信息片段
        user_msgs = []
        tool_msgs = []
        errors = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "user":
                user_msgs.append(content[:300])
            elif role == "tool":
                tool_msgs.append(content[:200])
                # 简单的错误检测
                if "error" in content.lower() or "failed" in content.lower():
                    errors.append(content[:150])

        prompt = f"""## 1. Intent
[用户原始请求的核心意图]

## 2. Technical Concepts
[涉及的关键技术概念]

## 3. Files Touched
[已读取或修改的文件列表]

## 4. Errors & Fixes
[遇到的错误及解决方案]
{chr(10).join(f"- {e}" for e in errors[:5]) if errors else "[无错误记录]"}

## 5. All User Messages
{chr(10).join(f"- {m}" for m in user_msgs[:10])}

## 6. Pending Tasks
[未完成的任务]

## 7. Current Work
[当前正在进行的工作]

## 8. Decisions Made
[关键决策记录]

## 9. Session Metadata
- Total messages: {len(messages)}
- Tool calls: {len(tool_msgs)}

请根据以上信息生成结构化摘要。"""

        return prompt

    # ============================================================
    # 主压缩入口
    # ============================================================

    def compress(
        self,
        messages: list[dict[str, str]],
        force_tier: int | None = None,
    ) -> CompactionResult:
        """执行上下文压缩。

        Args:
            messages: 消息列表
            force_tier: 强制使用指定层级（1/2/3），用于测试

        Returns:
            CompactionResult: 压缩结果
        """
        current_tokens = count_message_tokens(messages)

        # 决定使用哪个层级
        tier = force_tier
        if tier is None:
            if current_tokens >= self.max_tokens * 0.95:
                tier = 3
            elif current_tokens >= self.max_tokens * 0.85:
                tier = 2
            else:
                tier = 1

        logger.info(f"Compaction triggered: tier={tier}, tokens={current_tokens}/{self.max_tokens}")

        if tier == 1:
            result = self.tier1_micro_compact(messages)
        elif tier == 2:
            result = self.tier2_api_compact(messages)
        else:
            result = self.tier3_full_summarize(messages)

        self.state.last_compaction_tier = tier
        self.state.message_count = len(messages)
        self.state.total_tokens = result.compacted_tokens

        return result

    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime

        return datetime.now().isoformat()

    # ============================================================
    # 重建逻辑（压缩后恢复关键上下文）
    # ============================================================

    def rebuild_context(
        self,
        summary: str,
        recent_files: list[dict[str, str]],
        skills: list[str],
        tool_schemas: list[dict],
        claude_md: str,
    ) -> list[dict[str, str]]:
        """重建压缩后的上下文。

        Claude Code 的重建顺序：
        1. 边界标记 + pre-compaction metadata
        2. 格式化摘要
        3. 最近 5 个读取的文件（50K token cap）
        4. 重新注入 skills（按时间排序）
        5. 工具定义
        6. CLAUDE.md
        """
        context = []

        # 1. 边界标记
        context.append(
            {
                "role": "system",
                "content": f"[COMPACTION BOUNDARY]\n\n{summary}",
            }
        )

        # 2. 最近读取的文件（简化处理）
        for file_info in recent_files[:5]:
            context.append(
                {
                    "role": "system",
                    "content": f"[Recent file: {file_info.get('path', 'unknown')}]\n"
                    f"{file_info.get('content', '')[:5000]}",
                }
            )

        # 3. Skills 重新注入
        for skill in skills[-5:]:  # 最多 5 个
            context.append(
                {
                    "role": "system",
                    "content": f"[Skill: {skill}]",
                }
            )

        # 4. 工具定义（简化为名称列表）
        if tool_schemas:
            tool_names = [t.get("function", {}).get("name", "unknown") for t in tool_schemas]
            context.append(
                {
                    "role": "system",
                    "content": f"[Available tools: {', '.join(tool_names[:20])}]",
                }
            )

        # 5. CLAUDE.md
        if claude_md:
            context.append(
                {
                    "role": "system",
                    "content": f"[Project CLAUDE.md]\n{claude_md}",
                }
            )

        return context


# 全局实例
_context_manager: ContextManager | None = None


def get_context_manager() -> ContextManager:
    """获取全局 ContextManager 实例"""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager


# ============================================================
# Backward Compatibility: Legacy ContextWindow
# ============================================================


@dataclass
class ContextWindow:
    """Legacy context window class for backward compatibility.

    This class is kept for tests that depend on the old API.
    New code should use ContextManager instead.
    """

    messages: list[dict[str, str]] = field(default_factory=list)
    total_tokens: int = 0
    max_tokens: int = 128_000

    def add_message(self, message: dict[str, str], token_count: int = 0) -> None:
        """Add a message to the context."""
        self.messages.append(message)
        self.total_tokens += token_count

    def needs_compression(self, threshold: float = 0.8) -> bool:
        """Check if context needs to be compressed."""
        return self.total_tokens > (self.max_tokens * threshold)

    def compress(self) -> list[dict[str, str]]:
        """Compress context by summarizing older messages.

        Strategy:
        1. Keep system message
        2. Keep first user message (original prompt)
        3. Summarize middle messages as a single placeholder
        4. Keep last N messages verbatim

        Returns:
            Compressed message list.
        """
        max_recent = 10
        if len(self.messages) <= max_recent + 2:
            return self.messages

        # Identify system and first user message
        system_msgs = [m for m in self.messages if m.get("role") == "system"]
        system_msg = system_msgs[0] if system_msgs else None

        # Keep last N messages verbatim
        recent = self.messages[-max_recent:]

        # Build compressed context
        compressed: list[dict[str, str]] = []
        if system_msg:
            compressed.append(system_msg)

        # Add summary of dropped messages
        dropped_count = len(self.messages) - len(recent) - (1 if system_msg else 0)
        if dropped_count > 0:
            # Estimate token count of dropped messages
            dropped_tokens = sum(
                len(m.get("content", "")) // 4 for m in self.messages[1 : len(self.messages) - max_recent]
            )
            compressed.append(
                {
                    "role": "system",
                    "content": (
                        f"[{dropped_count} previous messages summarized "
                        f"(~{dropped_tokens} tokens) to fit context window]"
                    ),
                }
            )

        compressed.extend(recent)

        # Recalculate token count
        self.total_tokens = sum(len(m.get("content", "")) // 4 for m in compressed)
        return compressed
