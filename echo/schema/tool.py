from typing import Any, Dict, Optional, Literal, List
from typing_extensions import TypedDict
from pydantic import BaseModel


class ToolFunctionParametersSchema(TypedDict, total=False):
    """工具函数参数的schema定义
    
    Attributes:
        type: 参数类型
        description: 参数描述
        required: 是否为必需参数
    """
    type: str
    description: str
    required: bool


class ToolFunctionSchema(BaseModel):
    """工具函数的schema定义
    
    Attributes:
        name: 工具函数名称
        description: 工具函数描述
        parameters: 工具函数参数schema
    """
    name: str
    description: str
    parameters: Dict[str, ToolFunctionParametersSchema]


class ToolSchema(BaseModel):
    """工具的schema定义
    
    Attributes:
        type: 工具类型
        function: 工具函数schema
    """
    type: Literal["function"]
    function: ToolFunctionSchema


class ToolCallSchema(BaseModel):
    """工具调用的schema定义
    
    Attributes:
        type: 调用类型
        name: 工具名称
        arguments: 调用参数
    """
    type: Literal["function", "memory"]
    name: str
    arguments: Dict[str, Any]


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
