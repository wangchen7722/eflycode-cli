import fnmatch
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from eflycode.core.config.config_manager import resolve_workspace_dir
from eflycode.core.utils.checkpoint import capture_tool_checkpoint
from eflycode.core.config.ignore import (
    load_all_ignore_patterns,
    should_ignore_path,
)
from eflycode.core.llm.protocol import ToolFunctionParameters
from eflycode.core.tool.base import BaseTool, ToolGroup, ToolType
from eflycode.core.tool.errors import ToolExecutionError


def _is_text_file(file_path: str) -> bool:
    """判断文件是否为文本文件

    Args:
        file_path: 文件路径

    Returns:
        bool: 是否为文本文件
    """
    p = Path(file_path)
    if not p.exists() or not p.is_file():
        return False
    
    try:
        data = p.open("rb").read(1024)
    except Exception:
        return False
    
    if not data:
        return True
    
    if b"\x00" in data:
        return False
    
    return True


def _count_lines(file_path: str) -> Optional[int]:
    """计算文本文件的行数

    Args:
        file_path: 文件路径

    Returns:
        Optional[int]: 行数，如果不是文本文件则返回 None
    """
    if not _is_text_file(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return None


def _safe_path(path: str, base_dir: Optional[str] = None) -> Path:
    """验证路径安全性，防止路径遍历攻击

    Args:
        path: 文件路径
        base_dir: 基础目录，如果提供则限制路径在此目录下

    Returns:
        Path: 规范化的路径对象

    Raises:
        ToolExecutionError: 如果路径不安全
    """
    try:
        resolved = Path(path).resolve()
        if base_dir:
            base = Path(base_dir).resolve()
            if not str(resolved).startswith(str(base)):
                raise ToolExecutionError(
                    message=f"路径超出允许范围: {path}",
                    tool_name="file_system_tool",
                )
        return resolved
    except Exception as e:
        raise ToolExecutionError(
            message=f"无效的路径: {path}",
            tool_name="file_system_tool",
            error_details=e,
        ) from e


class ListDirectoryTool(BaseTool):
    """列出目录下的文件和子目录"""

    @property
    def name(self) -> str:
        return "list_directory"

    @property
    def type(self) -> str:
        return ToolType.FUNCTION

    @property
    def permission(self) -> str:
        return "read"

    @property
    def description(self) -> str:
        return "直接列出指定目录路径下的文件和子目录的名称。可以选择性地忽略与提供的通配符模式匹配的条目。文本文件会显示行数，文件夹会显示包含的项目数量。"

    @property
    def display_name(self) -> str:
        return "List"

    def display(self, dir_path: str = "", **kwargs) -> str:
        """工具显示名称"""
        if dir_path:
            return f"{self.display_name} {dir_path}"
        return self.display_name

    @property
    def parameters(self) -> ToolFunctionParameters:
        return ToolFunctionParameters(
            properties={
                "dir_path": {
                    "type": "string",
                    "description": "要列出的目录路径。可以是绝对路径，也可以是相对于工作区的路径。",
                },
                "ignore": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "额外的 glob 模式列表，在最终输出前剔除匹配的条目。",
                },
                "file_filtering_options": {
                    "type": "object",
                    "properties": {
                        "respect_git_ignore": {
                            "type": "boolean",
                            "description": "是否根据 .gitignore 过滤目录项。默认 true，仅在 Git 仓库中生效。",
                            "default": True,
                        },
                        "respect_eflycode_ignore": {
                            "type": "boolean",
                            "description": "是否应用 .eflycodeignore。默认 true。",
                            "default": True,
                        },
                    },
                },
            },
            required=["dir_path"],
        )

    def _count_items(
        self,
        directory: Path,
        max_depth: int,
        current_depth: int = 0,
        ignore_patterns: Optional[List[str]] = None,
        base_dir: Optional[Path] = None,
    ) -> int:
        """统计目录中的项目数量

        Args:
            directory: 目录路径
            max_depth: 最大递归深度
            current_depth: 当前深度
            ignore_patterns: 忽略模式列表
            base_dir: 基础目录，用于计算相对路径

        Returns:
            int: 项目数量
        """
        count = 0
        try:
            items = list(directory.iterdir())
            
            # 过滤被忽略的项目
            if ignore_patterns and base_dir:
                filtered_items = []
                for item in items:
                    if not should_ignore_path(item, ignore_patterns, base_dir):
                        filtered_items.append(item)
                items = filtered_items
            
            for item in items:
                if item.is_file():
                    count += 1
                elif item.is_dir():
                    count += 1  # 目录本身算一个
                    # 如果还没达到最大深度，递归统计子目录
                    if current_depth + 1 < max_depth:
                        count += self._count_items(
                            item, max_depth, current_depth + 1, ignore_patterns, base_dir
                        )
        except (PermissionError, OSError):
            pass

        return count

    def _build_tree(
        self,
        directory: Path,
        prefix: str = "",
        is_last: bool = True,
        current_depth: int = 0,
        max_depth: int = 1,
        ignore_patterns: Optional[List[str]] = None,
        base_dir: Optional[Path] = None,
    ) -> str:
        """构建目录树

        Args:
            directory: 目录路径
            prefix: 前缀字符串
            is_last: 是否为最后一个节点
            current_depth: 当前递归深度
            max_depth: 最大递归深度
            ignore_patterns: 忽略模式列表
            base_dir: 基础目录，用于计算相对路径

        Returns:
            str: 树状文本
        """
        result = []
        try:
            items = sorted(directory.iterdir(), key=lambda x: (x.is_file(), x.name))

            # 过滤被忽略的项目
            if ignore_patterns and base_dir:
                filtered_items = []
                for item in items:
                    if not should_ignore_path(item, ignore_patterns, base_dir):
                        filtered_items.append(item)
                items = filtered_items

            for i, item in enumerate(items):
                is_last_item = i == len(items) - 1
                current_prefix = "└── " if is_last_item else "├── "
                full_prefix = prefix + current_prefix

                if item.is_file():
                    line_count = _count_lines(str(item))
                    if line_count is not None:
                        result.append(f"{full_prefix}{item.name} ({line_count} lines)")
                    else:
                        result.append(f"{full_prefix}{item.name}")
                else:
                    # 如果是目录
                    if current_depth >= max_depth:
                        # 达到最大深度，只显示目录名和项目数量
                        item_count = self._count_items(
                            item, max_depth, current_depth, ignore_patterns, base_dir
                        )
                        result.append(f"{full_prefix}{item.name}/ ({item_count} items)")
                    else:
                        # 继续递归
                        result.append(f"{full_prefix}{item.name}/")
                        next_prefix = prefix + ("    " if is_last_item else "│   ")
                        result.append(
                            self._build_tree(
                                item,
                                next_prefix,
                                is_last_item,
                                current_depth + 1,
                                max_depth,
                                ignore_patterns,
                                base_dir,
                            )
                        )

        except PermissionError:
            result.append(f"{prefix}└── [权限不足]")

        return "\n".join(result)

    def do_run(
        self,
        dir_path: str,
        ignore: Optional[List[str]] = None,
        file_filtering_options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """执行列出目录操作

        Args:
            dir_path: 目录路径
            ignore: 额外的 glob 模式列表
            file_filtering_options: 文件过滤选项

        Returns:
            str: 目录列表文本
        """
        safe_path = _safe_path(dir_path)
        if not safe_path.exists():
            raise ToolExecutionError(
                message=f"目录不存在: {dir_path}",
                tool_name=self.name,
            )
        if not safe_path.is_dir():
            raise ToolExecutionError(
                message=f"路径不是目录: {dir_path}",
                tool_name=self.name,
            )

        # 确定基础目录（工作区目录）
        workspace_dir = resolve_workspace_dir()
        base_dir = workspace_dir

        # 解析文件过滤选项
        if file_filtering_options is None:
            file_filtering_options = {}
        respect_git_ignore = file_filtering_options.get("respect_git_ignore", True)
        respect_eflycode_ignore = file_filtering_options.get("respect_eflycode_ignore", True)

        # 加载忽略模式
        ignore_patterns = load_all_ignore_patterns(
            respect_git_ignore=respect_git_ignore,
            respect_eflycode_ignore=respect_eflycode_ignore,
            workspace_dir=workspace_dir,
        )

        # 添加自定义 ignore 模式
        if ignore:
            ignore_patterns.extend(ignore)

        # 构建目录树（保留现有特性：显示行数和项目数）
        tree = self._build_tree(
            safe_path,
            max_depth=1,  # 只列出直接子项，符合参考文档
            ignore_patterns=ignore_patterns if ignore_patterns else None,
            base_dir=base_dir,
        )

        # 统计忽略数量
        all_items = list(safe_path.iterdir())
        ignored_count = 0
        if ignore_patterns:
            for item in all_items:
                if should_ignore_path(item, ignore_patterns, base_dir):
                    ignored_count += 1

        # 格式化返回（按照参考文档格式）
        result = f"Directory listing for {dir_path}\n\n{tree}"
        item_count = len(all_items) - ignored_count
        return f"{result}\n\nListed {item_count} item(s). ({ignored_count} ignored)"


class ReadFileTool(BaseTool):
    """读取文件内容"""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def type(self) -> str:
        return ToolType.FUNCTION

    @property
    def permission(self) -> str:
        return "read"

    @property
    def description(self) -> str:
        return "读取并返回指定文件的内容。如果文件很大，内容将被截断。工具响应会清楚地指示是否发生了截断，并提供如何使用 'offset' 和 'limit' 参数读取更多文件的详细信息。处理文本、图片（PNG、JPG、GIF、WEBP、SVG、BMP）、音频文件（MP3、WAV、AIFF、AAC、OGG、FLAC）和 PDF 文件。对于文本文件，可以读取特定的行范围。"

    @property
    def display_name(self) -> str:
        return "Read"

    def display(self, file_path: str = "", **kwargs) -> str:
        """工具显示名称"""
        if file_path:
            return f"{self.display_name} {file_path}"
        return self.display_name

    @property
    def parameters(self) -> ToolFunctionParameters:
        return ToolFunctionParameters(
            properties={
                "file_path": {
                    "type": "string",
                    "description": "要读取的文件路径（相对于 workspace 或绝对路径均可）。",
                },
                "offset": {
                    "type": "integer",
                    "description": "（仅文本）读取的 0 基起始行。设置该值时也必须提供 limit。",
                },
                "limit": {
                    "type": "integer",
                    "description": "（仅文本）最多读取的行数，用于分页。",
                },
            },
            required=["file_path"],
        )

    def _read_binary_file(self, file_path: Path) -> str:
        """读取二进制文件（图片、音频、PDF）并返回 base64 编码

        Args:
            file_path: 文件路径

        Returns:
            str: base64 编码的字符串表示
        """
        import base64
        import mimetypes

        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            # 根据扩展名判断
            ext = file_path.suffix.lower()
            mime_map = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".gif": "image/gif",
                ".webp": "image/webp",
                ".svg": "image/svg+xml",
                ".bmp": "image/bmp",
                ".mp3": "audio/mpeg",
                ".wav": "audio/wav",
                ".aiff": "audio/aiff",
                ".aac": "audio/aac",
                ".ogg": "audio/ogg",
                ".flac": "audio/flac",
                ".pdf": "application/pdf",
            }
            mime_type = mime_map.get(ext, "application/octet-stream")

        try:
            with open(file_path, "rb") as f:
                data = f.read()
            base64_data = base64.b64encode(data).decode("utf-8")
            return f"[Binary file: {mime_type}]\n{base64_data}"
        except Exception as e:
            raise ToolExecutionError(
                message=f"读取二进制文件失败: {file_path}",
                tool_name=self.name,
                error_details=e,
            ) from e

    def do_run(
        self,
        file_path: str,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        **kwargs,
    ) -> str:
        """执行读取文件操作

        Args:
            file_path: 文件路径
            offset: 0 基起始行（仅文本）
            limit: 最多读取的行数（仅文本）

        Returns:
            str: 文件内容
        """
        safe_path = _safe_path(file_path)
        if not safe_path.exists():
            raise ToolExecutionError(
                message=f"文件不存在: {file_path}",
                tool_name=self.name,
            )
        if not safe_path.is_file():
            raise ToolExecutionError(
                message=f"路径不是文件: {file_path}",
                tool_name=self.name,
            )

        # 检查是否为二进制文件（图片、音频、PDF）
        ext = safe_path.suffix.lower()
        binary_extensions = {
            ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp",
            ".mp3", ".wav", ".aiff", ".aac", ".ogg", ".flac",
            ".pdf",
        }
        if ext in binary_extensions:
            return self._read_binary_file(safe_path)

        # 读取文本文件
        try:
            with open(safe_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            total_lines = len(lines)

            # 处理 offset 和 limit（0-based）
            if offset is not None:
                if limit is None:
                    raise ToolExecutionError(
                        message="设置 offset 时必须同时提供 limit",
                        tool_name=self.name,
                    )
                start = max(0, min(offset, total_lines))
                end = min(start + limit, total_lines)
            else:
                start = 0
                end = total_lines

            selected_lines = lines[start:end]
            content = "".join(selected_lines)

            # 如果内容被截断，添加提示
            if offset is not None or end < total_lines:
                warning = f"[WARNING: Showing lines {start + 1}-{end} / total lines {total_lines}]\n"
                warning += f"To read more, use offset={end} and limit=<desired_lines>\n\n"
                content = warning + content

            return content

        except ToolExecutionError:
            raise
        except Exception as e:
            raise ToolExecutionError(
                message=f"读取文件失败: {file_path}",
                tool_name=self.name,
                error_details=e,
            ) from e


class SearchFileContentTool(BaseTool):
    """在文件内容中搜索正则表达式模式"""

    @property
    def name(self) -> str:
        return "search_file_content"

    @property
    def type(self) -> str:
        return ToolType.FUNCTION

    @property
    def permission(self) -> str:
        return "read"

    @property
    def description(self) -> str:
        return "在文件内容中搜索正则表达式模式，并可通过 glob 过滤。"

    @property
    def display_name(self) -> str:
        return "Search"

    def display(self, pattern: str = "", **kwargs) -> str:
        """工具显示名称"""
        if pattern:
            return f"{self.display_name} '{pattern}'"
        return self.display_name

    @property
    def parameters(self) -> ToolFunctionParameters:
        return ToolFunctionParameters(
            properties={
                "pattern": {
                    "type": "string",
                    "description": "ECMAScript 正则表达式模式",
                },
                "dir_path": {
                    "type": "string",
                    "description": "要搜索的目录，相对路径解析后必须仍在 workspace。省略则遍历所有 workspace 目录。",
                },
                "include": {
                    "type": "string",
                    "description": "限制搜索文件的 glob（如 \"src/**/*.{ts,tsx}\"）",
                },
            },
            required=["pattern"],
        )

    def _try_git_grep(self, pattern: str, dir_path: Path) -> Optional[str]:
        """尝试使用 git grep 搜索

        Args:
            pattern: 正则表达式模式
            dir_path: 搜索目录

        Returns:
            Optional[str]: 搜索结果，如果失败返回 None
        """
        import subprocess

        try:
            # 检查是否为 Git 仓库
            git_dir = dir_path / ".git"
            if not (git_dir.exists() and (git_dir.is_dir() or git_dir.is_file())):
                return None

            # 尝试执行 git grep
            result = subprocess.run(
                ["git", "grep", "-n", "-E", pattern],
                cwd=str(dir_path),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            pass
        return None

    def _try_ripgrep(self, pattern: str, dir_path: Path, include: Optional[str]) -> Optional[str]:
        """尝试使用 ripgrep 搜索

        Args:
            pattern: 正则表达式模式
            dir_path: 搜索目录
            include: glob 模式

        Returns:
            Optional[str]: 搜索结果，如果失败返回 None
        """
        import subprocess

        try:
            cmd = ["rg", "-n", "--type-add", "text:*", "-t", "text", pattern, str(dir_path)]
            if include:
                cmd.extend(["-g", include])
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            pass
        return None

    def _search_with_python(
        self, pattern: str, dir_path: Path, include: Optional[str]
    ) -> str:
        """使用 Python 逐行扫描搜索

        Args:
            pattern: 正则表达式模式
            dir_path: 搜索目录
            include: glob 模式

        Returns:
            str: 搜索结果
        """
        try:
            regex = re.compile(pattern)
        except re.error as e:
            raise ToolExecutionError(
                message=f"无效的正则表达式: {pattern}",
                tool_name=self.name,
                error_details=e,
            ) from e

        results = []
        workspace_dir = resolve_workspace_dir()

        # 收集要搜索的文件
        files_to_search = []
        if dir_path.is_file():
            files_to_search.append(dir_path)
        else:
            for file_path in dir_path.rglob("*"):
                if not file_path.is_file():
                    continue
                # 检查是否在 workspace 内
                try:
                    file_path.relative_to(workspace_dir)
                except ValueError:
                    continue
                # 检查 include 模式
                if include:
                    if not fnmatch.fnmatch(str(file_path.relative_to(workspace_dir)), include):
                        continue
                files_to_search.append(file_path)

        # 搜索每个文件
        for file_path in files_to_search:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, start=1):
                        if regex.search(line):
                            # 格式化输出：File: path\nL<lineNumber>: trimmed line
                            rel_path = file_path.relative_to(workspace_dir)
                            trimmed_line = line.rstrip()
                            results.append(f"File: {rel_path}\nL{line_num}: {trimmed_line}")
            except Exception:
                continue

        return "\n\n".join(results)

    def do_run(
        self,
        pattern: str,
        dir_path: Optional[str] = None,
        include: Optional[str] = None,
        **kwargs,
    ) -> str:
        """执行搜索操作

        Args:
            pattern: ECMAScript 正则表达式
            dir_path: 要搜索的目录
            include: 限制搜索文件的 glob

        Returns:
            str: 搜索结果
        """
        workspace_dir = resolve_workspace_dir()

        # 确定搜索目录
        if dir_path:
            search_dir = _safe_path(dir_path)
            if not search_dir.exists():
                raise ToolExecutionError(
                    message=f"目录不存在: {dir_path}",
                    tool_name=self.name,
                )
            if not search_dir.is_dir():
                raise ToolExecutionError(
                    message=f"路径不是目录: {dir_path}",
                    tool_name=self.name,
                )
            # 验证在 workspace 内
            try:
                search_dir.relative_to(workspace_dir)
            except ValueError:
                raise ToolExecutionError(
                    message=f"目录不在 workspace 内: {dir_path}",
                    tool_name=self.name,
                )
        else:
            search_dir = workspace_dir

        # 依次尝试三种策略
        # 1. git grep
        result = self._try_git_grep(pattern, search_dir)
        if result:
            match_count = len([line for line in result.split("\n") if line.strip()])
            return f"Found {match_count} matches\n\n{result}"

        # 2. ripgrep
        result = self._try_ripgrep(pattern, search_dir, include)
        if result:
            match_count = len([line for line in result.split("\n") if line.strip()])
            return f"Found {match_count} matches\n\n{result}"

        # 3. Python 逐行扫描
        result = self._search_with_python(pattern, search_dir, include)
        if result:
            match_count = len([block for block in result.split("\n\n") if block.strip()])
            summary = f"Found {match_count} matches"
            if dir_path:
                summary += f" in {dir_path}"
            if include:
                summary += f" (filtered by: {include})"
            return f"{summary}\n\n{result}"

        return "No matches found"


class ReadManyFilesTool(BaseTool):
    """批量读取文件内容"""

    @property
    def name(self) -> str:
        return "read_many_files"

    @property
    def type(self) -> str:
        return ToolType.FUNCTION

    @property
    def permission(self) -> str:
        return "read"

    @property
    def description(self) -> str:
        return "从配置的目标目录中读取由 glob 模式指定的多个文件的内容。"

    @property
    def display_name(self) -> str:
        return "Read"

    def display(self, include: List[str] = None, **kwargs) -> str:
        """工具显示名称"""
        if include:
            parts = [f"{self.display_name} {file_path}" for file_path in include]
            return ", ".join(parts)
        return self.display_name

    @property
    def parameters(self) -> ToolFunctionParameters:
        return ToolFunctionParameters(
            properties={
                "include": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要匹配的 glob / 相对路径数组（示例：[\"src/**/*.ts\", \"README.md\"]）",
                },
                "exclude": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "附加的忽略模式，会与默认忽略（node_modules、日志等）合并，除非 use_default_excludes=false",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "控制是否递归。默认 true（配合 **）",
                    "default": True,
                },
                "use_default_excludes": {
                    "type": "boolean",
                    "description": "默认为 true。设为 false 时仅使用显式 exclude",
                    "default": True,
                },
                "file_filtering_options": {
                    "type": "object",
                    "properties": {
                        "respect_git_ignore": {
                            "type": "boolean",
                            "description": "是否尊重 .gitignore。默认 true",
                            "default": True,
                        },
                        "respect_eflycode_ignore": {
                            "type": "boolean",
                            "description": "是否应用 .eflycodeignore。默认 true",
                            "default": True,
                        },
                    },
                },
            },
            required=["include"],
        )

    def _read_binary_file(self, file_path: Path) -> str:
        """读取二进制文件并返回 base64 编码"""
        import base64
        import mimetypes

        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            ext = file_path.suffix.lower()
            mime_map = {
                ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
                ".bmp": "image/bmp", ".mp3": "audio/mpeg", ".wav": "audio/wav",
                ".aiff": "audio/aiff", ".aac": "audio/aac", ".ogg": "audio/ogg",
                ".flac": "audio/flac", ".pdf": "application/pdf",
            }
            mime_type = mime_map.get(ext, "application/octet-stream")

        try:
            with open(file_path, "rb") as f:
                data = f.read()
            base64_data = base64.b64encode(data).decode("utf-8")
            return f"[Binary file: {mime_type}]\n{base64_data}"
        except Exception:
            return "[Binary file: read error]"

    def do_run(
        self,
        include: List[str],
        exclude: Optional[List[str]] = None,
        recursive: bool = True,
        use_default_excludes: bool = True,
        file_filtering_options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """执行批量读取文件操作"""
        import glob as glob_module

        workspace_dir = resolve_workspace_dir()
        
        if file_filtering_options is None:
            file_filtering_options = {}
        respect_git_ignore = file_filtering_options.get("respect_git_ignore", True)
        respect_eflycode_ignore = file_filtering_options.get("respect_eflycode_ignore", True)

        ignore_patterns = load_all_ignore_patterns(
            respect_git_ignore=respect_git_ignore,
            respect_eflycode_ignore=respect_eflycode_ignore,
            workspace_dir=workspace_dir,
        )

        default_excludes = ["node_modules", "*.log", ".git", "__pycache__", "*.pyc"]
        if use_default_excludes:
            if exclude is None:
                exclude = []
            exclude.extend(default_excludes)

        matched_files = set()
        for pattern in include:
            if recursive and "**" not in pattern:
                pattern = pattern.replace("*", "**/*", 1) if "*" in pattern else f"{pattern}/**/*"
            
            for file_path in glob_module.glob(str(workspace_dir / pattern), recursive=recursive):
                file_path_obj = Path(file_path)
                if not file_path_obj.is_file():
                    continue
                try:
                    file_path_obj.relative_to(workspace_dir)
                except ValueError:
                    continue
                if exclude:
                    if any(fnmatch.fnmatch(str(file_path_obj.relative_to(workspace_dir)), excl_pattern) for excl_pattern in exclude):
                        continue
                if ignore_patterns:
                    if should_ignore_path(file_path_obj, ignore_patterns, workspace_dir):
                        continue
                matched_files.add(file_path_obj)

        if not matched_files:
            return "No files matched the include patterns."

        results = []
        skipped_reasons = {}
        for file_path in sorted(matched_files):
            try:
                if _is_text_file(str(file_path)):
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    results.append(f"--- {file_path} ---\n{content}")
                else:
                    ext = file_path.suffix.lower()
                    binary_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp",
                                       ".mp3", ".wav", ".aiff", ".aac", ".ogg", ".flac", ".pdf"}
                    if ext in binary_extensions:
                        file_name = file_path.name
                        if any(file_name in pattern or ext in pattern for pattern in include):
                            binary_content = self._read_binary_file(file_path)
                            results.append(f"--- {file_path} ---\n{binary_content}")
                        else:
                            skipped_reasons["Binary file not explicitly requested"] = skipped_reasons.get("Binary file not explicitly requested", 0) + 1
                    else:
                        skipped_reasons["Unsupported binary file"] = skipped_reasons.get("Unsupported binary file", 0) + 1
            except Exception as e:
                skipped_reasons[f"Read error: {str(e)[:50]}"] = skipped_reasons.get(f"Read error: {str(e)[:50]}", 0) + 1

        content_text = "\n\n".join(results)
        if content_text:
            content_text += "\n--- End of content ---"

        display_parts = [f"Read {len(results)} file(s)"]
        if matched_files:
            file_list = sorted(matched_files)[:10]
            display_parts.append(f"Files: {', '.join(str(f.relative_to(workspace_dir)) for f in file_list)}")
        if skipped_reasons:
            reason_list = sorted(skipped_reasons.items(), key=lambda x: x[1], reverse=True)[:5]
            display_parts.append(f"Skipped reasons: {', '.join(f'{k}({v})' for k, v in reason_list)}")

        return f"{content_text}\n\n{' | '.join(display_parts)}"


class GlobSearchTool(BaseTool):
    """查找匹配 glob 模式的文件"""

    @property
    def name(self) -> str:
        return "glob_search"

    @property
    def type(self) -> str:
        return ToolType.FUNCTION

    @property
    def permission(self) -> str:
        return "read"

    @property
    def description(self) -> str:
        return "高效地查找匹配特定 glob 模式的文件，会返回按\"最近修改优先\"排序的绝对路径列表。"

    @property
    def display_name(self) -> str:
        return "Glob"

    def display(self, pattern: str = "", **kwargs) -> str:
        """工具显示名称"""
        if pattern:
            return f"{self.display_name} '{pattern}'"
        return self.display_name

    @property
    def parameters(self) -> ToolFunctionParameters:
        return ToolFunctionParameters(
            properties={
                "pattern": {
                    "type": "string",
                    "description": "glob 表达式，例如 \"**/*.py\"、\"docs/*.md\"",
                },
                "dir_path": {
                    "type": "string",
                    "description": "搜索的起始目录（默认整个 workspace）",
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "是否区分大小写，默认 false",
                    "default": False,
                },
                "respect_git_ignore": {
                    "type": "boolean",
                    "description": "是否考虑 .gitignore。默认 true",
                    "default": True,
                },
                "respect_eflycode_ignore": {
                    "type": "boolean",
                    "description": "是否考虑 .eflycodeignore。默认 true",
                    "default": True,
                },
            },
            required=["pattern"],
        )

    def do_run(
        self,
        pattern: str,
        dir_path: Optional[str] = None,
        case_sensitive: bool = False,
        respect_git_ignore: bool = True,
        respect_eflycode_ignore: bool = True,
        **kwargs,
    ) -> str:
        """执行 glob 查找操作"""
        import glob as glob_module
        import time

        workspace_dir = resolve_workspace_dir()

        if dir_path:
            search_dir = _safe_path(dir_path)
            if not search_dir.exists():
                raise ToolExecutionError(message=f"目录不存在: {dir_path}", tool_name=self.name)
            if not search_dir.is_dir():
                raise ToolExecutionError(message=f"路径不是目录: {dir_path}", tool_name=self.name)
            try:
                search_dir.relative_to(workspace_dir)
            except ValueError:
                raise ToolExecutionError(message=f"目录不在 workspace 内: {dir_path}", tool_name=self.name)
        else:
            search_dir = workspace_dir

        ignore_patterns = load_all_ignore_patterns(
            respect_git_ignore=respect_git_ignore,
            respect_eflycode_ignore=respect_eflycode_ignore,
            workspace_dir=workspace_dir,
        )

        search_pattern = str(search_dir / pattern)
        matched_files = []
        for file_path_str in glob_module.glob(search_pattern, recursive=True):
            file_path = Path(file_path_str)
            if not file_path.is_file():
                continue
            if ignore_patterns:
                if should_ignore_path(file_path, ignore_patterns, workspace_dir):
                    continue
            matched_files.append(file_path)

        current_time = time.time()
        ten_minutes_ago = current_time - 600

        def get_sort_key(file_path: Path) -> tuple:
            try:
                mtime = file_path.stat().st_mtime
                is_recent = mtime >= ten_minutes_ago
                return (not is_recent, -mtime, str(file_path))
            except Exception:
                return (True, 0, str(file_path))

        matched_files.sort(key=get_sort_key)

        if not matched_files:
            return f"Found 0 file(s) matching pattern '{pattern}' in {search_dir}"

        file_list = "\n".join(str(f) for f in matched_files)
        return f"Found {len(matched_files)} file(s) matching pattern '{pattern}' in {search_dir}\n\n{file_list}"


class WriteFileTool(BaseTool):
    """写入文件内容"""

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def type(self) -> str:
        return ToolType.FUNCTION

    @property
    def permission(self) -> str:
        return "edit"

    @property
    def description(self) -> str:
        return "将内容写入本地文件系统中的指定文件。用户能够修改 content。如果被修改，将在响应中说明。"

    @property
    def display_name(self) -> str:
        return "Write"

    def display(self, file_path: str = "", **kwargs) -> str:
        """工具显示名称"""
        if file_path:
            return f"{self.display_name} {file_path}"
        return self.display_name

    @property
    def parameters(self) -> ToolFunctionParameters:
        return ToolFunctionParameters(
            properties={
                "file_path": {
                    "type": "string",
                    "description": "要覆盖写入的文件路径。必须位于 workspace 中，且不能指向目录。",
                },
                "content": {
                    "type": "string",
                    "description": "写入文件的完整内容。",
                },
            },
            required=["file_path", "content"],
        )

    def do_run(self, file_path: str, content: str, **kwargs) -> str:
        """执行写入文件操作

        Args:
            file_path: 文件路径
            content: 文件内容

        Returns:
            str: 操作结果
        """
        safe_path = _safe_path(file_path)
        
        # 验证不能是目录
        if safe_path.exists() and safe_path.is_dir():
            raise ToolExecutionError(
                message=f"路径是目录，不能写入: {file_path}",
                tool_name=self.name,
            )

        # 检查文件是否存在
        file_exists = safe_path.exists() and safe_path.is_file()

        # 捕获 checkpoint（最佳努力，不影响主流程）
        capture_tool_checkpoint(
            tool_name=self.name,
            tool_args={
                "file_path": str(safe_path),
                "content_preview": content[:2000],  # 避免写入过大内容
            },
        )

        try:
            # 递归创建父目录
            safe_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入文件
            with open(safe_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            # 返回相对路径和操作类型
            workspace_dir = resolve_workspace_dir()
            try:
                rel_path = safe_path.relative_to(workspace_dir)
            except ValueError:
                rel_path = safe_path
            
            action = "Overwrote" if file_exists else "Created"
            return f"{action} {rel_path}"
        except Exception as e:
            raise ToolExecutionError(
                message=f"写入文件失败: {file_path}",
                tool_name=self.name,
                error_details=e,
            ) from e


class ReplaceTool(BaseTool):
    """替换文件中的文本"""

    @property
    def name(self) -> str:
        return "replace"

    @property
    def type(self) -> str:
        return ToolType.FUNCTION

    @property
    def permission(self) -> str:
        return "edit"

    @property
    def description(self) -> str:
        return "替换文件中的文本。默认情况下，替换单个匹配项，但当指定 expected_replacements 时，可以替换多个匹配项。此工具需要提供围绕更改的大量上下文以确保精确定位。在尝试文本替换之前，始终使用 read_file 工具检查文件的当前内容。"

    @property
    def display_name(self) -> str:
        return "Edit"

    def display(self, file_path: str = "", **kwargs) -> str:
        """工具显示名称"""
        if file_path:
            return f"{self.display_name} {file_path}"
        return self.display_name

    @property
    def parameters(self) -> ToolFunctionParameters:
        return ToolFunctionParameters(
            properties={
                "file_path": {
                    "type": "string",
                    "description": "要修改的文件路径，调用前会自动校正到绝对路径并验证 workspace。",
                },
                "instruction": {
                    "type": "string",
                    "description": "高质量的语义说明（原因、位置、目标结果），供人类/LLM 理解。",
                },
                "old_string": {
                    "type": "string",
                    "description": "需要替换的确切文本，建议包含 >=3 行前后文，不能转义。",
                },
                "new_string": {
                    "type": "string",
                    "description": "用于替换的完整文本，必须与 old_string 不同。",
                },
                "expected_replacements": {
                    "type": "integer",
                    "description": "预期替换的次数（最小 1），默认 1。",
                    "default": 1,
                },
            },
            required=["file_path", "instruction", "old_string", "new_string"],
        )

    def _flexible_match(self, content: str, old_string: str) -> Optional[str]:
        """尝试灵活匹配（按行去空白对齐）

        Args:
            content: 文件内容
            old_string: 要匹配的字符串

        Returns:
            Optional[str]: 如果找到匹配的文本，返回匹配的文本；否则返回 None
        """
        # 简化实现：尝试去除行尾空白后匹配
        content_lines = content.split("\n")
        old_lines = old_string.split("\n")
        
        if len(old_lines) > len(content_lines):
            return None
        
        # 尝试在内容中查找匹配的行序列
        for i in range(len(content_lines) - len(old_lines) + 1):
            candidate = "\n".join(content_lines[i:i + len(old_lines)])
            if candidate.rstrip() == old_string.rstrip():
                return candidate
        
        return None

    def do_run(
        self,
        file_path: str,
        instruction: str,
        old_string: str,
        new_string: str,
        expected_replacements: int = 1,
        **kwargs,
    ) -> str:
        """执行替换内容操作

        Args:
            file_path: 文件路径
            instruction: 语义说明
            old_string: 要替换的确切文本
            new_string: 新内容
            expected_replacements: 预期替换次数

        Returns:
            str: 操作结果
        """
        safe_path = _safe_path(file_path)
        
        # 处理 old_string 为空的情况
        if not old_string:
            if not safe_path.exists():
                # 等价于创建新文件
                try:
                    safe_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(safe_path, "w", encoding="utf-8") as f:
                        f.write(new_string)
                    return f"Successfully created file: {file_path}"
                except Exception as e:
                    raise ToolExecutionError(
                        message=f"创建文件失败: {file_path}",
                        tool_name=self.name,
                        error_details=e,
                    ) from e
            else:
                raise ToolExecutionError(
                    message="old_string 为空但文件已存在",
                    tool_name=self.name,
                )

        if not safe_path.exists():
            raise ToolExecutionError(
                message=f"文件不存在: {file_path}",
                tool_name=self.name,
            )
        if not safe_path.is_file():
            raise ToolExecutionError(
                message=f"路径不是文件: {file_path}",
                tool_name=self.name,
            )

        if old_string == new_string:
            raise ToolExecutionError(
                message="old_string 和 new_string 必须不同",
                tool_name=self.name,
            )

        # 捕获 checkpoint（最佳努力，不影响主流程）
        capture_tool_checkpoint(
            tool_name=self.name,
            tool_args={
                "file_path": str(safe_path),
                "instruction": instruction,
                "old_string_preview": old_string[:2000],
                "new_string_preview": new_string[:2000],
                "expected_replacements": expected_replacements,
            },
        )

        try:
            # 读取文件，转换行结束符为 \n
            with open(safe_path, "r", encoding="utf-8", newline="") as f:
                content = f.read()
            # 统一行结束符
            content = content.replace("\r\n", "\n").replace("\r", "\n")

            # 多阶段匹配
            # 1. 精确匹配
            count = content.count(old_string)
            if count == expected_replacements:
                # 精确匹配，直接替换
                new_content = content.replace(old_string, new_string, expected_replacements)
            elif count > 0:
                # 匹配次数不符合预期
                raise ToolExecutionError(
                    message=f"old_string 在文件中出现 {count} 次，但 expected_replacements={expected_replacements}",
                    tool_name=self.name,
                )
            else:
                # 2. 尝试灵活匹配
                matched_text = self._flexible_match(content, old_string)
                if matched_text:
                    new_content = content.replace(matched_text, new_string, 1)
                    if expected_replacements > 1:
                        raise ToolExecutionError(
                            message="灵活匹配只支持单次替换",
                            tool_name=self.name,
                        )
                else:
                    raise ToolExecutionError(
                        message=f"未找到要替换的内容: {file_path}\n提示: 请确保 old_string 包含足够的上下文（至少 3 行前后文）",
                        tool_name=self.name,
                    )

            # 写入文件
            with open(safe_path, "w", encoding="utf-8", newline="") as f:
                f.write(new_content)

            return f"Successfully modified file: {file_path} ({expected_replacements} replacement(s))"
        except ToolExecutionError:
            raise
        except Exception as e:
            raise ToolExecutionError(
                message=f"替换内容失败: {file_path}",
                tool_name=self.name,
                error_details=e,
            ) from e


class DeleteFileTool(BaseTool):
    """按照文件名删除文件"""

    @property
    def name(self) -> str:
        return "delete_file"

    @property
    def type(self) -> str:
        return ToolType.FUNCTION

    @property
    def permission(self) -> str:
        return "delete"

    @property
    def description(self) -> str:
        return "按照文件名删除文件。"

    @property
    def display_name(self) -> str:
        return "Delete"

    def display(self, file_path: str = "", **kwargs) -> str:
        """工具显示名称"""
        if file_path:
            return f"{self.display_name} {file_path}"
        return self.display_name

    @property
    def parameters(self) -> ToolFunctionParameters:
        return ToolFunctionParameters(
            properties={
                "file_path": {
                    "type": "string",
                    "description": "文件路径",
                },
            },
            required=["file_path"],
        )

    def do_run(self, file_path: str, **kwargs) -> str:
        """执行删除文件操作

        Args:
            file_path: 文件路径

        Returns:
            str: 操作结果

        Raises:
            FileNotFoundError: 如果文件不存在
        """
        safe_path = _safe_path(file_path)
        if not safe_path.exists():
            raise ToolExecutionError(
                message=f"文件不存在: {file_path}",
                tool_name=self.name,
            )
        if not safe_path.is_file():
            raise ToolExecutionError(
                message=f"路径不是文件: {file_path}",
                tool_name=self.name,
            )

        try:
            safe_path.unlink()
            return f"文件已删除: {file_path}"
        except Exception as e:
            raise ToolExecutionError(
                message=f"删除文件失败: {file_path}",
                tool_name=self.name,
                error_details=e,
            ) from e


class MoveFileTool(BaseTool):
    """移动文件（重命名）"""

    @property
    def name(self) -> str:
        return "move_file"

    @property
    def type(self) -> str:
        return ToolType.FUNCTION

    @property
    def permission(self) -> str:
        return "edit"

    @property
    def description(self) -> str:
        return "移动文件（重命名）。如果目标文件已存在，会抛出错误。"

    @property
    def display_name(self) -> str:
        return "Move"

    def display(self, source_path: str = "", target_path: str = "", **kwargs) -> str:
        """工具显示名称"""
        if source_path and target_path:
            return f"{self.display_name} {source_path} -> {target_path}"
        elif source_path:
            return f"{self.display_name} {source_path}"
        return self.display_name

    @property
    def parameters(self) -> ToolFunctionParameters:
        return ToolFunctionParameters(
            properties={
                "source_path": {
                    "type": "string",
                    "description": "源文件路径",
                },
                "target_path": {
                    "type": "string",
                    "description": "目标文件路径",
                },
            },
            required=["source_path", "target_path"],
        )

    def do_run(self, source_path: str, target_path: str, **kwargs) -> str:
        """执行移动文件操作

        Args:
            source_path: 源文件路径
            target_path: 目标文件路径

        Returns:
            str: 操作结果

        Raises:
            FileNotFoundError: 如果源文件不存在
            FileExistsError: 如果目标文件已存在
        """
        safe_source = _safe_path(source_path)
        if not safe_source.exists():
            raise FileNotFoundError(f"源文件不存在: {source_path}")
        if not safe_source.is_file():
            raise ToolExecutionError(
                message=f"源路径不是文件: {source_path}",
                tool_name=self.name,
            )

        safe_target = _safe_path(target_path)
        if safe_target.exists():
            raise FileExistsError(f"目标文件已存在: {target_path}")

        try:
            safe_target.parent.mkdir(parents=True, exist_ok=True)
            safe_source.rename(safe_target)
            return f"文件已移动: {source_path} -> {target_path}"
        except Exception as e:
            raise ToolExecutionError(
                message=f"移动文件失败: {source_path} -> {target_path}",
                tool_name=self.name,
                error_details=e,
            ) from e


FILE_SYSTEM_TOOL_GROUP = ToolGroup(
    name="file_system_tools",
    description="文件系统操作工具组，包含文件的读取、创建、编辑、删除等操作",
    tools=[
        ListDirectoryTool(),
        ReadFileTool(),
        ReadManyFilesTool(),
        GlobSearchTool(),
        SearchFileContentTool(),
        WriteFileTool(),
        ReplaceTool(),
        DeleteFileTool(),
        MoveFileTool(),
    ],
)

