import os.path
import re
from echo.tools.base_tool import BaseTool


class ReadFileTool(BaseTool):
    """读取文件工具类"""
    NAME = "read_file"
    DESCRIPTION = """
    Request to read the contents of a file at the specified path. 
    Use this when you need to examine the contents of an existing file you do not know the contents of, for example to analyze code, review text files, or extract information from configuration files. 
    The output includes line numbers prefixed to each line (e.g. "1 | const x = 1")
    """.replace("\n", "")
    PARAMETERS = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path of the file to read",
            }
        },
        "required": ["path"],
    }
    EXAMPLES = {
        "Read the contents of /path/to/file": {
            "type": "function",
            "name": "read_file",
            "arguments": {
                "path": "/path/to/file"
            }
        }
    }

    def run(self, path: str, **kwargs) -> str:
        """执行读取文件的操作"""
        if not os.path.exists(path):
            return f"ERROR: File not found at {path}. Please ensure the file exists."
        if not os.path.isfile(path):
            return f"ERROR: {path} is not a file. Please ensure the path points to a file."
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        line_digit_count = len(str(len(lines)))
        return f"Successfully read file's content ({path}):\n" + "".join([f"{i + 1:>{line_digit_count}} | {line}" for i, line in enumerate(lines)])


class EditFileWithReplace(BaseTool):
    """搜索替换工具类"""
    NAME = "edit_file_with_replace"
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
            "name": "edit_file_with_replace",
            "arguments": {
                "path": "/path/to/file",
                "old_string": "foo",
                "new_string": "bar"
            }
        }
    }

    def run(self, path: str, old_string: str, new_string: str, **kwargs) -> str:
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


if __name__ == "__main__":
    print(ReadFileTool().run(r"D:\Codes\Python\echo\requirements.txt"))
    print(EditFileWithReplace().run(r"D:\Codes\Python\echo\temp_file.txt", "TypedDict", "TypedDict1"))
