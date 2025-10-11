from typing import Any, Dict, List, Optional, Literal, Generator
from pydantic import BaseModel, Field


class ToolFunctionParameters(BaseModel):
    type: Literal["object"] = "object"
    properties: Dict[str, Any]
    required: Optional[List[str]] = None


class ToolFunction(BaseModel):
    """工具函数参数规范

    Attributes:
        name: 工具函数的名称，用于标识和调用特定的工具函数
        description: 工具函数的详细描述，说明其功能、用途和使用方法
        parameters: 工具函数的参数定义，包含参数名称、类型、描述等信息的字典
    """

    name: str
    description: str
    parameters: ToolFunctionParameters

class ToolDefinition(BaseModel):
    """工具定义

    Attributes:
        name: 工具名称
        description: 工具描述
        parameters: 工具参数
    """

    type: Literal["function"] = "function"
    function: ToolFunction


class ToolCallFunction(BaseModel):
    """工具调用信息

    Attributes:
        name: 被调用的工具函数名称
        arguments: 工具函数的参数，通常为JSON格式的字符串
    """

    name: str
    arguments: str

class DeltaToolCallFunction(BaseModel):
    """工具调用信息

    Attributes:
        name: 被调用的工具函数名称
        arguments: 工具函数的参数，通常为JSON格式的字符串
    """

    name: Optional[str] = None
    arguments: str


class ToolCall(BaseModel):
    """工具调用信息

    Attributes:
        id: 工具调用的唯一标识符
        type: 调用类型，固定为"function"
        function: 函数调用的详细信息
    """

    id: str
    type: Literal["function"]
    function: ToolCallFunction

class DeltaToolCall(BaseModel):
    """工具调用信息

    Attributes:
        id: 工具调用的唯一标识符
        type: 调用类型，固定为"function"
        function: 函数调用的详细信息
    """
    index: int
    id: Optional[str] = None
    type: Optional[Literal["function"]] = None
    function: DeltaToolCallFunction


class Message(BaseModel):
    """聊天消息格式

    Attributes:
        role: 消息发送者的角色
        reasoning_content: 推理过程的内容，用于展示决策过程
        content: 消息的主要内容
        name: 工具或函数的名称，仅在role为tool或function时使用
        tool_calls: 工具调用的列表
        tool_call_id: 工具调用的ID
    """

    role: Literal["system", "user", "assistant", "tool"]
    reasoning_content: Optional[str] = None
    content: Optional[str] = None
    name: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None

class DeltaMessage(BaseModel):
    """聊天消息格式

    Attributes:
        role: 消息发送者的角色
        reasoning_content: 推理过程的内容，用于展示决策过程
        content: 消息的主要内容
        name: 工具或函数的名称，仅在role为tool或function时使用
        tool_calls: 工具调用的列表
        tool_call_id: 工具调用的ID
    """

    role: Literal["system", "user", "assistant", "tool"]
    reasoning_content: Optional[str] = None
    content: Optional[str] = None
    name: Optional[str] = None
    tool_calls: Optional[List[DeltaToolCall]] = None

class Choice(BaseModel):
    """完成选项

    Attributes:
        index: 选项的索引号
        message: 完成的消息内容
        finish_reason: 完成的原因，如"stop"、"length"等
    """

    index: int
    message: Message
    finish_reason: Optional[str]


class Usage(BaseModel):
    """API使用量统计

    Attributes:
        prompt_tokens: 提示词消耗的token数量
        completion_tokens: 完成内容消耗的token数量
        total_tokens: 总共消耗的token数量
    """

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletion(BaseModel):
    """聊天完成响应

    Attributes:
        id: 响应的唯一标识符
        object: 对象类型，如"chat.completion"
        created: 响应创建的Unix时间戳
        model: 使用的模型名称
        choices: 完成选项的列表
        usage: API使用量统计信息
    """

    id: str
    object: str
    created: int
    model: str
    choices: List[Choice]
    usage: Usage

    def __str__(self) -> str:
        if self.choices:
            message = self.choices[0].message
            if message.role == "assistant":
                tool_call_str = ""
                # 工具调用
                if message.tool_calls:
                    tool_calls = message.tool_calls
                    tool_call_str = "\n".join(
                        [
                            f"Tool Call ID: {tool_call.id}\nTool Call: {tool_call.function.name}\nTool Arguments: {tool_call.function.arguments}"
                            for tool_call in tool_calls
                        ]
                    )
                if message.content == None or message.content.strip() == "":
                    return f"{message.role}: \n{tool_call_str}"
                return f"{message.role}: {message.content}\n\n{tool_call_str}"
            elif message.role == "tool":
                # 工具执行结果
                tool_call_str = f"Tool Call ID: {message.tool_call_id}\nTool Result: {message.content}"
                return f"{message.role}: {tool_call_str}"
            else:
                return f"{message.role}: {message.content}"
        else:
            return "No choices available"

class StreamChoice(BaseModel):
    """流式响应的选项格式

    Attributes:
        index: 选项的索引号
        delta: 增量的消息内容
        finish_reason: 完成的原因
    """

    index: int
    delta: DeltaMessage
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    """流式聊天完成响应

    Attributes:
        id: 响应的唯一标识符
        object: 对象类型
        created: 响应创建的Unix时间戳
        model: 使用的模型名称
        choices: 流式完成选项的列表
        usage: API使用量统计信息
    """

    id: str
    object: str
    created: int
    model: str
    choices: List[StreamChoice]
    usage: Optional[Usage] = None


class LLMConfig(BaseModel):
    """模型配置项"""

    model: str = Field(description="模型ID")
    name: str = Field(description="模型名称")
    provider: str = Field(description="模型提供方")
    api_key: str = Field(description="API密钥")
    base_url: str = Field(description="基础URL")
    max_context_length: int = Field(description="最大上下文长度")
    supports_native_tool_call: bool = Field(
        default=False, description="是否支持原生函数调用"
    )
    temperature: float = Field(default=0.2, description="温度")


class LLMCapability(BaseModel):
    """模型能力"""
    supports_native_tool_call: bool = Field(
        default=False, description="是否支持原生函数调用"
    )


class LLMRequestContext(BaseModel):
    """模型请求上下文"""
    capability: LLMCapability = Field(description="模型能力")


class LLMRequest(BaseModel):
    model: str = Field(description="模型ID")
    messages: List[Message] = Field(description="消息列表")
    tools: Optional[List[ToolDefinition]] = Field(default=None, description="工具列表")
    tool_choice: Optional[Dict[str, Any]] = Field(default=None, description="工具选择")
    generate_config: Optional[Dict[str, Any]] = Field(
        default=None, description="生成配置"
    )
    context: LLMRequestContext = Field(description="模型请求上下文")


class LLMPrompt(BaseModel):
    """模型提示"""
    messages: List[Message] = Field(description="消息列表")
    tools: Optional[List[ToolDefinition]] = Field(default=None, description="工具列表")
    tool_choice: Optional[Dict[str, Any]] = Field(default=None, description="工具选择")
    generate_config: Optional[Dict[str, Any]] = Field(
        default=None, description="生成配置"
    )

LLMCallResponse = ChatCompletion
LLMStreamResponse = Generator[ChatCompletionChunk, None, None]
