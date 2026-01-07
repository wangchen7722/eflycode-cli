import json
import shlex
import subprocess
from pathlib import Path
from typing import Annotated, Optional

from eflycode.core.config.config_manager import resolve_workspace_dir
from eflycode.core.llm.protocol import ToolFunctionParameters
from eflycode.core.tool.base import BaseTool, ToolType
from eflycode.core.tool.errors import ToolExecutionError


# 命令白名单
COMMAND_WHITELIST = {
    # 文件操作
    "ls",
    "cat",
    "grep",
    "find",
    "head",
    "tail",
    "wc",
    "sort",
    "uniq",
    # 版本控制
    "git",
    # Python 相关
    "python",
    "python3",
    "pip",
    "pip3",
    # 系统工具
    "pwd",
    "cd",
    "echo",
    "which",
    "env",
    # 构建工具
    "make",
    "npm",
    "yarn",
}


def _parse_command(command: str) -> str:
    """解析命令字符串，提取命令名

    Args:
        command: 命令字符串

    Returns:
        str: 命令名（第一个单词）

    Raises:
        ToolExecutionError: 如果命令为空或无法解析
    """
    if not command or not command.strip():
        raise ToolExecutionError(
            message="命令不能为空",
            tool_name="execute_command",
        )
    
    try:
        # 使用 shlex.split 安全地分割命令
        parts = shlex.split(command.strip())
        if not parts:
            raise ToolExecutionError(
                message="无法解析命令",
                tool_name="execute_command",
            )
        return parts[0]
    except ValueError as e:
        raise ToolExecutionError(
            message=f"命令解析失败: {str(e)}",
            tool_name="execute_command",
        ) from e


def _check_command_allowed(command_name: str) -> None:
    """检查命令是否在白名单中

    Args:
        command_name: 命令名

    Raises:
        ToolExecutionError: 如果命令不在白名单中
    """
    if command_name not in COMMAND_WHITELIST:
        raise ToolExecutionError(
            message=f"命令 '{command_name}' 不在允许列表中。允许的命令: {', '.join(sorted(COMMAND_WHITELIST))}",
            tool_name="execute_command",
        )


def _get_workspace_dir() -> Path:
    """获取项目根目录

    Returns:
        Path: 项目根目录，如果无法获取则返回当前工作目录
    """
    return resolve_workspace_dir()


def _validate_workdir(workdir: Optional[str]) -> Path:
    """验证并返回工作目录

    Args:
        workdir: 工作目录路径，如果为 None 则使用项目根目录

    Returns:
        Path: 验证后的工作目录路径

    Raises:
        ToolExecutionError: 如果工作目录不存在或不是目录
    """
    if workdir:
        workdir_path = Path(workdir).resolve()
        if not workdir_path.exists():
            raise ToolExecutionError(
                message=f"工作目录不存在: {workdir}",
                tool_name="execute_command",
            )
        if not workdir_path.is_dir():
            raise ToolExecutionError(
                message=f"工作目录不是目录: {workdir}",
                tool_name="execute_command",
            )
        return workdir_path
    else:
        return _get_workspace_dir()


class ExecuteCommandTool(BaseTool):
    """执行 Shell 命令工具

    用于执行 Shell 命令，支持指定工作目录和超时时间。
    只允许执行白名单中的命令，确保安全性。
    """

    @property
    def name(self) -> str:
        return "execute_command"

    @property
    def type(self) -> str:
        return ToolType.FUNCTION

    @property
    def permission(self) -> str:
        return "read"

    @property
    def description(self) -> str:
        return (
            "执行 Shell 命令工具。用于执行系统命令，如文件操作、版本控制、构建等。"
            "只允许执行白名单中的命令，包括: ls, cat, grep, find, git, python, pip, make, npm, yarn 等。"
            "命令会在指定的工作目录中执行，可以设置超时时间。"
            "返回命令的标准输出、标准错误和退出码。"
        )

    @property
    def parameters(self) -> ToolFunctionParameters:
        return ToolFunctionParameters(
            type="object",
            properties={
                "command": {
                    "type": "string",
                    "description": "要执行的 Shell 命令字符串",
                },
                "workdir": {
                    "type": "string",
                    "description": "工作目录，如果不提供则使用项目根目录",
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时时间（秒），默认 60 秒",
                    "minimum": 1,
                    "maximum": 3600,
                },
            },
            required=["command"],
        )

    def do_run(
        self,
        command: Annotated[str, "要执行的 Shell 命令字符串"],
        workdir: Annotated[Optional[str], "工作目录，如果不提供则使用项目根目录"] = None,
        timeout: Annotated[Optional[int], "超时时间（秒），默认 60 秒"] = None,
    ) -> str:
        """执行 Shell 命令

        Args:
            command: 要执行的 Shell 命令字符串
            workdir: 工作目录，如果不提供则使用项目根目录
            timeout: 超时时间（秒），默认 60 秒

        Returns:
            str: JSON 格式字符串，包含 stdout、stderr、exit_code 和 success

        Raises:
            ToolExecutionError: 如果命令不在白名单中、工作目录无效或执行失败
        """
        # 解析命令并检查白名单
        command_name = _parse_command(command)
        _check_command_allowed(command_name)

        # 验证工作目录
        workdir_path = _validate_workdir(workdir)

        # 设置默认超时时间
        if timeout is None:
            timeout = 60

        try:
            # 执行命令
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(workdir_path),
                timeout=timeout,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            # 构建返回结果
            output = {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
                "success": result.returncode == 0,
            }

            return json.dumps(output, ensure_ascii=False)

        except subprocess.TimeoutExpired:
            raise ToolExecutionError(
                message=f"命令执行超时（超过 {timeout} 秒）: {command}",
                tool_name="execute_command",
            )
        except Exception as e:
            raise ToolExecutionError(
                message=f"命令执行失败: {str(e)}",
                tool_name="execute_command",
                error_details=e,
            ) from e

