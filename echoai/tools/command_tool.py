import os
import subprocess
import traceback
from typing import Optional

from echoai.tools.base_tool import BaseTool


class ExecuteCommandTool(BaseTool):
    """执行命令的工具"""

    NAME = "execute_command"
    TYPE = "function"
    IS_APPROVAL = True
    DESCRIPTION = """
    Request to execute a CLI command on the system. Use this when you need to perform system operations or run specific commands to accomplish any step in the user's task. 
    You must tailor your command to the user's system and provide a clear explanation of what the command does. 
    For command chaining, use the appropriate chaining syntax for the user's shell. Prefer to execute complex CLI commands over creating executable scripts, as they are more flexible and easier to run. 
    Prefer relative commands and paths that avoid location sensitivity for terminal consistency, e.g: `python main.py`, or `go test ./cmd/front --config ./cmd/front/config.yml`. 
    IMPORTANT: You MUST avoid using text-based search commands like `grep` or `find`. Instead, use file-system_related tool calls.
    IMPORTANT: Prefer to using the provided tools over commands. For example, if you need to create a file, use the create_file tool instead of executing a command like `touch file.txt`.
    """
    DISPLAY = "{agent_name} want to execute this command"
    PARAMETERS = {
        ""
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The CLI command to execute. This should be valid for the current operating system. Ensure the command is properly formatted and does not contain any harmful instructions.",
            },
            "cwd": {
                "type": "string",
                "description": f"The working directory to execute the command in default ({os.getcwd()}).",
            },
            "timeout": {
                "type": "integer",
                "description": "The maximum time in seconds to wait for the command to complete. If the command takes longer than this time, the execution will be stopped and an error will be returned.",
            },
        },
        "required": ["command"],
    }
    EXAMPLES = {
        "Requesting to launch a frontend server": {
            "type": "function",
            "name": "execute_command",
            "arguments": {
                "command": "npm start",
            }
        },
        "Requesting to execute pip install -r requirements.txt": {
            "type": "function",
            "name": "execute_command",
            "arguments": {
                "command": "pip install -r requirements.txt",
            }
        }
    }

    def do_run(self, command: str, cwd: Optional[str] = None, timeout: Optional[int] = None) -> str:
        """执行命令"""
        if cwd:
            work_dir = os.path.abspath(cwd)
            if not os.path.exists(work_dir):
                return f"Error: The specified directory ({cwd}) does not exist, current directory is {os.getcwd()}"
            if not os.path.isdir(work_dir):
                return f"Error: The specified path ({cwd}) is not a directory"
        else:
            work_dir = os.getcwd()
        try:
            process = subprocess.run(
                command,
                cwd=work_dir,  # 设置工作目录
                capture_output=True,  # 捕获标准输出和标准错误
                text=True,  # 以文本模式处理输出
                timeout=timeout,  # 设置超时时间
                check=True,  # 若命令返回非零退出码，则引发 CalledProcessError 异常
                shell=True  # 使用 shell 执行命令
            )
            output = ""
            code = process.returncode
            output += f"code: {code}\n"
            stdout = process.stdout
            if stdout.strip() == "":
                output += "stdout: No output\n"
            else:
                output += f"stdout:\n{stdout}\n"
            stderr = process.stderr
            if stderr.strip() == "":
                output += "stderr: No output"
            else:
                output += f"stderr:\n{stderr}"
            return f"Command executed successfully in {work_dir}\n" + output
        except subprocess.TimeoutExpired as e:
            # 判断是否是超时异常，如果是一个常驻程序，那么可以忽略这个异常
            stdout = e.stdout
            stderr = e.stderr
            return f"Error: Command execution timed out after {timeout} seconds\n" + f"stdout:\n{stdout}\n" + f"stderr:\n{stderr}"
        except subprocess.CalledProcessError as e:
            output = ""
            code = e.returncode
            output += f"code: {code}\n"
            stdout = e.stdout
            if stdout.strip() == "":
                output += "stdout: No output\n"
            else:
                output += f"stdout:\n{stdout}\n"
            stderr = e.stderr
            if stderr.strip() == "":
                output += "stderr: No output"
            else:
                output += f"stderr:\n{stderr}"
            return f"Error: Command execution failed in {work_dir}\n" + output
        except Exception as e:
            details = traceback.format_exc()
            return f"Error: execute command failed: {e}\ndetails:\n{details}"
