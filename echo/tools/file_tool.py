import os
from pathlib import Path
import re
from typing import Optional
import glob
from echo.tools.base_tool import BaseTool


class ListFilesTool(BaseTool):
    """列出文件工具类"""
    NAME = "list_files"
    TYPE = "function"
    DESCRIPTION = """
    Request to list files and directories within the specified directory. 
    If recursive is true, it will list all files and directories recursively. 
    If recursive is false or not provided, it will only list the top-level contents. 
    Do not use this tool to confirm the existence of files you may have created, as the user will let you know if the files were created successfully or not.
    """
    DISPLAY = "{agent_name} want to list files"
    PARAMETERS = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path of the directory to list",
            },
            "recursive": {
                "type": "boolean",
                "description": "Whether to list files recursively. Use true for recursive listing, false or omit for top-level only.",
            }
        },
        "required": ["path"],
    }
    EXAMPLES = {
        "Requesting to list all files in the current directory": {
            "type": TYPE,
            "name": NAME,
            "arguments": {
                "path": ".",
                "recursive": False
            }
        }
    }

    def do_run(self, path: str, recursive: bool = False, **kwargs) -> str:
        """执行列出文件的操作"""
        if not os.path.exists(path):
            return f"ERROR: Directory not found at {path}. Please ensure the directory exists."
        if not os.path.isdir(path):
            return f"ERROR: {path} is not a directory. Please ensure the path points to a directory."
        if recursive:
            file_list = []
            for root, dirs, files in os.walk(path):
                to_removed_dirs = [
                    directory
                    for directory in dirs
                    if directory.startswith(".") or directory in ["__pycache__", "node_modules"]
                ]
                for to_removed_dir in to_removed_dirs:
                    dirs.remove(to_removed_dir)
                for file in files:
                    file_list.append(Path(os.path.join(root, file)).as_posix())
            return f"Successfully listed all files in {path} recursively:\n" + "\n".join(file_list)
        else:
            file_list = [
                Path(filepath).as_posix()
                for filepath in os.listdir(path)
            ]
            return f"Successfully listed all files in {path}:\n" + "\n".join(file_list)


class ReadFileTool(BaseTool):
    """读取文件工具类"""
    NAME = "read_file"
    TYPE = "function"
    DESCRIPTION = """
    Request to read the contents of a file at the specified path. 
    Use this when you need to examine the contents of an existing file you do not know the contents of, for example to analyze code, review text files, or extract information from configuration files. 
    The output includes line numbers prefixed to each line (e.g. "1 | const x = 1")
    """.replace("\n", "")
    DISPLAY = "{agent_name} want to read this file"
    PARAMETERS = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path of the file to read",
            },
            "start_line": {
                "type": "integer",
                "description": "The starting line number to read from (inclusive)",
            },
            "end_line": {
                "type": "integer",
                "description": "The ending line number to read to (inclusive)",
            }
        },
        "required": ["path"],
    }
    EXAMPLES = {
        "Reading an entire file": {
            "type": "function",
            "name": "read_file",
            "arguments": {
                "path": "/path/to/file"
            }
        },
        "Reading the first 1000 lines of a large log file": {
            "type": "function",
            "name": "read_file",
            "arguments": {
                "path": "/path/to/large_log_file",
                "end_line": 1000
            }
        },
        "Reading lines 500-1000 of a CSV file": {
            "type": "function",
            "name": "read_file",
            "arguments": {
                "path": "/path/to/csv_file",
                "start_line": 500,
                "end_line": 1000
            }
        },
        "Reading a specific function in a source file": {
            "type": "function",
            "name": "read_file",
            "arguments": {
                "path": "/path/to/source_file",
                "start_line": 46,
                "end_line": 68,
            }
        }
    }

    def do_run(self, path: str, start_line: Optional[int] = None, end_line: Optional[int] = None, **kwargs) -> str:
        """执行读取文件的操作"""
        if not os.path.exists(path):
            return f"ERROR: File not found at {path}. Please ensure the file exists."
        if not os.path.isfile(path):
            return f"ERROR: {path} is not a file. Please ensure the path points to a file."
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if end_line is not None:
            if end_line < 1 or end_line > len(lines):
                return f"ERROR: end_line must be between 1 and {len(lines)}. Please ensure the end_line is correct."
            lines = lines[:end_line]
        if start_line is not None:
            if start_line < 1 or start_line > len(lines):
                return f"ERROR: start_line must be between 1 and {len(lines)}. Please ensure the start_line is correct."
            lines = lines[start_line - 1:]
        line_digit_count = len(str(len(lines)))
        start_line_number = start_line or 1
        return "".join(
            [f"{str(i).rjust(line_digit_count)} | {line}" for i, line in enumerate(lines, start_line_number)])


class SearchFilesTool(BaseTool):
    """搜索文件工具类"""
    NAME = "search_files"
    TYPE = "function"
    DESCRIPTION = """
    Request to perform a regex search across files in a specified directory, providing context-rich results. 
    This tool searches for patterns or specific content across multiple files, displaying each match with encapsulating context.
    """
    DISPLAY = "{agent_name} want to search files"
    PARAMETERS = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path of the directory to search. This directory will be recursively searched.",
            },
            "regex": {
                "type": "string",
                "description": "The regular expression pattern to search for. Uses Rust regex syntax.",
            },
            "pattern": {
                "type": "string",
                "description": "Glob pattern to filter files (e.g., '*.py' for Python files). If not provided, it will search all files (*)."
            }
        },
        "required": ["path"]
    }
    EXAMPLES = {
        "Requesting to search for all .py files in the current directory": {
            "type": "function",
            "name": "search_files",
            "arguments": {
                "path": ".",
                "regex": ".*",
                "pattern": "*.py"
            }
        }
    }

    def do_run(self, path: str, regex: str, pattern: Optional[str] = None, **kwargs) -> str:
        """执行搜索文件的操作"""
        if not os.path.exists(path):
            return f"ERROR: Directory not found at {path}. Please ensure the directory exists."
        if not os.path.isdir(path):
            return f"ERROR: {path} is not a directory. Please ensure the path points to a directory."
        if pattern is None:
            pattern = "*"
        try:
            re_pattern = re.compile(regex, re.MULTILINE | re.DOTALL)
        except re.error as e:
            return f"ERROR: Invalid regular expression pattern: {e}"
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
                matches.append(f"ERROR: Failed to read file {filepath}: {e}")
                continue
            for match in re_pattern.finditer(file_content):
                # 跳过空匹配
                if match.group().strip() == "":
                    continue
                start, end = match.span()
                context_start = max(0, start - 100)
                context_end = min(len(file_content), end + 100)
                context = file_content[context_start:context_end]
                line_number = file_content.count("\n", 0, start) + 1
                matches.append((filepath, line_number, match.group(), context))
        if not matches:
            return f"No matches found for '{regex}' in {path} with pattern '{pattern}'."
        output = ""
        for match in matches:
            filepath, line_number, matched_content, context = match
            file_match = f"## filepath: {filepath}\n- line_number: {line_number}\n- matched_content: {matched_content}\n- context: {context}"
            output += file_match + "\n\n"
        return f"Successfully searched for '{regex}' in {path} with pattern '{pattern}' and found {len(matches)} matches:\n\n{output}"


class CreateFileTool(BaseTool):
    """创建文件工具类"""
    NAME = "create_file"
    TYPE = "function"
    DESCRIPTION = """
    Request to create a new file at the specified path.
    Use this when you need to create a new file, such as when you need to create a new configuration file or when you need to create a new source code file.
    If the file already exists, it will return an error.
    If the file's parent directory does not exist, it will create the parent directory automatically.
    """
    DISPLAY = "{agent_name} want to create this file"
    PARAMETERS = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path of the file to create, including the file name and extension.",
            },
            "content": {
                "type": "string",
                "description": "The content of the file to create, default is an empty string.",
            }
        },
        "required": ["path", "content"],
    }
    EXAMPLES = {
        "Requesting to create a new file": {
            "type": "function",
            "name": "create_file",
            "arguments": {
                "path": "/path/to/new_file.txt",
                "content": "This is the content of the new file."
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
                return f"ERROR: Failed to create directory at {dirpath}: {e}"
        if os.path.exists(path):
            return f"ERROR: File already exists at {path}."
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully created file at {path} with content: {content}"
        except Exception as e:
            return f"ERROR: Failed to create file at {path}: {e}"


class InsertFileTool(BaseTool):
    """插入文件工具类"""
    NAME = "insert_file"
    TYPE = "function"
    DESCRIPTION = """
    Request to insert content into a file at the specified path.
    Use this when you need to insert content into an existing file, such as when you need to insert code into a source code file.
    Remember before using this tool, you MUST read the file first to understand the content and structure of the file.
    """
    DISPLAY = "{agent_name} want to insert this file"
    PARAMETERS = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path of the file to insert content into, including the file name and extension.",
            },
            "content": {
                "type": "string",
                "description": "The content to insert into the file.",
            },
            "line_number": {
                "type": "integer",
                "description": "The line number (starting from 1) where the content should be inserted (inclusive).",
            }
        },
        "required": ["path", "content", "line_number"],
    }
    EXAMPLES = {
        "Requesting to insert content into a file": {
            "type": "function",
            "name": "insert_file",
            "arguments": {
                "path": "/path/to/file",
                "content": "This is the content to insert.",
                "line_number": 10
            }
        }
    }

    def do_run(self, path: str, content: str, line_number: int, **kwargs) -> str:
        """执行插入文件的操作"""
        if not os.path.exists(path):
            return f"ERROR: File not found at {path}. Please ensure the file exists."
        if not os.path.isfile(path):
            return f"ERROR: {path} is not a file. Please ensure the path points to a file."
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        max_line_number = max(len(lines), 1)
        if line_number < 1 or line_number > max_line_number:
            return f"ERROR: line_number must be between 1 and {max_line_number}. Please ensure the line_number is correct."
        lines.insert(line_number - 1, content + "\n")
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return f"Successfully inserted content into file at {path} at line {line_number}."


class EditFileTool(BaseTool):
    """搜索替换工具类"""
    NAME = "edit_file"
    TYPE = "function"
    DESCRIPTION = """
    Request to search and replace text in a file at the specified path.
    When you need to edit the contents of an existing file, use this tool to search for a specific string and replace it with another string.
    Before using this tool, you MUST make sure you understand the content and structure of the file.
    CRITICAL REQUIREMENTS FOR USING THIS TOOL:
    1. UNIQUENESS: The old_string MUST uniquely identify the specific instance you want to change. This means:
    - Include AT LEAST 3-5 lines of context BEFORE the change point
    - Include AT LEAST 3-5 lines of context AFTER the change point
    - Include all whitespace, indentation, and surrounding code exactly as it appears in the file
    2. SINGLE INSTANCE: This tool can only change ONE instance at a time. If you need to change multiple instances:
    - Make separate calls to this tool for each instance
    - Each call must uniquely identify its specific instance using extensive context
    3. VERIFICATION: Before using this tool:
    - Check how many instances of the target text exist in the file
    - If multiple instances exist, gather enough context to uniquely identify each one
    - Plan separate tool calls for each instance
    WARNING: If you do not follow these requirements:
    - The tool will fail if old_string matches multiple locations
    - The tool will fail if old_string doesn't match exactly (including whitespace)
    IMPORTANT: If you want to create a new file, use:
    - A new file path, including absolute file path and file name (e.g. /path/to/new_file.txt)
    - An empty old_string
    - The new content you want to write to the file as new_string
    """
    DISPLAY = "{agent_name} want to edit this file"
    PARAMETERS = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path of the file to edit or create",
            },
            "old_string": {
                "type": "string",
                "description": "The text to replace (MUST BE UNIQUE within the file, and must match the file contents exactly, including all whitespace and indentation)",
            },
            "new_string": {
                "type": "string",
                "description": "The text to replace the old_string with",
            }
        },
        "required": ["path", "old_string", "new_string"],
    }
    EXAMPLES = {
        "Replace 'foo' with 'bar' in /path/to/file": {
            "type": "function",
            "name": "edit_file",
            "arguments": {
                "path": "/path/to/file",
                "old_string": "foo",
                "new_string": "bar"
            }
        }
    }

    def do_run(self, path: str, old_string: str, new_string: str, **kwargs) -> str:
        """执行搜索替换的操作"""
        if old_string == "":
            # 说明是要创建文件
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    file_content = f.read()
                if file_content.strip() == "":
                    # 插入内容
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(new_string)
                    return f"Successfully created new file at {path}"
                return f"ERROR: File already exists at {path}. Please view the file's content and edit it."
            # 创建文件
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_string)
            return f"Successfully created new file at {path}"
        # old_string != ""
        if not os.path.exists(path):
            return f"ERROR: File not found at {path}. Please ensure the file exists."
        if not os.path.isfile(path):
            return f"ERROR: {path} is not a file. Please ensure the path points to a file."
        with open(path, "r", encoding="utf-8") as f:
            file_content = f.read()
        matches = re.findall(re.escape(old_string), file_content)
        if len(matches) == 0:
            return f"ERROR: '{old_string}' not found in {path}. Please ensure the old_string is correct."
        if len(matches) != 1:
            return f"ERROR: Found {len(matches)} instances of '{old_string}' in {path}. Please ensure the old_string is UNIQUE."
        file_content = file_content.replace(old_string, new_string)
        with open(path, "w", encoding="utf-8") as f:
            f.write(file_content)
        return f"Successfully replaced '{old_string}' with '{new_string}' in {path}"
