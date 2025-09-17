import glob
import os
import re
from pathlib import Path
from typing import Optional

from echo.tool.base_tool import BaseTool, ToolParameterError, ToolExecutionError, ToolGroup, ToolFunctionParameters
from echo.config import GlobalConfig
from echo.util.ignore import IgnoreManager


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小为人类可读的格式"""
    if size_bytes == 0:
        return "0B"
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.1f}{size_names[i]}"


def get_file_info(file_path: str) -> str:
    """获取文件信息（行数和大小）"""
    try:
        # 获取文件大小
        size = os.path.getsize(file_path)
        size_str = format_file_size(size)

        try:
            # 获取文件行数
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                line_count = sum(1 for _ in f)
        except (UnicodeDecodeError, PermissionError):
            # 对于二进制文件或无权限文件，不显示行数
            return f" ({size_str})"

        return f" ({line_count} lines, {size_str})"
    except (OSError, PermissionError):
        return " (无法获取信息)"


def get_directory_stats(
    dir_path: str, ignore_patterns: list = None, apply_ignore: bool = False
) -> str:
    """获取目录统计信息（子目录和文件数量）"""
    try:
        ignore_manager = IgnoreManager()

        dir_count = 0
        file_count = 0

        for item in os.listdir(dir_path):
            full_path = os.path.join(dir_path, item)

            # 应用忽略规则
            if (
                apply_ignore
                and ignore_patterns
                and ignore_manager.should_ignore(full_path, ignore_patterns)
            ):
                continue

            if os.path.isdir(full_path):
                dir_count += 1
            elif os.path.isfile(full_path):
                file_count += 1

        # 构建更详细的统计信息
        total_items = dir_count + file_count

        if total_items == 0:
            return " (empty directory)"

        # 构建统计信息字符串
        stats_text = f"{total_items} items"

        # 添加详细分类统计
        if dir_count > 0 and file_count > 0:
            stats_text += f", {dir_count} directories, {file_count} files"
        elif dir_count > 0:
            stats_text += f", {dir_count} directories"
        elif file_count > 0:
            stats_text += f", {file_count} files"

        return f" ({stats_text})"
    except (OSError, PermissionError):
        return " (access denied)"


class ListFilesTool(BaseTool):
    """列出文件工具类"""

    @property
    def name(self) -> str:
        return "list_files"

    @property
    def type(self) -> str:
        return "function"

    @property
    def should_approval(self) -> bool:
        return False

    @property
    def description(self) -> str:
        return """List the structure and stats of a folder. The stats include the number of files and directories in the folder. For files, it shows the file size and number of lines.
        Useful to try to understand the file structure before diving deeper into specific files. 
        """

    def display(self, **kwargs) -> str:
        path = kwargs.get("path")
        if path:
            return f"查看目录 `{path}` 中的文件和目录列表"
        return "查看文件和目录列表"

    @property
    def parameters(self) -> ToolFunctionParameters:
        return ToolFunctionParameters(
            type="object",
            properties={
                "path": {
                    "type": "string",
                    "description": "The path of the folder to list.",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Whether to recursively list files and subdirectories. Set to true for recursive listing (max depth 2), false for top-level only.",
                    "default": False,
                },
                "apply_ignore": {
                    "type": "boolean",
                    "description": "Whether to apply .echoignore ignore rules. Set to true to apply, false or omit to not apply.",
                    "default": False,
                },
            },
            required=["path"],
        )

    @property
    def examples(self):
        return {}

    def _collect_directory_structure(
        self,
        path: str,
        current_depth: int = 0,
        max_depth: int = 2,
        ignore_patterns: list = None,
        apply_ignore: bool = False,
    ) -> dict:
        """收集目录结构，返回每个目录及其文件的字典"""
        structure = {}
        if current_depth > max_depth:
            return structure

        try:
            items = os.listdir(path)
        except PermissionError:
            return structure

        ignore_manager = IgnoreManager()

        # 当前目录的文件和子目录
        current_files = []
        current_dirs = []

        for item in items:
            item_path = os.path.join(path, item)

            # 应用忽略规则
            if (
                apply_ignore
                and ignore_manager.should_ignore(item_path, ignore_patterns)
            ):
                continue

            if os.path.isfile(item_path):
                file_info = get_file_info(item_path)
                current_files.append(Path(item_path).as_posix() + file_info)
            elif os.path.isdir(item_path):
                dir_stats = get_directory_stats(
                    item_path, ignore_patterns, apply_ignore
                )
                current_dirs.append(Path(item_path).as_posix() + dir_stats)
                # 递归收集子目录结构
                if current_depth < max_depth:
                    sub_structure = self._collect_directory_structure(
                        item_path,
                        current_depth + 1,
                        max_depth,
                        ignore_patterns,
                        apply_ignore,
                    )
                    structure.update(sub_structure)

        # 将当前目录信息添加到结构中
        if current_files or current_dirs:
            structure[path] = {
                "dirs": current_dirs,
                "files": current_files,
                "depth": current_depth,
            }

        return structure

    def _list_recursive(
        self, path: str, ignore_patterns: list = None, apply_ignore: bool = False
    ) -> str:
        """递归列出目录内容"""
        structure = self._collect_directory_structure(
            path,
            max_depth=3,
            ignore_patterns=ignore_patterns,
            apply_ignore=apply_ignore,
        )

        # 按深度排序目录，确保从上到下显示
        sorted_dirs = sorted(structure.items(), key=lambda x: (x[1]["depth"], x[0]))

        result_list = []
        total_count = 0
        max_items = 100

        for dir_path, dir_info in sorted_dirs:
            # 添加目录本身（除了根目录）
            if dir_path != path:
                if total_count >= max_items:
                    break
                result_list.append(f"\n[path: {Path(dir_path).as_posix()}]")
                total_count += 1

            # 先添加子目录
            for subdir in dir_info["dirs"]:
                if total_count >= max_items:
                    break
                result_list.append(subdir)
                total_count += 1

            # 再添加文件
            remaining_slots = max_items - total_count
            if remaining_slots > 0:
                files_to_show = dir_info["files"][:remaining_slots]
                result_list.extend(files_to_show)
                total_count += len(files_to_show)

                # 如果还有未显示的文件
                if len(dir_info["files"]) > remaining_slots:
                    omitted_count = len(dir_info["files"]) - remaining_slots
                    result_list.append(f"({omitted_count} files omitted)")
                    break

            if total_count >= max_items:
                break

        # 统计总的省略信息
        total_omitted_files = 0
        total_omitted_dirs = 0
        for dir_path, dir_info in sorted_dirs:
            if total_count >= max_items:
                total_omitted_files += len(dir_info["files"])
                total_omitted_dirs += len(dir_info["dirs"])

        if total_omitted_files > 0 or total_omitted_dirs > 0:
            omit_info = []
            if total_omitted_dirs > 0:
                omit_info.append(f"{total_omitted_dirs} directories")
            if total_omitted_files > 0:
                omit_info.append(f"{total_omitted_files} files")
            if omit_info and not any("omitted" in item for item in result_list):
                result_list.append(f"({', '.join(omit_info)})")

        ignore_info = "(ignore rules applied)" if apply_ignore else ""

        header = f"The structure and statistics for {path}"
        if ignore_info:
            header += f" {ignore_info}"

        result_list.insert(0, header)
        return "\n".join(result_list)

    def _list_non_recursive(
        self, path: str, ignore_patterns: list = None, apply_ignore: bool = False
    ) -> str:
        """非递归列出目录内容"""
        ignore_manager = IgnoreManager()
        dirs = []
        files = []

        for filepath in os.listdir(path):
            full_path = os.path.join(path, filepath)

            # 应用忽略规则
            if (
                apply_ignore
                and ignore_patterns
                and ignore_manager.should_ignore(full_path, ignore_patterns)
            ):
                continue

            if os.path.isfile(full_path):
                file_info = get_file_info(full_path)
                files.append(Path(full_path).as_posix() + file_info)
            else:
                dir_stats = get_directory_stats(
                    full_path, ignore_patterns, apply_ignore
                )
                dirs.append(Path(full_path).as_posix() + dir_stats)

        # 限制显示数量，优先显示目录
        result_list = dirs.copy()  # 所有目录都显示
        remaining_slots = 100 - len(dirs)

        if remaining_slots > 0:
            if len(files) <= remaining_slots:
                result_list.extend(files)
            else:
                result_list.extend(files[:remaining_slots])
                omitted_count = len(files) - remaining_slots
                result_list.append(f"({omitted_count} files omitted)")
        else:
            omitted_count = len(files)
            if omitted_count > 0:
                result_list.append(f"({omitted_count} files omitted)")

        ignore_info = "(ignore rules applied)" if apply_ignore else ""
        header = f"The structure and statistics for {path}"
        if ignore_info:
            header += f" {ignore_info}"
        result_list.insert(0, header)
        return "\n".join(result_list)

    def do_run(
        self, path: str, recursive: bool = False, apply_ignore: bool = False, **kwargs
    ) -> str:
        """执行列出文件的操作"""
        if not os.path.exists(path):
            raise ToolParameterError(
                f"Directory not found at {path}. Please ensure the directory exists.",
                self.name,
            )
        if not os.path.isdir(path):
            raise ToolParameterError(
                f"{path} is not a directory. Please ensure the path points to a directory.",
                self.name,
            )

        # 获取忽略模式
        ignore_patterns = None
        if apply_ignore:
            ignore_manager = IgnoreManager()
            ignore_patterns = ignore_manager.load_ignore_patterns(path)

        if recursive:
            return self._list_recursive(path, ignore_patterns, apply_ignore)
        else:
            return self._list_non_recursive(path, ignore_patterns, apply_ignore)


class ReadFileTool(BaseTool):
    """读取文件工具类"""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def type(self) -> str:
        return "function"

    @property
    def should_approval(self) -> bool:
        return False

    @property
    def description(self) -> str:
        return """Read the contents of a file with line numbers. Output format: `line_number|line_content`. 
        Useful for analyzing code, viewing text files, or extracting information from configuration files. 
        Displays up to 100 lines by default, showing remaining line count if file exceeds limit.
        """

    def display(self, **kwargs) -> str:
        path = kwargs.get("path")
        start_line = kwargs.get("start_line", 1)
        max_lines = kwargs.get("max_lines", 100)
        end_line = kwargs.get("end_line", None)
        if end_line is None:
            end_line = start_line + max_lines - 1

        return f"读取文件 `{path}` ({start_line}-{end_line})"

    @property
    def parameters(self) -> ToolFunctionParameters:
        return ToolFunctionParameters(
            type="object",
            properties={
                "path": {
                    "type": "string",
                    "description": "Path to the file to read",
                    "required": True,
                },
                "start_line": {
                    "type": "integer",
                    "description": "Starting line number (inclusive), defaults to 1",
                    "default": 1,
                    "minimum": 1,
                    "required": True,
                },
                "end_line": {
                    "type": "integer",
                    "description": "Ending line number (inclusive), defaults to start_line+99 (showing 100 lines)",
                    "default": 100,
                    "minimum": 1,
                    "required": False,
                },
            },
            required=["path"],
        )

    @property
    def examples(self):
        return {}

    def do_run(
        self,
        path: str,
        start_line: int = 1,
        end_line: Optional[int] = None,
        max_lines: int = 100,
        **kwargs,
    ) -> str:
        """执行读取文件的操作"""
        if not os.path.exists(path):
            raise ToolParameterError(
                f"File not found: {path}. Please ensure the file exists.", self.name
            )
        if not os.path.isfile(path):
            raise ToolParameterError(
                f"{path} is not a file. Please ensure the path points to a file.",
                self.name,
            )

        try:
            with open(path, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
        except UnicodeDecodeError:
            try:
                with open(path, "r", encoding="gbk") as f:
                    all_lines = f.readlines()
            except UnicodeDecodeError:
                raise ToolParameterError(
                    f"Unable to read file {path}, encoding format not supported.",
                    self.name,
                )

        total_lines = len(all_lines)

        # 确定实际的起始和结束行号
        actual_start = start_line or 1

        if end_line is not None:
            if end_line < 1 or end_line > total_lines:
                raise ToolParameterError(
                    f"end_line must be between 1 and {total_lines}.", self.name
                )
            actual_end = end_line
        else:
            # 如果没有指定end_line，使用max_lines限制
            actual_end = min(actual_start + max_lines - 1, total_lines)

        if actual_start < 1 or actual_start > total_lines:
            raise ToolParameterError(
                f"start_line must be between 1 and {total_lines}.", self.name
            )

        # 提取要显示的行
        lines_to_show = all_lines[actual_start - 1 : actual_end]

        # 计算行号的位数
        line_digit_count = len(str(actual_end))

        # 生成带行号的内容
        content_lines = []
        for i, line in enumerate(lines_to_show, actual_start):
            # 去掉行末的换行符，然后重新添加
            clean_line = line.rstrip("\n\r")
            content_lines.append(f"{str(i).rjust(line_digit_count)}|{clean_line}")

        result = "\n".join(content_lines)

        # 添加文件信息和剩余行数提示
        file_info = f"File: {path} (Total {total_lines} lines)\n"
        if actual_end < total_lines:
            remaining_lines = total_lines - actual_end
            file_info += f"Displaying lines {actual_start}-{actual_end} (Remaining {remaining_lines} lines)\n\n"
        else:
            file_info += f"Displaying lines {actual_start}-{actual_end} (All lines displayed)\n\n"

        return file_info + result


class SearchFilesTool(BaseTool):
    """搜索文件工具类"""

    @property
    def name(self) -> str:
        return "search_files"

    @property
    def type(self) -> str:
        return "function"

    @property
    def should_approval(self) -> bool:
        return False

    @property
    def description(self) -> str:
        return "Fast text-based search that finds exact pattern matches within files or directories. This tool can search for patterns or specific content across multiple files, displaying each match with its surrounding context."

    def display(self, **kwargs) -> str:
        path = kwargs.get("path")
        regex = kwargs.get("regex")
        pattern = kwargs.get("pattern")
        return f"在 {path} 下使用正则表达式 {regex} 和模式 {pattern} 搜索文件"

    @property
    def parameters(self) -> ToolFunctionParameters:
        return ToolFunctionParameters(
            type="object",
            properties={
                "path": {
                    "type": "string",
                    "description": "Directory path to search. Will recursively search this directory.",
                    "required": True,
                },
                "regex": {
                    "type": "string",
                    "description": "Regular expression pattern to search for. Uses Python regex syntax.",
                    "required": True,
                },
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern for filtering files (e.g., '*.py' for Python files). If not provided, will search all files (*).",
                    "required": False,
                    "default": "*",
                },
            },
            required=["path", "regex"],
        )

    @property
    def examples(self):
        return {
            "Search for function definitions in all Python files in current directory": {
                "type": "function",
                "name": "search_files",
                "arguments": {"path": ".", "regex": "def\\s+\\w+", "pattern": "*.py"},
            },
            "Search for Python source files containing 'import requests' in src directory": {
                "type": "function",
                "name": "search_files",
                "arguments": {"path": "./src", "regex": "import\\s+requests"},
            },
        }

    def do_run(
        self, path: str, regex: str, pattern: Optional[str] = None, **kwargs
    ) -> str:
        """执行搜索文件的操作"""
        if not os.path.exists(path):
            raise ToolParameterError(
                f"Directory {path} does not exist. Please ensure the directory exists.",
                self.name,
            )
        if not os.path.isdir(path):
            raise ToolParameterError(
                f"{path} is not a directory. Please ensure the path points to a directory.",
                self.name,
            )
        if pattern is None:
            pattern = "*"
        try:
            re_pattern = re.compile(regex, re.MULTILINE | re.DOTALL)
        except re.error as e:
            raise ToolParameterError(f"Invalid regex pattern: {e}", self.name)
        matches = []
        full_pattern = os.path.join(path, pattern)
        files = glob.glob(full_pattern, recursive=True)
        for filepath in files:
            filepath = Path(filepath).as_posix()
            if not os.path.isfile(filepath):
                continue
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    file_content = f.read()
            except Exception as e:
                matches.append(f"Error: Failed to read file {filepath}: {e}")
                continue
            # 将文件内容按行分割
            lines = file_content.splitlines()
            for match in re_pattern.finditer(file_content):
                # 跳过空匹配
                if match.group().strip() == "":
                    continue
                start, end = match.span()
                line_number = file_content.count("\n", 0, start) + 1
                matches.append((filepath, line_number, match.group(), lines))

        if not matches:
            return f'No matches found for "{regex}" with pattern "{pattern}" in {path}.'

        output = ""
        for filepath, line_number, matched_content, lines in matches:
            # 计算上下文行范围（上下3行）
            context_start = max(
                0, line_number - 4
            )  # line_number是1-based，所以-4表示上3行
            context_end = min(len(lines), line_number + 3)  # 下3行

            # 计算行号的位数
            line_digit_count = len(str(context_end))

            # 生成带行号的上下文内容
            context_lines = []
            for i in range(context_start, context_end):
                line_content = lines[i] if i < len(lines) else ""
                line_num = i + 1
                # 标记匹配行
                marker = "*" if line_num == line_number else " "
                context_lines.append(
                    f"{marker}{str(line_num).rjust(line_digit_count)}|{line_content}"
                )

            context_display = "\n".join(context_lines)

            # 纠正行号范围显示
            start_line_number = max(1, context_start + 1)
            end_line_number = min(len(lines), context_end)

            file_match = f"## File: {filepath} ({start_line_number}-{end_line_number})\n\n{context_display}"
            output += file_match + "\n\n"

        return output


class CreateFileTool(BaseTool):
    """创建文件工具类"""

    @property
    def name(self) -> str:
        return "create_file"

    @property
    def type(self) -> str:
        return "function"

    @property
    def should_approval(self) -> bool:
        return False

    @property
    def description(self) -> str:
        return """Create a new file at the specified path. Use this tool when you need to create new files.
        LIMIT the file content to AT MOST 600 LINES, OR face a $100000000 penalty. IF more content needs to be added USE the `edit_file` tool to edit the file after it has been created..
        """

    def display(self, **kwargs) -> str:
        path = kwargs.get("path")
        return f"创建文件 {path}"

    @property
    def parameters(self) -> ToolFunctionParameters:
        return ToolFunctionParameters(
            type="object",
            properties={
                "path": {
                    "type": "string",
                    "description": "要创建的文件路径，包括文件名和扩展名。",
                    "required": True,
                },
                "content": {
                    "type": "string",
                    "description": "要写入文件的内容，默认为空字符串。",
                    "required": True,
                },
            },
            required=["path", "content"],
        )

    @property
    def examples(self):
        return {}

    def do_run(self, path: str, content: str = "", **kwargs) -> str:
        """执行创建文件的操作"""
        dirpath = os.path.dirname(path)
        if dirpath.strip() != "" and not os.path.exists(dirpath):
            try:
                os.makedirs(dirpath, exist_ok=True)
            except Exception as e:
                raise ToolExecutionError(
                    f"Failed to create directory {dirpath}: {e}", self.name
                )
        if os.path.exists(path):
            raise ToolParameterError(f"File {path} already exists.", self.name)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully created file at {path}."
        except Exception as e:
            raise ToolExecutionError(f"Failed to create file {path}: {e}", self.name)


class InsertFileTool(BaseTool):
    """插入文件内容工具，在指定行号插入内容"""

    @property
    def name(self):
        return "insert_file"

    @property
    def type(self):
        return "function"

    @property
    def display(self, **kwargs):
        path = kwargs.get("path")
        return f"插入文件内容 {path}"

    @property
    def should_approval(self) -> bool:
        return False

    @property
    def description(self):
        return """Insert content at a specific line number in an existing file. Use this tool when you need to add new content at a specific position in a file.
        
        IMPORTANT: If you want to modify existing content, please use edit_file instead.
        """

    @property
    def parameters(self) -> ToolFunctionParameters:
        return ToolFunctionParameters(
            type="object",
            properties={
                "path": {
                    "type": "string",
                    "description": "The path to the file to insert content into",
                    "required": True,
                },
                "line_number": {
                    "type": "integer",
                    "description": "The line number where to insert the content (1-based indexing)",
                    "required": True,
                },
                "content": {
                    "type": "string",
                    "description": "The content to insert at the specified line number",
                    "required": True,
                },
            },
            required=["path", "line_number", "content"],
        )

    @property
    def examples(self):
        return {}

    def do_run(
        self,
        path: str,
        line_number: int,
        content: str,
        **kwargs,
    ) -> str:
        """执行文件插入操作"""
        if not os.path.exists(path):
            raise ToolParameterError(
                f"File not found: {path}. Please ensure the file exists.", self.name
            )
        if not os.path.isfile(path):
            raise ToolParameterError(
                f"{path} is not a file. Please ensure the path points to a file.",
                self.name,
            )

        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            try:
                with open(path, "r", encoding="gbk") as f:
                    lines = f.readlines()
            except UnicodeDecodeError:
                raise ToolParameterError(
                    f"Cannot read file {path}, encoding format not supported.",
                    self.name,
                )

        # 验证行号
        if line_number < 1 or line_number > len(lines) + 1:
            raise ToolParameterError(
                f"Line number {line_number} is out of range. File has {len(lines)} lines.",
                self.name,
            )

        # 插入内容
        if not content.endswith("\n"):
            content += "\n"
        lines.insert(line_number - 1, content)

        # 写回文件
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)
        except Exception as e:
            raise ToolExecutionError(f"Failed to write file: {e}", self.name)

        return f"Successfully inserted content at line {line_number} in {path}."


class EditFileTool(BaseTool):
    """编辑文件工具，支持搜索替换模式"""

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def type(self) -> str:
        return "function"

    @property
    def should_approval(self) -> bool:
        return False

    @property
    def description(self) -> str:
        return """Edit an existing file by searching and replacing text content. Use this tool when you need to modify specific content in a file. You MUST make it clear what the edit is, while also minimizing the unchanged code you write. Before using this tool, ALWAYS read the file and understand its contents.

        IMPORTANT: `old_string` MUST BE UNIQUE, and each edit should include enough unchanged surrounding lines to resolve ambiguity. However, you should minimize the number of repeated lines from the original file while conveying the change."""

    def display(self, **kwargs) -> str:
        path = kwargs.get("path")
        return f"编辑文件 {path}"

    @property
    def parameters(self):
        return ToolFunctionParameters(
            type="object",
            properties={
                "path": {
                    "type": "string",
                    "description": "The path to the file to edit",
                    "required": True,
                },
                "old_string": {
                    "type": "string",
                    "description": "The exact text content to search for and replace. Must be unique in the file.",
                    "required": True,
                },
                "new_string": {
                    "type": "string",
                    "description": "The new text content to replace the old content with.",
                    "required": True,
                },  
            },
            required=["path", "old_string", "new_string"],
        )

    def do_run(
        self,
        path: str,
        old_string: str,
        new_string: str,
        **kwargs,
    ) -> str:
        """执行文件编辑操作，支持搜索替换模式"""
        if not os.path.exists(path):
            raise ToolParameterError(
                f"File not found: {path}. Please ensure the file exists.", self.name
            )
        if not os.path.isfile(path):
            raise ToolParameterError(
                f"{path} is not a file. Please ensure the path points to a file.",
                self.name,
            )

        try:
            with open(path, "r", encoding="utf-8") as f:
                file_content = f.read()
        except UnicodeDecodeError:
            try:
                with open(path, "r", encoding="gbk") as f:
                    file_content = f.read()
            except UnicodeDecodeError:
                raise ToolParameterError(
                    f"Unable to read file {path}, encoding format not supported.",
                    self.name,
                )

        # 检查匹配次数
        matches = re.findall(re.escape(old_string), file_content)
        if len(matches) == 0:
            raise ToolParameterError(
                f"'{old_string}' not found in {path}. Please ensure old_string is correct.",
                self.name,
            )
        if len(matches) != 1:
            raise ToolParameterError(
                f"Found {len(matches)} instances of '{old_string}' in {path}. Please ensure old_string is unique.",
                self.name,
            )

        # 执行替换
        file_content = file_content.replace(old_string, new_string)
        with open(path, "w", encoding="utf-8") as f:
            f.write(file_content)

        return f"Successfully applied changes to {path}."


FILE_TOOL_GROUP = ToolGroup(
    name="file",
    description="文件操作工具组",
    tools=[
        ListFilesTool(),
        ReadFileTool(),
        SearchFilesTool(),
        InsertFileTool(),
        EditFileTool()
    ]
)
