"""HARNESS.md Loader - 项目级指令加载器。

参考 Claude Code 的 CLAUDE.md 加载机制：
- 加载项目根目录的 HARNESS.md
- 支持父目录递归向上查找
- 解析 frontmatter 中的 paths 规则
- 支持 @import 语法导入额外文件
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 项目命名
HARNESS_FILENAME = "HARNESS.md"
HARNESS_DIR = ".harness"
HARNESS_LOCAL = "HARNESS.local.md"


def find_harness_file(start_path: Path) -> Path | None:
    """从起始路径向上递归查找 HARNESS.md 文件。

    搜索顺序：
    1. ./HARNESS.md
    2. ./.harness/HARNESS.md
    3. ./HARNESS.local.md
    4. 向上递归到父目录

    Args:
        start_path: 起始搜索路径（通常是项目根目录）

    Returns:
        找到的 HARNESS.md 路径，如果未找到返回 None
    """
    current = start_path.resolve()

    # 避免无限递归，限制向上搜索深度
    max_depth = 10
    for _ in range(max_depth):
        if not current.exists() or not current.is_dir():
            break

        # 1. ./HARNESS.md
        harness_path = current / HARNESS_FILENAME
        if harness_path.exists():
            logger.debug(f"Found HARNESS.md at {harness_path}")
            return harness_path

        # 2. ./.harness/HARNESS.md
        harness_dir_path = current / HARNESS_DIR / HARNESS_FILENAME
        if harness_dir_path.exists():
            logger.debug(f"Found HARNESS.md at {harness_dir_path}")
            return harness_dir_path

        # 3. ./HARNESS.local.md (本地偏好)
        local_path = current / HARNESS_LOCAL
        if local_path.exists():
            logger.debug(f"Found HARNESS.local.md at {local_path}")
            return local_path

        # 向上到父目录
        parent = current.parent
        if parent == current:
            break  # 根目录
        current = parent

    return None


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """解析 YAML frontmatter。

    Args:
        content: 文件内容

    Returns:
        (frontmatter_dict, body_content)
    """
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    import yaml

    try:
        frontmatter = yaml.safe_load(parts[1]) or {}
        body = parts[2].strip()
        return frontmatter, body
    except Exception as e:
        logger.warning(f"Failed to parse frontmatter: {e}")
        return {}, content


def resolve_imports(content: str, base_path: Path) -> str:
    """解析 @import 语法，递归导入其他文件。

    语法: @path/to/file.md
    - 相对路径相对于当前文件
    - 最大递归深度: 5 层

    Args:
        content: 文件内容
        base_path: 当前文件所在目录

    Returns:
        展开 @import 后的内容
    """
    import re

    max_depth = 5
    depth = 0

    while depth < max_depth:
        match = re.search(r"@([^\s\n]+)", content)
        if not match:
            break

        import_path = match.group(1)
        full_path = (base_path / import_path).resolve()

        if not full_path.exists():
            logger.warning(f"Import file not found: {full_path}")
            content = content.replace(match.group(0), f"[Import not found: {import_path}]", 1)
            continue

        try:
            imported_content = full_path.read_text(encoding="utf-8")
            # 递归处理被导入的文件
            imported_content = resolve_imports(imported_content, full_path.parent)
            content = content.replace(
                f"@{import_path}",
                f"\n--- Imported from {import_path} ---\n{imported_content}\n--- End import ---",
                1
            )
        except Exception as e:
            logger.warning(f"Failed to import {import_path}: {e}")
            content = content.replace(
                match.group(0),
                f"[Import error: {import_path} - {e}]",
                1
            )

        depth += 1

    return content


def load_harness_for_project(project_path: str | Path) -> str:
    """加载项目的 HARNESS.md 内容。

    Args:
        project_path: 项目根目录路径

    Returns:
        HARNESS.md 内容，如果不存在返回空字符串
    """
    project_path = Path(project_path)

    if not project_path.exists():
        logger.debug(f"Project path does not exist: {project_path}")
        return ""

    harness_path = find_harness_file(project_path)
    if not harness_path:
        logger.debug(f"No HARNESS.md found for project: {project_path}")
        return ""

    try:
        content = harness_path.read_text(encoding="utf-8")

        # 解析 frontmatter
        frontmatter, body = parse_frontmatter(content)

        # 检查 paths 规则（可选的 glob 过滤）
        if frontmatter.get("paths"):
            # 如果指定了 paths 规则，后续可以用于过滤
            # 目前先加载全部内容
            pass

        # 处理 @import 语法
        resolved_content = resolve_imports(body, harness_path.parent)

        logger.info(f"Loaded HARNESS.md from {harness_path}")
        return resolved_content

    except Exception as e:
        logger.error(f"Failed to load HARNESS.md from {harness_path}: {e}")
        return ""


# 全局缓存
_harness_cache: dict[str, str] = {}


def get_harness_for_project(project_path: str | Path) -> str:
    """获取项目的 HARNESS.md 内容（带缓存）。

    Args:
        project_path: 项目根目录路径

    Returns:
        HARNESS.md 内容
    """
    key = str(Path(project_path).resolve())

    if key not in _harness_cache:
        _harness_cache[key] = load_harness_for_project(project_path)

    return _harness_cache[key]


def clear_harness_cache() -> None:
    """清除 HARNESS.md 缓存（用于测试或重新加载）。"""
    global _harness_cache
    _harness_cache.clear()
