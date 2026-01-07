import fnmatch
import re
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional, Union

from eflycode.core.config.ignore import load_ignore_patterns, should_ignore_path
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
                    tool_name="file_tool",
                )
        return resolved
    except Exception as e:
        raise ToolExecutionError(
            message=f"无效的路径: {path}",
            tool_name="file_tool",
            error_details=e,
        ) from e


class ListFilesTool(BaseTool):
    """列出目录下的文件和子目录"""

    @property
    def name(self) -> str:
        return "list_files"

    @property
    def type(self) -> str:
        return ToolType.FUNCTION

    @property
    def permission(self) -> str:
        return "read"

    @property
    def description(self) -> str:
        return "列出目录下的文件和子目录，以树状文本返回。默认递归深度为1，可通过 max_depth 参数调整。文本文件会显示行数，文件夹会显示包含的项目数量。"

    def display(self, directory: str = "", **kwargs) -> str:
        """工具显示名称"""
        if directory:
            return f"列出目录 {directory}"
        return "列出目录"

    @property
    def parameters(self) -> ToolFunctionParameters:
        return ToolFunctionParameters(
            properties={
                "directory": {
                    "type": "string",
                    "description": "要列出的目录路径",
                },
                "max_depth": {
                    "type": "integer",
                    "description": "最大递归深度，默认为1，即只列出当前目录和直接子目录",
                    "default": 1,
                },
            },
            required=["directory"],
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

    def do_run(self, directory: str, max_depth: int = 1, **kwargs) -> str:
        """执行列出文件操作

        Args:
            directory: 目录路径
            max_depth: 最大递归深度，默认为1

        Returns:
            str: 树状文件列表
        """
        safe_path = _safe_path(directory)
        if not safe_path.exists():
            raise ToolExecutionError(
                message=f"目录不存在: {directory}",
                tool_name=self.name,
            )
        if not safe_path.is_dir():
            raise ToolExecutionError(
                message=f"路径不是目录: {directory}",
                tool_name=self.name,
            )

        # 确定基础目录
        # 尝试从配置中获取工作区目录，否则使用 safe_path 的父目录
        try:
            from eflycode.core.config import load_config
            config = load_config()
            base_dir = config.workspace_dir
        except Exception:
            # 如果获取配置失败，使用 safe_path 的父目录
            base_dir = safe_path.parent if safe_path.parent != safe_path else safe_path

        # 加载忽略模式
        ignore_patterns = load_ignore_patterns(workspace_dir=base_dir)

        tree = self._build_tree(
            safe_path,
            max_depth=max_depth,
            ignore_patterns=ignore_patterns,
            base_dir=base_dir,
        )
        return f"{directory}/\n{tree}"


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
        return "读取文件内容，支持多个文件，每个文件可独立指定行号范围或行数。行号基于原文件。"

    def display(self, files: List[Union[str, Dict[str, Any]]] = None, **kwargs) -> str:
        """工具显示名称"""
        if not files:
            return "读取文件"
        
        result = []
        for file_spec in files:
            if isinstance(file_spec, str):
                result.append(f"读取 {file_spec}")
            elif isinstance(file_spec, dict):
                path = file_spec.get("path", "")
                start_line = file_spec.get("start_line")
                end_line = file_spec.get("end_line")
                line_count = file_spec.get("line_count")
                
                line_info = ""
                if start_line is not None:
                    if line_count is not None:
                        line_info = f" ({start_line}行-{start_line + line_count - 1}行)"
                    elif end_line is not None:
                        line_info = f" ({start_line}行-{end_line}行)"
                    else:
                        line_info = f" (从{start_line}行开始)"
                
                result.append(f"读取 {path}{line_info}")
        
        return " | ".join(result) if len(result) == 1 else f"读取 {len(result)} 个文件"

    @property
    def parameters(self) -> ToolFunctionParameters:
        return ToolFunctionParameters(
            properties={
                "files": {
                    "type": "array",
                    "description": "文件路径列表或字典列表。如果是字典，包含 path（文件路径）、start_line（起始行号，可选）、end_line（结束行号，可选）、line_count（读取行数，可选）",
                    "items": {
                        "oneOf": [
                            {"type": "string"},
                            {
                                "type": "object",
                                "properties": {
                                    "path": {"type": "string"},
                                    "start_line": {"type": "integer"},
                                    "end_line": {"type": "integer"},
                                    "line_count": {"type": "integer"},
                                },
                                "required": ["path"],
                            },
                        ],
                    },
                },
                "show_line_numbers": {
                    "type": "boolean",
                    "description": "是否显示行号",
                },
            },
            required=["files"],
        )

    def _read_file_content(
        self, file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None, line_count: Optional[int] = None, show_line_numbers: bool = False
    ) -> str:
        """读取文件内容

        Args:
            file_path: 文件路径
            start_line: 起始行号（1-based）
            end_line: 结束行号（1-based）
            line_count: 读取行数
            show_line_numbers: 是否显示行号

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

        try:
            with open(safe_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            total_lines = len(lines)

            if start_line is not None:
                start = max(1, min(start_line, total_lines))
                if line_count is not None:
                    end = min(start + line_count - 1, total_lines)
                elif end_line is not None:
                    end = min(end_line, total_lines)
                else:
                    end = total_lines
            else:
                start = 1
                end = total_lines

            selected_lines = lines[start - 1 : end]

            if show_line_numbers:
                result = []
                for i, line in enumerate(selected_lines, start=start):
                    result.append(f"{i:4d} | {line.rstrip()}")
                return "\n".join(result)
            else:
                return "".join(selected_lines).rstrip()

        except Exception as e:
            raise ToolExecutionError(
                message=f"读取文件失败: {file_path}",
                tool_name=self.name,
                error_details=e,
            ) from e

    def do_run(self, files: List[Union[str, Dict[str, Any]]], show_line_numbers: bool = False, **kwargs) -> str:
        """执行读取文件操作

        Args:
            files: 文件路径列表或字典列表
            show_line_numbers: 是否显示行号

        Returns:
            str: 文件内容
        """
        results = []
        for file_spec in files:
            if isinstance(file_spec, str):
                file_path = file_spec
                start_line = None
                end_line = None
                line_count = None
            elif isinstance(file_spec, dict):
                file_path = file_spec.get("path")
                start_line = file_spec.get("start_line")
                end_line = file_spec.get("end_line")
                line_count = file_spec.get("line_count")
            else:
                raise ToolExecutionError(
                    message=f"无效的文件规格: {file_spec}",
                    tool_name=self.name,
                )

            content = self._read_file_content(file_path, start_line, end_line, line_count, show_line_numbers)
            results.append(f"=== {file_path} ===\n{content}")

        return "\n\n".join(results)


class GrepSearchTool(BaseTool):
    """在文件或目录中搜索匹配的内容"""

    @property
    def name(self) -> str:
        return "grep_search"

    @property
    def type(self) -> str:
        return ToolType.FUNCTION

    @property
    def permission(self) -> str:
        return "read"

    @property
    def description(self) -> str:
        return "在文件或目录中搜索匹配的内容，支持正则表达式和多种搜索选项。"

    def display(self, pattern: str = "", path: str = "", **kwargs) -> str:
        """工具显示名称"""
        if pattern and path:
            return f"搜索 {path} 中的 '{pattern}'"
        elif pattern:
            return f"搜索 '{pattern}'"
        elif path:
            return f"搜索 {path}"
        return "搜索文件"

    @property
    def parameters(self) -> ToolFunctionParameters:
        return ToolFunctionParameters(
            properties={
                "pattern": {
                    "type": "string",
                    "description": "要搜索的匹配模式（正则或普通字符串）",
                },
                "path": {
                    "type": "string",
                    "description": "要搜索的文件或目录路径",
                },
                "ignore_case": {
                    "type": "boolean",
                    "description": "是否忽略大小写 (-i)",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "是否递归搜索目录 (-r)",
                },
                "line_number": {
                    "type": "boolean",
                    "description": "是否显示行号 (-n)",
                },
                "include": {
                    "type": "string",
                    "description": "只搜索匹配的文件模式，如 *.py",
                },
                "exclude": {
                    "type": "string",
                    "description": "排除的文件模式，如 *.log",
                },
                "max_count": {
                    "type": "integer",
                    "description": "最多输出的匹配行数 (-m)",
                },
            },
            required=["pattern", "path"],
        )

    def _should_include_file(self, file_path: Path, include: Optional[str], exclude: Optional[str]) -> bool:
        """判断文件是否应该被包含在搜索中

        Args:
            file_path: 文件路径
            include: 包含模式
            exclude: 排除模式

        Returns:
            bool: 是否应该包含
        """
        file_str = str(file_path)
        if include and not fnmatch.fnmatch(file_str, include):
            return False
        if exclude and fnmatch.fnmatch(file_str, exclude):
            return False
        return True

    def do_run(
        self,
        pattern: Annotated[str, "要搜索的匹配模式（正则或普通字符串）"],
        path: Annotated[str, "要搜索的文件或目录路径"],
        ignore_case: Annotated[bool, "是否忽略大小写 (-i)"] = False,
        recursive: Annotated[bool, "是否递归搜索目录 (-r)"] = False,
        line_number: Annotated[bool, "是否显示行号 (-n)"] = True,
        include: Annotated[Optional[str], "只搜索匹配的文件模式，如 *.py"] = None,
        exclude: Annotated[Optional[str], "排除的文件模式，如 *.log"] = None,
        max_count: Annotated[Optional[int], "最多输出的匹配行数 (-m)"] = None,
        **kwargs,
    ) -> str:
        """执行搜索操作

        Args:
            pattern: 搜索模式
            path: 文件或目录路径
            ignore_case: 是否忽略大小写
            recursive: 是否递归搜索
            line_number: 是否显示行号
            include: 包含的文件模式
            exclude: 排除的文件模式
            max_count: 最大匹配行数

        Returns:
            str: 搜索结果
        """
        safe_path = _safe_path(path)
        if not safe_path.exists():
            raise ToolExecutionError(
                message=f"路径不存在: {path}",
                tool_name=self.name,
            )

        flags = re.IGNORECASE if ignore_case else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            raise ToolExecutionError(
                message=f"无效的正则表达式: {pattern}",
                tool_name=self.name,
                error_details=e,
            ) from e

        results = []
        match_count = 0

        def search_file(file_path: Path) -> None:
            nonlocal match_count
            if not self._should_include_file(file_path, include, exclude):
                return
            if not file_path.is_file():
                return

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, start=1):
                        if max_count is not None and match_count >= max_count:
                            return
                        if regex.search(line):
                            match_count += 1
                            if line_number:
                                results.append(f"{file_path}:{line_num}:{line.rstrip()}")
                            else:
                                results.append(f"{file_path}:{line.rstrip()}")
                            if max_count is not None and match_count >= max_count:
                                return
            except Exception:
                pass

        if safe_path.is_file():
            search_file(safe_path)
        elif safe_path.is_dir():
            if recursive:
                for file_path in safe_path.rglob("*"):
                    if file_path.is_file():
                        search_file(file_path)
                        if max_count is not None and match_count >= max_count:
                            break
            else:
                for file_path in safe_path.iterdir():
                    if file_path.is_file():
                        search_file(file_path)
                        if max_count is not None and match_count >= max_count:
                            break

        result_text = "\n".join(results)
        if max_count is not None and match_count >= max_count:
            result_text += f"\n[已达到最大匹配行数限制: {max_count}]"

        return result_text if result_text else "未找到匹配的内容"


class CreateFileTool(BaseTool):
    """创建新文件"""

    @property
    def name(self) -> str:
        return "create_file"

    @property
    def type(self) -> str:
        return ToolType.FUNCTION

    @property
    def permission(self) -> str:
        return "edit"

    @property
    def description(self) -> str:
        return "创建一个新文件并写入完整内容。如果目录不存在会自动创建；如果文件已存在会直接失败。"

    def display(self, filepath: str = "", **kwargs) -> str:
        """工具显示名称"""
        if filepath:
            return f"创建文件 {filepath}"
        return "创建文件"

    @property
    def parameters(self) -> ToolFunctionParameters:
        return ToolFunctionParameters(
            properties={
                "filepath": {
                    "type": "string",
                    "description": "要创建的文件路径（包含文件名）。如果中间目录不存在，会自动 mkdir -p。",
                },
                "content": {
                    "type": "string",
                    "description": "文件的完整内容（一次性写入）",
                },
            },
            required=["filepath", "content"],
        )

    def do_run(self, filepath: str, content: str, **kwargs) -> str:
        """执行创建文件操作

        Args:
            filepath: 文件路径
            content: 文件内容

        Returns:
            str: 操作结果

        Raises:
            FileExistsError: 如果文件已存在
        """
        safe_path = _safe_path(filepath)
        if safe_path.exists():
            raise ToolExecutionError(
                message=f"文件已存在: {filepath}",
                tool_name=self.name,
            )

        try:
            safe_path.parent.mkdir(parents=True, exist_ok=True)
            with open(safe_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"文件创建成功: {filepath}"
        except Exception as e:
            raise ToolExecutionError(
                message=f"创建文件失败: {filepath}",
                tool_name=self.name,
                error_details=e,
            ) from e


class InsertFileContentTool(BaseTool):
    """在文件指定位置插入内容"""

    @property
    def name(self) -> str:
        return "insert_file_content"

    @property
    def type(self) -> str:
        return ToolType.FUNCTION

    @property
    def permission(self) -> str:
        return "edit"

    @property
    def description(self) -> str:
        return "在文件指定位置插入内容。"

    def display(self, file_path: str = "", line_number: int = 0, **kwargs) -> str:
        """工具显示名称"""
        if file_path and line_number:
            return f"在 {file_path} 第 {line_number} 行插入内容"
        elif file_path:
            return f"在 {file_path} 插入内容"
        return "插入文件内容"

    @property
    def parameters(self) -> ToolFunctionParameters:
        return ToolFunctionParameters(
            properties={
                "file_path": {
                    "type": "string",
                    "description": "文件路径",
                },
                "content": {
                    "type": "string",
                    "description": "要插入的内容",
                },
                "line_number": {
                    "type": "integer",
                    "description": "插入位置的行号（1-based）",
                },
            },
            required=["file_path", "content", "line_number"],
        )

    def do_run(self, file_path: str, content: str, line_number: int, **kwargs) -> str:
        """执行插入内容操作

        Args:
            file_path: 文件路径
            content: 要插入的内容
            line_number: 插入位置的行号（1-based）

        Returns:
            str: 操作结果
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
            with open(safe_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            total_lines = len(lines)
            insert_pos = max(1, min(line_number, total_lines + 1)) - 1

            lines.insert(insert_pos, content + "\n" if not content.endswith("\n") else content)

            with open(safe_path, "w", encoding="utf-8") as f:
                f.writelines(lines)

            return f"内容已插入到文件 {file_path} 的第 {line_number} 行"
        except Exception as e:
            raise ToolExecutionError(
                message=f"插入内容失败: {file_path}",
                tool_name=self.name,
                error_details=e,
            ) from e


class ReplaceEditFileTool(BaseTool):
    """替换文件中的内容（每次只允许编辑一块）"""

    @property
    def name(self) -> str:
        return "replace_edit_file"

    @property
    def type(self) -> str:
        return ToolType.FUNCTION

    @property
    def permission(self) -> str:
        return "edit"

    @property
    def description(self) -> str:
        return "替换文件中的内容。如果 old_content 在文件中出现多次，会抛出错误。每次只允许替换单一块内容。"

    def display(self, file_path: str = "", **kwargs) -> str:
        """工具显示名称"""
        if file_path:
            return f"替换 {file_path} 中的内容"
        return "替换文件内容"

    @property
    def parameters(self) -> ToolFunctionParameters:
        return ToolFunctionParameters(
            properties={
                "file_path": {
                    "type": "string",
                    "description": "文件路径",
                },
                "old_content": {
                    "type": "string",
                    "description": "要替换的旧内容",
                },
                "new_content": {
                    "type": "string",
                    "description": "新内容",
                },
            },
            required=["file_path", "old_content", "new_content"],
        )

    def do_run(self, file_path: str, old_content: str, new_content: str, **kwargs) -> str:
        """执行替换内容操作

        Args:
            file_path: 文件路径
            old_content: 要替换的旧内容
            new_content: 新内容

        Returns:
            str: 操作结果

        Raises:
            ToolExecutionError: 如果 old_content 出现多次
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
            with open(safe_path, "r", encoding="utf-8") as f:
                content = f.read()

            count = content.count(old_content)
            if count == 0:
                raise ToolExecutionError(
                    message=f"未找到要替换的内容: {file_path}",
                    tool_name=self.name,
                )
            if count > 1:
                raise ToolExecutionError(
                    message=f"要替换的内容在文件中出现 {count} 次，只能替换单一块内容: {file_path}",
                    tool_name=self.name,
                )

            new_file_content = content.replace(old_content, new_content, 1)

            with open(safe_path, "w", encoding="utf-8") as f:
                f.write(new_file_content)

            return f"内容已替换: {file_path}"
        except ToolExecutionError:
            raise
        except Exception as e:
            raise ToolExecutionError(
                message=f"替换内容失败: {file_path}",
                tool_name=self.name,
                error_details=e,
            ) from e


class DeleteFileContentTool(BaseTool):
    """按照行号删除文件内容"""

    @property
    def name(self) -> str:
        return "delete_file_content"

    @property
    def type(self) -> str:
        return ToolType.FUNCTION

    @property
    def permission(self) -> str:
        return "delete"

    @property
    def description(self) -> str:
        return "按照行号删除文件内容。如果不提供 end_line，则只删除一行。"

    def display(self, file_path: str = "", start_line: int = 0, end_line: int = 0, **kwargs) -> str:
        """工具显示名称"""
        if file_path and start_line:
            if end_line and end_line != start_line:
                return f"删除 {file_path} 第 {start_line}-{end_line} 行"
            else:
                return f"删除 {file_path} 第 {start_line} 行"
        elif file_path:
            return f"删除 {file_path} 的内容"
        return "删除文件内容"

    @property
    def parameters(self) -> ToolFunctionParameters:
        return ToolFunctionParameters(
            properties={
                "file_path": {
                    "type": "string",
                    "description": "文件路径",
                },
                "start_line": {
                    "type": "integer",
                    "description": "起始行号（1-based）",
                },
                "end_line": {
                    "type": "integer",
                    "description": "结束行号（1-based，可选）",
                },
            },
            required=["file_path", "start_line"],
        )

    def do_run(self, file_path: str, start_line: int, end_line: Optional[int] = None, **kwargs) -> str:
        """执行删除内容操作

        Args:
            file_path: 文件路径
            start_line: 起始行号（1-based）
            end_line: 结束行号（1-based，可选）

        Returns:
            str: 操作结果
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
            with open(safe_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            total_lines = len(lines)
            start = max(1, min(start_line, total_lines)) - 1
            if end_line is not None:
                end = min(end_line, total_lines)
            else:
                end = start_line

            del lines[start:end]

            with open(safe_path, "w", encoding="utf-8") as f:
                f.writelines(lines)

            deleted_lines = end - start_line + 1 if end_line else 1
            return f"已删除文件 {file_path} 的第 {start_line} 到 {end_line if end_line else start_line} 行（共 {deleted_lines} 行）"
        except Exception as e:
            raise ToolExecutionError(
                message=f"删除内容失败: {file_path}",
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

    def display(self, file_path: str = "", **kwargs) -> str:
        """工具显示名称"""
        if file_path:
            return f"删除文件 {file_path}"
        return "删除文件"

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
            raise FileNotFoundError(f"文件不存在: {file_path}")
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

    def display(self, source_path: str = "", target_path: str = "", **kwargs) -> str:
        """工具显示名称"""
        if source_path and target_path:
            return f"移动文件 {source_path} -> {target_path}"
        elif source_path:
            return f"移动文件 {source_path}"
        return "移动文件"

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


def create_file_tool_group() -> ToolGroup:
    """创建文件工具组

    Returns:
        ToolGroup: 包含所有文件操作工具的工具组
    """
    tools = [
        ListFilesTool(),
        ReadFileTool(),
        GrepSearchTool(),
        CreateFileTool(),
        InsertFileContentTool(),
        ReplaceEditFileTool(),
        DeleteFileContentTool(),
        DeleteFileTool(),
        MoveFileTool(),
    ]

    return ToolGroup(
        name="file_tools",
        description="文件操作工具组，包含文件的读取、创建、编辑、删除等操作",
        tools=tools,
    )

