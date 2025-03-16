from typing import Dict, List, Optional, Union, Literal
from pydantic import BaseModel, Field

class Message(BaseModel):
    """聊天消息格式"""
    role: Literal["system", "user", "assistant", "tool"] = Field(..., description="消息角色")
    reasoning_content: Optional[str] = Field(None, description="推理内容")
    content: Optional[str] = Field(None, description="消息内容")
    name: Optional[str] = Field(None, description="工具/函数名称，仅在role为tool或function时使用")
    tool_calls: Optional[List[Dict]] = Field(None, description="工具调用信息")
    tool_call_id: Optional[str] = Field(None, description="工具调用ID")

class Choice(BaseModel):
    """完成选项"""
    index: int = Field(..., description="选项索引")
    message: Message = Field(..., description="完成的消息")
    finish_reason: Optional[str] = Field(None, description="完成原因")

class Usage(BaseModel):
    """API使用量统计"""
    prompt_tokens: int = Field(..., description="提示词token数")
    completion_tokens: int = Field(..., description="完成内容token数")
    total_tokens: int = Field(..., description="总token数")

class ChatCompletion(BaseModel):
    """聊天完成响应"""
    id: str = Field(..., description="响应ID")
    object: str = Field(..., description="对象类型")
    created: int = Field(..., description="创建时间戳")
    model: str = Field(..., description="使用的模型")
    choices: List[Choice] = Field(..., description="完成选项列表")
    usage: Usage = Field(..., description="使用量统计")

class StreamChoice(BaseModel):
    """流式响应的选项格式"""
    index: int = Field(..., description="选项索引")
    delta: Message = Field(..., description="增量消息内容")
    finish_reason: Optional[str] = Field(None, description="完成原因")

class ChatCompletionChunk(BaseModel):
    """流式聊天完成响应"""
    id: str = Field(..., description="响应ID")
    object: str = Field(..., description="对象类型")
    created: int = Field(..., description="创建时间戳")
    model: str = Field(..., description="使用的模型")
    choices: List[StreamChoice] = Field(..., description="流式完成选项列表")

class ToolFunction(BaseModel):
    """工具函数参数规范"""
    name: str = Field(..., description="函数名称")
    description: str = Field(..., description="函数描述")
    parameters: Dict = Field(..., description="函数参数定义")

class ToolCall(BaseModel):
    """工具调用信息"""
    id: str = Field(..., description="调用ID")
    type: Literal["function"] = Field(..., description="调用类型")
    function: ToolFunction = Field(..., description="函数调用信息")