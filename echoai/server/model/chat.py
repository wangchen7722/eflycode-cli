import json
from typing import Literal, Optional, Sequence

from pydantic import BaseModel, Field, field_validator

from echoai.server.utils.validator import validate_uuid4

# ===================================================================================
# ================================= Message Content =================================
# ===================================================================================


class ChatMessageThinkingContentModel(BaseModel):
    """
    聊天消息中的思考内容。
    """

    type: Literal["thinking"]
    """内容类型"""
    text: str = Field(..., min_length=1)
    """文本内容"""


class ChatMessageTextContentModel(BaseModel):
    """
    聊天消息中的文本内容模型。
    """

    type: Literal["text"]
    """内容类型"""
    text: str = Field(..., min_length=1)
    """文本内容"""


class ChatMessageToolCallContentModel(BaseModel):
    """
    聊天消息中的工具使用消息模型。
    """

    type: Literal["tool_call"]
    """工具调用类型"""
    id: str = Field(..., min_length=1)
    """工具调用ID，必须以 'tool-' 开头，后跟一个 UUID4 格式的字符串
    用于唯一标识该工具调用。
    """
    name: str = Field(..., min_length=1)
    """函数名称"""
    arguments: str = Field(..., min_length=1)
    """函数参数, 必须是有效的JSON字符串"""

    @field_validator("arguments")
    def arguments_must_be_valid_json(cls, v: str):
        try:
            json.loads(v)
        except json.JSONDecodeError:
            raise ValueError("Invalid arguments")
        return v

    @field_validator("id")
    def id_must_be_startwith_tool_and_endwith_uuid4(cls, v: str):
        if not v.startswith("tool-"):
            raise ValueError("Invalid id")
        if not validate_uuid4(v[5:]):
            raise ValueError("Invalid id")
        return v


class ChatMessageToolResultContentModel(BaseModel):
    """
    聊天消息中的工具结果消息模型。
    """

    type: Literal["tool_result"]
    """工具结果类型"""
    tool_call_id: str = Field(..., min_length=1)
    """工具调用ID"""
    content: str = Field(..., min_length=1)
    """工具结果内容"""

    @field_validator("tool_call_id")
    def tool_call_id_must_be_startwith_tool_and_endwith_uuid4(cls, v: str):
        if not v.startswith("tool-"):
            raise ValueError("Invalid id")
        if not validate_uuid4(v[5:]):
            raise ValueError("Invalid id")
        return v


class ChatMessageImageContentSourceModel(BaseModel):
    """
    聊天消息中图片内容的来源模型。
    """

    type: Literal["base64"]
    """图片编码类型"""
    media_type: Literal["image/jpeg", "image/png", "image/gif", "image/webp"]
    """图片媒体类型"""
    data: str = Field(..., min_length=1)
    """Base64编码的图片数据"""


class ChatMessageImageContentModel(BaseModel):
    """
    聊天消息中的图片内容模型。
    """

    type: Literal["image"]
    """内容类型"""
    source: ChatMessageImageContentSourceModel
    """图片内容来源"""


# ===========================================================================
# ================================= Message =================================
# ===========================================================================


class ChatBaseMessageModel(BaseModel):
    """
    聊天消息基础模型。
    """

    # id: Optional[str] = None
    # """消息ID"""
    name: Optional[str] = None
    """消息名称"""

    # @field_validator("id")
    # def id_must_be_uuid4(cls, v: str):
    #     if not validate_uuid4(v):
    #         raise ValueError("Invalid id")
    #     return v


class ChatUserMessageModel(ChatBaseMessageModel):
    """
    用户消息模型。
    """

    role: Literal["user"]
    """消息类型"""
    content: (
        str
        | Sequence[
            ChatMessageTextContentModel
            | ChatMessageImageContentModel
            | ChatMessageToolResultContentModel
        ]
    )
    """消息内容"""

    @field_validator("content")
    def convert_str_to_text_content(cls, v):
        if isinstance(v, str):
            return [ChatMessageTextContentModel(type="text", text=v)]
        return v


class ChatAssistantMessageModel(ChatBaseMessageModel):
    """
    助手消息模型。
    """

    role: Literal["assistant"]
    """角色类型"""
    content: Sequence[
        ChatMessageThinkingContentModel
        | ChatMessageTextContentModel
        | ChatMessageImageContentModel
        | ChatMessageToolCallContentModel
    ]
    """消息内容"""


class ChatMessageToolCallFunctionModel(BaseModel):
    """
    工具调用函数的模型。
    """

    name: str = Field(..., min_length=1)
    """函数名称"""
    arguments: str = Field(..., min_length=1)
    """函数参数"""

    @field_validator("arguments")
    def arguments_must_be_valid_json(cls, v: str):
        try:
            json.loads(v)
        except json.JSONDecodeError:
            raise ValueError("Invalid arguments")
        return v


# =================================================================================
# ================================= Message Tools =================================
# =================================================================================


class ChatToolFunctionModel(BaseModel):
    """
    工具函数的定义模型。
    """

    name: str = Field(..., min_length=1)
    """函数名称"""
    description: str = Field(..., min_length=1)
    """函数描述"""
    parameters: dict = Field(..., min_items=1)
    """函数参数"""


class ChatToolModel(BaseModel):
    """
    聊天消息中可用工具的模型。
    """

    type: Literal["function"]
    """工具类型"""
    function: ChatToolFunctionModel
    """工具函数定义"""


# ================================================================================
# ================================= Chat Request =================================
# ================================================================================


class ChatRequest(BaseModel):
    """
    聊天请求模型。
    """
    chat_id: str
    """聊天窗口的唯一标识符。
    用于在多个会话中区分不同的对话，必须是符合UUID4格式的字符串。
    """
    request_id: str
    """请求的唯一标识符。
    用于追踪和关联特定的请求-响应对，可选字段，如果提供必须是符合UUID4格式的字符串。
    """
    model: str = Field(..., min_length=1)
    """使用的AI模型标识符。
    指定要使用的语言模型，必须是非空字符串。
    """
    message: ChatUserMessageModel
    """用户发送的消息。
    包含用户的输入文本或其他内容。
    """
    tools: Optional[Sequence[ChatToolModel]] = None
    """可用工具列表。
    定义模型可以调用的外部功能或工具，用于扩展模型的能力范围。
    """

    @field_validator("chat_id")
    def chat_id_must_be_uuid4(cls, v: str):
        if not validate_uuid4(v):
            raise ValueError("Invalid chat_id")
        return v


# ================================================================================
# ================================= Chat Response ================================
# ================================================================================

class ChatResponse(BaseModel):
    """
    聊天响应模型。
    """
    message: ChatAssistantMessageModel
    """助手的响应消息。
    包含模型生成的响应文本或其他内容。
    """
    finish_reason: Optional[Literal["stop", "length"]]
    """完成原因。
    指示模型停止生成响应的原因，可选字段。
    """
    usage: Optional[dict] = None
    """使用情况统计。
    包含模型的使用情况统计信息，可选字段。
    """


class ChatChunkResponse(BaseModel):
    """
    聊天响应模型。
    """
    type: Literal[""]
    """消息类型"""
    delta: ChatAssistantMessageModel
    """助手的响应消息。
    包含模型生成的响应文本或其他内容。
    """
    finish_reason: Optional[Literal["stop", "length"]] = None
    """完成原因。
    指示模型停止生成响应的原因，可选字段。
    """
    usage: Optional[dict] = None
    """使用情况统计。
    包含模型的使用情况统计信息，可选字段。
    """


# ================================================================================
# ================================= Event Response ===============================
# ================================================================================



class ChatEventResponse(BaseModel):
    """
    事件响应模型。
    """
    type: Literal[""]