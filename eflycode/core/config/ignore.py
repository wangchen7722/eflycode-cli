"""忽略文件管理模块

负责查找和解析 .eflycodeignore 和 .gitignore 文件，提供路径忽略判断功能
忽略文件位置：
- .eflycode/.eflycodeignore
- .gitignore
"""

import fnmatch
from pathlib import Path
from typing import List, Optional

from eflycode.core.config.config_manager import resolve_workspace_dir
from eflycode.core.constants import EFLYCODE_DIR, IGNORE_FILE


def _load_patterns_from_file(ignore_file: Path) -> List[str]:
    """从文件加载忽略模式

    Args:
        ignore_file: 忽略文件路径

    Returns:
        List[str]: 忽略模式列表
    """
    if not ignore_file.exists() or not ignore_file.is_file():
        return []

    patterns = []
    try:
        with open(ignore_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # 跳过空行和注释行
                if line and not line.startswith("#"):
                    patterns.append(line)
    except Exception:
        return []

    return patterns


def _is_git_repository(workspace_dir: Path) -> bool:
    """检测是否为 Git 仓库

    Args:
        workspace_dir: 工作区目录

    Returns:
        bool: 是否为 Git 仓库
    """
    git_dir = workspace_dir / ".git"
    return git_dir.exists() and (git_dir.is_dir() or git_dir.is_file())


def find_gitignore_file(
    workspace_dir: Optional[Path] = None, require_git_repo: bool = True
) -> Optional[Path]:
    """查找 .gitignore 文件

    Args:
        workspace_dir: 工作区目录，如果为 None 则自动解析

    Returns:
        Optional[Path]: 找到的 .gitignore 文件路径，如果没找到返回 None
    """
    if workspace_dir is None:
        workspace_dir = resolve_workspace_dir()
    
    if require_git_repo and not _is_git_repository(workspace_dir):
        return None
    
    gitignore_file = workspace_dir / ".gitignore"
    if gitignore_file.exists() and gitignore_file.is_file():
        return gitignore_file
    return None


def find_ignore_file(workspace_dir: Optional[Path] = None) -> Optional[Path]:
    """查找 .eflycodeignore 文件

    查找逻辑：
    1. 在工作区的 .eflycode/.eflycodeignore 中查找
    2. 返回找到的文件路径，如果没找到返回 None

    Returns:
        Optional[Path]: 找到的 .eflycodeignore 文件路径，如果没找到返回 None
    """
    if workspace_dir is None:
        workspace_dir = resolve_workspace_dir()
    ignore_file = workspace_dir / EFLYCODE_DIR / IGNORE_FILE
    if ignore_file.exists() and ignore_file.is_file():
        return ignore_file
    return None


def load_ignore_patterns(workspace_dir: Optional[Path] = None) -> List[str]:
    """加载忽略模式列表

    从 .eflycode/.eflycodeignore 文件中加载忽略模式

    Returns:
        List[str]: 忽略模式列表，如果文件不存在返回空列表
    """
    ignore_file = find_ignore_file(workspace_dir)
    if ignore_file:
        return _load_patterns_from_file(ignore_file)
    return []


def load_gitignore_patterns(
    workspace_dir: Optional[Path] = None, require_git_repo: bool = True
) -> List[str]:
    """加载 .gitignore 模式列表

    Args:
        workspace_dir: 工作区目录，如果为 None 则自动解析
        require_git_repo: 是否要求存在 Git 仓库，默认 True

    Returns:
        List[str]: 忽略模式列表，如果文件不存在或不是 Git 仓库返回空列表
    """
    gitignore_file = find_gitignore_file(
        workspace_dir, require_git_repo=require_git_repo
    )
    if gitignore_file:
        return _load_patterns_from_file(gitignore_file)
    return []


def load_all_ignore_patterns(
    respect_git_ignore: bool = True,
    respect_eflycode_ignore: bool = True,
    workspace_dir: Optional[Path] = None,
    require_git_repo: bool = True,
) -> List[str]:
    """加载所有忽略模式（.gitignore 和 .eflycodeignore）

    Args:
        respect_git_ignore: 是否加载 .gitignore，默认 True
        respect_eflycode_ignore: 是否加载 .eflycodeignore，默认 True
        workspace_dir: 工作区目录，如果为 None 则自动解析
        require_git_repo: 是否要求存在 Git 仓库，默认 True

    Returns:
        List[str]: 合并后的忽略模式列表
    """
    patterns = []
    
    if respect_git_ignore:
        if workspace_dir is None:
            workspace_dir = resolve_workspace_dir()
        gitignore_patterns = load_gitignore_patterns(
            workspace_dir, require_git_repo=require_git_repo
        )
        patterns.extend(gitignore_patterns)
    
    if respect_eflycode_ignore:
        eflycode_patterns = load_ignore_patterns(workspace_dir)
        patterns.extend(eflycode_patterns)
    
    return patterns


def should_ignore_path(path: Path, ignore_patterns: List[str], base_dir: Path) -> bool:
    """判断路径是否应该被忽略

    使用 fnmatch 进行模式匹配，支持 *、**、! 等模式（类似 .gitignore）

    Args:
        path: 要判断的路径
        ignore_patterns: 忽略模式列表
        base_dir: 基础目录，用于计算相对路径

    Returns:
        bool: True 表示应该忽略，False 表示不忽略
    """
    if not ignore_patterns:
        return False

    try:
        # 将路径转换为相对于 base_dir 的路径
        if path.is_absolute() and base_dir.is_absolute():
            try:
                relative_path = path.relative_to(base_dir)
            except ValueError:
                # 如果 path 不在 base_dir 下，使用绝对路径
                path_str = str(path)
            else:
                path_str = str(relative_path)
        else:
            path_str = str(path)

        # 标准化路径分隔符（统一使用 /）
        path_str = path_str.replace("\\", "/")

        # 检查每个忽略模式
        for pattern in ignore_patterns:
            # 处理否定模式（! 开头）
            if pattern.startswith("!"):
                negate_pattern = pattern[1:].strip()
                if _match_pattern(path_str, negate_pattern, base_dir):
                    return False
            else:
                if _match_pattern(path_str, pattern, base_dir):
                    return True

        return False
    except Exception:
        # 如果匹配过程中出错，默认不忽略
        return False


def _match_pattern(path_str: str, pattern: str, base_dir: Path) -> bool:
    """匹配单个模式

    Args:
        path_str: 要匹配的路径字符串（相对路径，使用 / 作为分隔符）
        pattern: 匹配模式
        base_dir: 基础目录

    Returns:
        bool: 是否匹配
    """
    # 标准化模式中的路径分隔符
    pattern = pattern.replace("\\", "/")

    # 处理 ** 模式（匹配任意路径）
    if "**" in pattern:
        # 简化处理：如果模式以 ** 开头或结尾，使用通配符匹配
        if pattern.startswith("**"):
            # **/pattern 或 **pattern
            if pattern == "**":
                return True
            remaining = pattern[2:].lstrip("/")
            if remaining:
                return fnmatch.fnmatch(path_str, f"*{remaining}") or fnmatch.fnmatch(
                    path_str, remaining
                )
        elif pattern.endswith("**"):
            # pattern/**
            remaining = pattern[:-2].rstrip("/")
            if remaining:
                return path_str.startswith(remaining + "/") or fnmatch.fnmatch(
                    path_str, remaining
                )
        else:
            # pattern/**/pattern
            parts = pattern.split("**")
            if len(parts) == 2:
                prefix = parts[0].rstrip("/")
                suffix = parts[1].lstrip("/")
                if prefix and suffix:
                    return (
                        path_str.startswith(prefix + "/")
                        and path_str.endswith("/" + suffix)
                    ) or fnmatch.fnmatch(path_str, f"{prefix}/*{suffix}")
                elif prefix:
                    return path_str.startswith(prefix + "/") or fnmatch.fnmatch(
                        path_str, prefix
                    )
                elif suffix:
                    return path_str.endswith("/" + suffix) or fnmatch.fnmatch(
                        path_str, suffix
                    )

    # 处理目录模式（以 / 结尾）
    if pattern.endswith("/"):
        pattern = pattern[:-1]
        # 对于目录模式，检查路径是否为目录或路径以该模式开头
        return fnmatch.fnmatch(path_str, pattern) or path_str.startswith(
            pattern + "/"
        )

    # 处理普通模式
    # 支持从根目录开始的模式（以 / 开头）
    if pattern.startswith("/"):
        pattern = pattern[1:]
        return fnmatch.fnmatch(path_str, pattern) or path_str == pattern

    # 支持匹配任意位置的模式
    return (
        fnmatch.fnmatch(path_str, pattern)
        or fnmatch.fnmatch(path_str, f"*/{pattern}")
        or path_str.endswith(f"/{pattern}")
    )

