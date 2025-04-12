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