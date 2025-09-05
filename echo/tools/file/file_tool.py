import glob
import os
import re
from pathlib import Path
from typing import Optional

from echo.tools.base_tool import BaseTool, ToolParameterError, ToolExecutionError
from echo.config import GlobalConfig


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
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                line_count = sum(1 for _ in f)
        except (UnicodeDecodeError, PermissionError):
            # 对于二进制文件或无权限文件，不显示行数
            return f" ({size_str})"
        
        return f" ({line_count} lines, {size_str})"
    except (OSError, PermissionError):
        return " (无法获取信息)"


def get_directory_stats(dir_path: str, ignore_patterns: list = None, apply_ignore: bool = False) -> str:
    """获取目录统计信息（子目录和文件数量）"""
    try:
        config = GlobalConfig.get_instance()
        ignore_manager = config.get_ignore_manager()
        
        dir_count = 0
        file_count = 0
        
        for item in os.listdir(dir_path):
            full_path = os.path.join(dir_path, item)
            
            # 应用忽略规则
            if apply_ignore and ignore_patterns and ignore_manager.should_ignore(full_path, ignore_patterns):
                continue
                
            if os.path.isdir(full_path):
                dir_count += 1
            elif os.path.isfile(full_path):
                file_count += 1
        
        stats = []
        if dir_count > 0:
            stats.append(f"{dir_count} 个目录")
        if file_count > 0:
            stats.append(f"{file_count} 个文件")
        
        if stats:
            return f" ({', '.join(stats)})"
        else:
            return " (空目录)"
    except (OSError, PermissionError):
        return " (无法访问)"


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
        return """ 查看指定目录中的文件和目录。支持递归遍历子目录，可以根据.echoignore文件中定义的规则过滤不需要的文件和目录。显示每个文件的详细信息包括文件大小，以及每个目录包含的文件和子目录数量统计。"""
    
    def display(self, **kwargs) -> str:
        path = kwargs.get("path")
        if path:
            return f"查看目录 '{path}' 中的文件和目录列表"
        return "查看文件和目录列表"
    
    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要查看的目录路径",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "是否递归查看目录中的文件和子目录。使用true进行递归查看，最大深度为2层，false或省略仅查看顶级内容。",
                    "default": False
                },
                "apply_ignore": {
                    "type": "boolean",
                    "description": "是否应用.echoignore忽略规则。使用true应用忽略规则，false或省略则不应用。",
                    "default": False
                }
            },
            "required": ["path"],
        }
    
    @property
    def examples(self):
        return {
            "查看当前目录中的所有文件和目录": {
                "type": self.type,
                "name": self.name,
                "arguments": {
                    "path": ".",
                    "recursive": False,
                    "apply_ignore": False
                }
            }
        }

    def _collect_directory_structure(self, path: str, current_depth: int = 0, max_depth: int = 2, ignore_patterns: list = None, apply_ignore: bool = False) -> dict:
        """收集目录结构，返回每个目录及其文件的字典"""
        structure = {}
        if current_depth > max_depth:
            return structure
        
        try:
            items = os.listdir(path)
        except PermissionError:
            return structure
        
        config = GlobalConfig.get_instance()
        ignore_manager = config.get_ignore_manager()
        
        # 当前目录的文件和子目录
        current_files = []
        current_dirs = []
        
        for item in items:
            item_path = os.path.join(path, item)
            
            # 应用忽略规则
            if apply_ignore and ignore_patterns and ignore_manager.should_ignore(item_path, ignore_patterns):
                continue
            
            if os.path.isfile(item_path):
                file_info = get_file_info(item_path)
                current_files.append(Path(item_path).as_posix() + file_info)
            elif os.path.isdir(item_path):
                dir_stats = get_directory_stats(item_path, ignore_patterns, apply_ignore)
                current_dirs.append(Path(item_path).as_posix() + dir_stats)
                # 递归收集子目录结构
                if current_depth < max_depth:
                    sub_structure = self._collect_directory_structure(item_path, current_depth + 1, max_depth, ignore_patterns, apply_ignore)
                    structure.update(sub_structure)
        
        # 将当前目录信息添加到结构中
        if current_files or current_dirs:
            structure[path] = {
                "dirs": current_dirs,
                "files": current_files,
                "depth": current_depth
            }
        
        return structure

    def _list_recursive(self, path: str, ignore_patterns: list = None, apply_ignore: bool = False) -> str:
        """递归列出目录内容"""
        structure = self._collect_directory_structure(path, max_depth=3, ignore_patterns=ignore_patterns, apply_ignore=apply_ignore)
        
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
                result_list.append(f"\n[目录: {Path(dir_path).as_posix()}]")
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
                    result_list.append(f"（省略 {omitted_count} 个文件）")
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
                omit_info.append(f"{total_omitted_dirs} 个目录")
            if total_omitted_files > 0:
                omit_info.append(f"{total_omitted_files} 个文件")
            if omit_info and not any("省略" in item for item in result_list):
                result_list.append(f"（省略 {' 和 '.join(omit_info)}）")
        
        ignore_info = "（应用忽略规则）" if apply_ignore else ""
        return f"成功递归查看 {os.path.abspath(path)} 中的所有文件和目录（最大深度2）{ignore_info}：\n" + "\n".join(result_list)
    
    def _list_non_recursive(self, path: str, ignore_patterns: list = None, apply_ignore: bool = False) -> str:
        """非递归列出目录内容"""
        config = GlobalConfig.get_instance()
        ignore_manager = config.get_ignore_manager()
        dirs = []
        files = []
        
        for filepath in os.listdir(path):
            full_path = os.path.join(path, filepath)
            
            # 应用忽略规则
            if apply_ignore and ignore_patterns and ignore_manager.should_ignore(full_path, ignore_patterns):
                continue
            
            if os.path.isfile(full_path):
                file_info = get_file_info(full_path)
                files.append(Path(full_path).as_posix() + file_info)
            else:
                dir_stats = get_directory_stats(full_path, ignore_patterns, apply_ignore)
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
                result_list.append(f"（省略 {omitted_count} 个文件）")
        else:
            omitted_count = len(files)
            if omitted_count > 0:
                result_list.append(f"（省略 {omitted_count} 个文件）")
        
        ignore_info = "（应用忽略规则）" if apply_ignore else ""
        return f"成功查看 {os.path.abspath(path)} 中的所有文件和目录{ignore_info}：\n" + "\n".join(result_list)
    
    def do_run(self, path: str, recursive: bool = False, apply_ignore: bool = False, **kwargs) -> str:
        """执行列出文件的操作"""
        if not os.path.exists(path):
            raise ToolParameterError(f"在 {path} 处未找到目录。请确保目录存在。", self.name)
        if not os.path.isdir(path):
            raise ToolParameterError(f"{path} 不是一个目录。请确保路径指向一个目录。", self.name)
        
        # 获取忽略模式
        ignore_patterns = None
        if apply_ignore:
            config = GlobalConfig.get_instance()
            ignore_manager = config.get_ignore_manager()
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
        return """读取指定路径文件的内容。用于查看现有文件的内容，例如分析代码、查看文本文件或从配置文件中提取信息。输出包含行号前缀（例如 "1 | const x = 1"）。默认每次显示100行，如果文件超过100行会显示剩余行数。
        """
    
    def display(self, **kwargs) -> str:
        return "读取文件"
    
    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要读取的文件路径"
                },
                "start_line": {
                    "type": "integer",
                    "description": "起始行号（包含），默认为1",
                    "minimum": 1
                },
                "end_line": {
                    "type": "integer",
                    "description": "结束行号（包含），默认为start_line+99（即显示100行）",
                    "minimum": 1
                },
                "max_lines": {
                    "type": "integer",
                    "description": "最大显示行数，默认为100",
                    "default": 100,
                    "minimum": 1,
                    "maximum": 1000
                }
            },
            "required": ["path"]
        }
    
    @property
    def examples(self):
        return {
            "读取整个文件（默认显示前100行）": {
                "type": "function",
                "name": "read_file",
                "arguments": {
                    "path": "/path/to/file"
                }
            },
            "读取文件的前200行": {
                "type": "function",
                "name": "read_file",
                "arguments": {
                    "path": "/path/to/large_file",
                    "max_lines": 200
                }
            },
            "读取文件的第500-600行": {
                "type": "function",
                "name": "read_file",
                "arguments": {
                    "path": "/path/to/csv_file",
                    "start_line": 500,
                    "end_line": 600
                }
            },
            "读取源文件中的特定函数": {
                "type": "function",
                "name": "read_file",
                "arguments": {
                    "path": "/path/to/source_file",
                    "start_line": 46,
                    "end_line": 68
                }
            }
        }

    def do_run(self, path: str, start_line: Optional[int] = None, end_line: Optional[int] = None, max_lines: int = 100, **kwargs) -> str:
        """执行读取文件的操作"""
        if not os.path.exists(path):
            raise ToolParameterError(f"文件未找到：{path}。请确保文件存在。", self.name)
        if not os.path.isfile(path):
            raise ToolParameterError(f"{path} 不是一个文件。请确保路径指向一个文件。", self.name)
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
        except UnicodeDecodeError:
            try:
                with open(path, "r", encoding="gbk") as f:
                    all_lines = f.readlines()
            except UnicodeDecodeError:
                raise ToolParameterError(f"无法读取文件 {path}，编码格式不支持。", self.name)
        
        total_lines = len(all_lines)
        
        # 确定实际的起始和结束行号
        actual_start = start_line or 1
        
        if end_line is not None:
            if end_line < 1 or end_line > total_lines:
                raise ToolParameterError(f"end_line 必须在 1 到 {total_lines} 之间。", self.name)
            actual_end = end_line
        else:
            # 如果没有指定end_line，使用max_lines限制
            actual_end = min(actual_start + max_lines - 1, total_lines)
        
        if actual_start < 1 or actual_start > total_lines:
            raise ToolParameterError(f"start_line 必须在 1 到 {total_lines} 之间。", self.name)
        
        # 提取要显示的行
        lines_to_show = all_lines[actual_start - 1:actual_end]
        
        # 计算行号的位数
        line_digit_count = len(str(actual_end))
        
        # 生成带行号的内容
        content_lines = []
        for i, line in enumerate(lines_to_show, actual_start):
            # 去掉行末的换行符，然后重新添加
            clean_line = line.rstrip('\n\r')
            content_lines.append(f"{str(i).rjust(line_digit_count)}|{clean_line}")
        
        result = "\n".join(content_lines)
        
        # 添加文件信息和剩余行数提示
        file_info = f"文件：{path}（共 {total_lines} 行）\n"
        if actual_end < total_lines:
            remaining_lines = total_lines - actual_end
            file_info += f"显示第 {actual_start}-{actual_end} 行（剩余 {remaining_lines} 行）\n\n"
        else:
            file_info += f"显示第 {actual_start}-{actual_end} 行（已显示全部内容）\n\n"
        
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
        return "在指定目录中执行正则表达式搜索，提供上下文丰富的结果。此工具可以跨多个文件搜索模式或特定内容，显示每个匹配项及其周围的上下文。"
    
    def display(self, **kwargs) -> str:
        return "搜索文件"
    
    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要搜索的目录路径。将递归搜索此目录。",
                },
                "regex": {
                    "type": "string",
                    "description": "要搜索的正则表达式模式。使用Python正则表达式语法。",
                },
                "pattern": {
                    "type": "string",
                    "description": "用于过滤文件的Glob模式（例如，'*.py'表示Python文件）。如果未提供，将搜索所有文件（*）。"
                }
            },
            "required": ["path", "regex"]
        }
    
    @property
    def examples(self):
        return {
            "在当前目录搜索所有Python文件中的函数定义": {
                "type": "function",
                "name": "search_files",
                "arguments": {
                    "path": ".",
                    "regex": "def\\s+\\w+",
                    "pattern": "*.py"
                }
            },
            "在src目录中搜索所有包含'import requests'的Python源代码文件": {
                "type": "function",
                "name": "search_files",
                "arguments": {
                    "path": "./src",
                    "regex": "import\\s+requests"
                }
            }
        }

    def do_run(self, path: str, regex: str, pattern: Optional[str] = None, **kwargs) -> str:
        """执行搜索文件的操作"""
        if not os.path.exists(path):
            raise ToolParameterError(f"目录 {path} 不存在。请确保目录存在。", self.name)
        if not os.path.isdir(path):
            raise ToolParameterError(f"{path} 不是一个目录。请确保路径指向一个目录。", self.name)
        if pattern is None:
            pattern = "*"
        try:
            re_pattern = re.compile(regex, re.MULTILINE | re.DOTALL)
        except re.error as e:
            raise ToolParameterError(f"无效的正则表达式模式: {e}", self.name)
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
                matches.append(f"错误：读取文件 {filepath} 失败：{e}")
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
            return f"在 {path} 中使用模式 \"{pattern}\" 搜索 \"{regex}\" 未找到匹配项。"
        
        output = ""
        for filepath, line_number, matched_content, lines in matches:
            # 计算上下文行范围（上下3行）
            context_start = max(0, line_number - 4)  # line_number是1-based，所以-4表示上3行
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
                context_lines.append(f"{marker}{str(line_num).rjust(line_digit_count)}|{line_content}")
            
            context_display = "\n".join(context_lines)
            
            file_match = f"## 文件: {filepath}\n匹配行: {line_number}\n匹配内容: {matched_content}\n\n{context_display}"
            output += file_match + "\n\n"
        
        return f"成功在 {path} 中搜索 \"{regex}\"，找到 {len(matches)} 个匹配项：\n\n{output}"


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
        return """在指定路径创建新文件。当需要创建新的配置文件或源代码文件时使用此工具。如果文件已存在将返回错误，如果父目录不存在将自动创建。"""
    
    def display(self, **kwargs) -> str:
        return "创建文件"
    
    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要创建的文件路径，包括文件名和扩展名。"
                },
                "content": {
                    "type": "string",
                    "description": "要写入文件的内容，默认为空字符串。"
                }
            },
            "required": ["path", "content"]
        }
    
    @property
    def examples(self):
        return {
            "创建新的文本文件": {
                "type": "function",
                "name": "create_file",
                "arguments": {
                    "path": "/path/to/new_file.txt",
                    "content": "这是新文件的内容。"
                }
            },
            "创建空的Python文件": {
                "type": "function",
                "name": "create_file",
                "arguments": {
                    "path": "/path/to/script.py",
                    "content": "#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n\n"
                }
            }
        }

    def do_run(self, path: str, content: str = "", **kwargs) -> str:
        """执行创建文件的操作"""
        dirpath = os.path.dirname(path)
        if dirpath.strip() != "" and not os.path.exists(dirpath):
            try:
                os.makedirs(dirpath, exist_ok=True)
            except Exception as e:
                raise ToolExecutionError(f"创建目录 {dirpath} 失败: {e}", self.name)
        if os.path.exists(path):
            raise ToolParameterError(f"文件 {path} 已存在。", self.name)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"成功在 {path} 创建文件。"
        except Exception as e:
            raise ToolExecutionError(f"创建文件 {path} 失败: {e}", self.name)


class EditFileTool(BaseTool):
    """文件编辑工具类，支持搜索替换和插入操作"""
    
    @property
    def name(self) -> str:
        return "edit_file"
    
    @property
    def type(self) -> str:
        return "function"
    
    @property
    def should_approval(self) -> bool:
        return True
    
    @property
    def description(self) -> str:
        return """
在指定路径的文件中进行搜索替换或插入操作。支持两种模式：
1. 搜索替换模式：在文件中搜索特定字符串并替换为新字符串
2. 插入模式：在指定行号位置插入新内容

使用前必须先读取文件了解其内容和结构。

搜索替换模式要求：
- old_string必须在文件中唯一存在
- 包含足够的上下文（前后3-5行）确保唯一性
- 精确匹配所有空白字符和缩进

插入模式要求：
- 设置old_string为空字符串
- 通过line_number参数指定插入位置
- new_string为要插入的内容"""
    
    def display(self, **kwargs) -> str:
        return "编辑文件"
    
    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要编辑的文件路径，包括文件名和扩展名。"
                },
                "old_string": {
                    "type": "string",
                    "description": "要替换的文本（必须在文件中唯一存在，精确匹配所有空白字符和缩进）。插入模式时设置为空字符串。"
                },
                "new_string": {
                    "type": "string",
                    "description": "替换后的新文本或要插入的内容。"
                },
                "line_number": {
                    "type": "integer",
                    "description": "插入模式时的行号（从1开始）。仅在old_string为空字符串时使用。"
                }
            },
            "required": ["path", "old_string", "new_string"]
        }
    
    @property
    def examples(self):
        return {
            "搜索替换文本": {
                "type": "function",
                "name": "edit_file",
                "arguments": {
                    "path": "/path/to/file.py",
                    "old_string": "def old_function():\n    pass",
                    "new_string": "def new_function():\n    return True"
                }
            },
            "在指定行插入内容": {
                "type": "function",
                "name": "edit_file",
                "arguments": {
                    "path": "/path/to/file.py",
                    "old_string": "",
                    "new_string": "# 这是新插入的注释",
                    "line_number": 10
                }
            }
        }

    def do_run(self, path: str, old_string: str, new_string: str, line_number: Optional[int] = None, **kwargs) -> str:
        """执行文件编辑操作，支持搜索替换和插入模式"""
        
        # 插入模式：old_string为空字符串
        if old_string == "":
            if line_number is None:
                raise ToolParameterError("插入模式需要指定line_number参数。", self.name)
            
            if not os.path.exists(path):
                raise ToolParameterError(f"文件未找到：{path}。请确保文件存在。", self.name)
            if not os.path.isfile(path):
                raise ToolParameterError(f"{path} 不是一个文件。请确保路径指向一个文件。", self.name)
            
            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            except UnicodeDecodeError:
                try:
                    with open(path, "r", encoding="gbk") as f:
                        lines = f.readlines()
                except UnicodeDecodeError:
                    raise ToolParameterError(f"无法读取文件 {path}，编码格式不支持。", self.name)
            
            total_lines = len(lines)
            if line_number < 1 or line_number > total_lines + 1:
                raise ToolParameterError(f"行号必须在 1 到 {total_lines + 1} 之间。", self.name)
            
            # 在指定行号插入内容
            if not new_string.endswith('\n'):
                new_string += '\n'
            lines.insert(line_number - 1, new_string)
            
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            
            return f"成功在 {path} 的第 {line_number} 行插入内容。"
        
        # 搜索替换模式：old_string不为空
        else:
            if not os.path.exists(path):
                raise ToolParameterError(f"文件未找到：{path}。请确保文件存在。", self.name)
            if not os.path.isfile(path):
                raise ToolParameterError(f"{path} 不是一个文件。请确保路径指向一个文件。", self.name)
            
            try:
                with open(path, "r", encoding="utf-8") as f:
                    file_content = f.read()
            except UnicodeDecodeError:
                try:
                    with open(path, "r", encoding="gbk") as f:
                        file_content = f.read()
                except UnicodeDecodeError:
                    raise ToolParameterError(f"无法读取文件 {path}，编码格式不支持。", self.name)
            
            # 检查匹配次数
            matches = re.findall(re.escape(old_string), file_content)
            if len(matches) == 0:
                raise ToolParameterError(f"在 {path} 中未找到 '{old_string}'。请确保old_string正确。", self.name)
            if len(matches) != 1:
                raise ToolParameterError(f"在 {path} 中找到 {len(matches)} 个 '{old_string}' 实例。请确保old_string唯一存在。", self.name)
            
            # 执行替换
            file_content = file_content.replace(old_string, new_string)
            with open(path, "w", encoding="utf-8") as f:
                f.write(file_content)
            
            return f"成功在 {path} 中将内容替换。"
