from typing import Any, Dict, List, Optional, Literal, Required, NotRequired
from typing_extensions import TypedDict


class ToolFunction(TypedDict, total=False):
    """工具函数参数规范
    
    Attributes:
        name (str): 工具函数的名称，用于标识和调用特定的工具函数
        description (str): 工具函数的详细描述，说明其功能、用途和使用方法
        parameters (Dict): 工具函数的参数定义，包含参数名称、类型、描述等信息的字典
    """
    name: Required[str]
    description: Required[str]
    parameters: Required[Dict[str, Any]]


class ToolCallFunction(TypedDict, total=False):
    """工具调用信息
    
    Attributes:
        name (str): 被调用的工具函数名称
        arguments (str): 工具函数的参数，通常为JSON格式的字符串
    """
    name: Required[str]
    arguments: Required[str]


class ToolCall(TypedDict, total=False):
    """工具调用信息
    
    Attributes:
        id (str): 工具调用的唯一标识符
        type (Literal["function"]): 调用类型，固定为"function"
        function (ToolCallFunction): 函数调用的详细信息
    """
    id: Required[str]  # 调用ID
    type: Required[Literal["function"]]
    function: Required[ToolCallFunction]


class Message(TypedDict, total=False):
    """聊天消息格式
    
    Attributes:
        role (Literal["system", "user", "assistant", "tool"]): 消息发送者的角色
        reasoning_content (Optional[str]): 推理过程的内容，用于展示决策过程
        content (Optional[str]): 消息的主要内容
        name (Optional[str]): 工具或函数的名称，仅在role为tool或function时使用
        tool_calls (Optional[List[ToolCall]]): 工具调用的列表
        tool_call_id (Optional[str]): 工具调用的ID
    """
    role: Required[Literal["system", "user", "assistant", "tool"]]
    reasoning_content: NotRequired[Optional[str]]
    content: NotRequired[Optional[str]]
    name: NotRequired[Optional[str]]
    tool_calls: NotRequired[Optional[List[ToolCall]]]
    tool_call_id: NotRequired[Optional[str]]


class Choice(TypedDict, total=False):
    """完成选项
    
    Attributes:
        index (int): 选项的索引号
        message (Message): 完成的消息内容
        finish_reason (Optional[str]): 完成的原因，如"stop"、"length"等
    """
    index: Required[int]
    message: Required[Message]
    finish_reason: Required[Optional[str]]


class Usage(TypedDict, total=False):
    """API使用量统计
    
    Attributes:
        prompt_tokens (int): 提示词消耗的token数量
        completion_tokens (int): 完成内容消耗的token数量
        total_tokens (int): 总共消耗的token数量
    """
    prompt_tokens: Required[int]
    completion_tokens: Required[int]
    total_tokens: Required[int]


class ChatCompletion(TypedDict, total=False):
    """聊天完成响应
    
    Attributes:
        id (str): 响应的唯一标识符
        object (str): 对象类型，如"chat.completion"
        created (int): 响应创建的Unix时间戳
        model (str): 使用的模型名称
        choices (List[Choice]): 完成选项的列表
        usage (Usage): API使用量统计信息
    """
    id: Required[str]
    object: Required[str]
    created: Required[int]
    model: Required[str]
    choices: Required[List[Choice]]
    usage: Required[Usage]


class StreamChoice(TypedDict, total=False):
    """流式响应的选项格式
    
    Attributes:
        index (int): 选项的索引号
        delta (Message): 增量的消息内容
        finish_reason (Optional[str]): 完成的原因
    """
    index: Required[int]
    delta: Required[Message]
    finish_reason: Required[Optional[str]]


class ChatCompletionChunk(TypedDict, total=False):
    """流式聊天完成响应
    
    Attributes:
        id (str): 响应的唯一标识符
        object (str): 对象类型
        created (int): 响应创建的Unix时间戳
        model (str): 使用的模型名称
        choices (List[StreamChoice]): 流式完成选项的列表
    """
    id: Required[str]
    object: Required[str]
    created: Required[int]
    model: Required[str]
    choices: Required[List[StreamChoice]]
    usage: NotRequired[Optional[Usage]]
