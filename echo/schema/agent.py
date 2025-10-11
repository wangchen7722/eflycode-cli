from enum import Enum
from typing import Any, Optional, Sequence, List, Dict
from pydantic import BaseModel

from echo.schema.llm import ToolCall, Usage, Message


class AgentResponseChunkType(Enum):
    """Agent响应块类型枚举"""
    TEXT = "text"
    TOOL_CALL = "tool_call"
    DONE = "done"

    def __str__(self):
        return self.value

    def __repr__(self):
        return self.value


class AgentResponseChunk(BaseModel):
    """Agent返回结果的流式输出类，用于处理大语言模型的流式响应

    Attributes:
        type (AgentResponseChunkType): 当前chunk的类型
        content (Optional[str]): 当前chunk的文本内容
            示例: "这是一段生成的文本"
        finish_reason (Optional[str]): 当前chunk的结束原因
            示例: "stop", "length", "tool_calls", "content_filter", "function_call"
        tool_calls (Optional[List[ToolCall]]): 当前chunk中包含的工具调用
            示例: [{"name": "search", "arguments": {"query": "搜索内容"}}]
        usage (Usage): 当前chunk的token使用统计
            示例: {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        metadata (Optional[Dict[str, Any]]): 响应的元数据信息
    """

    type: AgentResponseChunkType
    content: str
    finish_reason: Optional[str]
    tool_calls: Optional[List[ToolCall]]
    usage: Optional[Usage]
    metadata: Optional[Dict[str, Any]] = None


class AgentResponse(BaseModel):
    """大模型调用的返回结果类，包含完整的响应内容和元数据信息

    Attributes:
        messages (List[Message]): 智能体请求消息列表
        content (Optional[str]): 完整的响应文本内容
            示例: "这是完整的响应文本"
        finish_reason (Optional[str]): 响应结束的原因
            示例: "stop", "length", "tool_calls", "content_filter", "function_call"
        tool_calls (Optional[List[ToolCall]]): 响应中包含的所有工具调用
            示例: [{"name": "search", "arguments": {"query": "搜索内容"}}]
        usage (Usage): 完整响应的token使用统计
            示例: {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300}
        metadata (Optional[Dict[str, Any]]): 响应的元数据信息
    """
    messages: List[Message]
    content: Optional[str]
    finish_reason: Optional[str]
    tool_calls: Optional[List[ToolCall]]
    usage: Optional[Usage]
    metadata: Optional[Dict[str, Any]] = None


class ToolCallResponse(BaseModel):
    """工具调用响应类，用于表示工具调用的执行结果

    Attributes:
        tool_name (str): 工具名称
        arguments (str): 工具调用的参数
        response (str): 工具执行的响应结果
    """
    tool_name: str
    arguments: str
    success: bool
    result: str
    message: str