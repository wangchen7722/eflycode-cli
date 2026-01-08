import json
from typing import Any, Dict, List, Literal, Optional, TypeAlias, Union

from pydantic import BaseModel, Field

from eflycode.core.constants import (
    DEFAULT_MAX_CONTEXT_LENGTH,
    DEFAULT_TIMEOUT,
    DEFAULT_MAX_RETRIES,
)

# 重新导出以保持向后兼容
__all__ = [
    "DEFAULT_MAX_CONTEXT_LENGTH",
    "MessageRole",
    "ToolCallType",
    "ToolChoice",
    "ToolFunctionParameters",
    "ToolFunction",
    "ToolDefinition",
    "ToolCallFunction",
    "ToolCall",
    "DeltaToolCallFunction",
    "DeltaToolCall",
    "Message",
    "DeltaMessage",
    "Usage",
    "ChatCompletion",
    "ChatCompletionChunk",
    "LLMRequest",
    "LLMConfig",
]

MessageRole: TypeAlias = Literal["system", "user", "assistant", "tool"]
ToolCallType: TypeAlias = Literal["function"]
ToolChoice: TypeAlias = Union[Dict[str, Any], str]

class ToolFunctionParameters(BaseModel):
    type: Literal["object"] = "object"
    properties: Dict[str, Any] = Field(default_factory=dict)
    required: Optional[List[str]] = None

class ToolFunction(BaseModel):
    name: str
    description: str = ""
    parameters: ToolFunctionParameters

class ToolDefinition(BaseModel):
    type: Literal["function"] = "function"
    function: ToolFunction

class ToolCallFunction(BaseModel):
    name: str
    arguments: str = Field(default="")

    def parse_arguments(self) -> Dict[str, Any]:
        raw = (self.arguments or "").strip()
        if not raw:
            return {}
        return json.loads(raw)

    @property
    def arguments_dict(self) -> Dict[str, Any]:
        return self.parse_arguments()
        

class ToolCall(BaseModel):
    id: str
    type: ToolCallType = "function"
    function: ToolCallFunction

class DeltaToolCallFunction(BaseModel):
    name: Optional[str] = None
    arguments: Optional[str] = None

class DeltaToolCall(BaseModel):
    index: int
    id: Optional[str] = None
    type: Optional[ToolCallType] = None
    function: Optional[DeltaToolCallFunction] = None

class Message(BaseModel):
    role: MessageRole
    reasoning_content: Optional[str] = None
    # TODO: 添加 ContentPart
    content: Optional[Union[str]] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None

class DeltaMessage(BaseModel):
    role: Optional[MessageRole] = None
    reasoning_content: Optional[str] = None
    content: Optional[Union[str]] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[DeltaToolCall]] = None

class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    
class ChatCompletion(BaseModel):
    id: str
    object: Literal["chat.completion"]
    created: int
    model: str
    message: Message
    finish_reason: Optional[str] = None
    usage: Optional[Usage] = None

class ChatCompletionChunk(BaseModel):
    id: str
    object: Literal["chat.completion.chunk"]
    created: int
    model: str
    delta: DeltaMessage
    finish_reason: Optional[str] = None
    usage: Optional[Usage] = None

class LLMRequest(BaseModel):
    model: str
    messages: List[Message]
    tools: Optional[List[ToolDefinition]] = None
    generate_config: Optional[Dict[str, Any]] = None

class LLMConfig(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: float = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None