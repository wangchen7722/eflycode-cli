from typing import Any, Dict, Optional, Literal, List, Required
from typing_extensions import TypedDict


class ToolFunctionParametersSchema(TypedDict, total=False):
    """工具函数参数的schema定义"""
    type: Required[str]
    properties: Required[Dict[str, Dict[str, Any]]]
    required: Required[Optional[List[str]]]


class ToolFunctionSchema(TypedDict, total=False):
    """工具函数的schema定义"""
    name: Required[str]
    description: Required[str]
    parameters: Required[ToolFunctionParametersSchema]


class ToolSchema(TypedDict, total=False):
    """工具的schema定义"""
    type: Required[Literal["function"]]
    function: Required[ToolFunctionSchema]


class ToolCallSchema(TypedDict, total=False):
    """工具的schema定义"""
    type: Required[Literal["function", "memory"]]
    name: Required[str]
    arguments: Required[Dict[str, Any]]


class ToolError(Exception):
    """工具相关错误的基类"""

    def __init__(self, message: str, tool_name: str = None, error_details: Any = None):
        """
        初始化工具错误

        Args:
            message: 错误消息
            tool_name: 相关的工具名称
            error_details: 详细的错误信息
        """
        super().__init__(message)
        self.tool_name = tool_name
        self.error_details = error_details
        self.message = message


class ToolParameterError(ToolError):
    """工具参数错误，包括传参错误、参数类型校验错误等"""

    def __str__(self):
        if self.tool_name:
            return f"工具 '{self.tool_name}' 参数错误: {self.message}"
        return f"工具参数错误: {self.message}"


class ToolExecutionError(ToolError):
    """工具执行过程中的错误"""

    def __str__(self):
        if self.tool_name:
            return f"工具 '{self.tool_name}' 执行失败: {self.message}"
        return f"工具执行失败: {self.message}"
