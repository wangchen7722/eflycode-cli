from typing import Dict, List, Optional, Generator
from enum import Enum
from pydantic import BaseModel, Field

from prompt.prompt_loader import PromptLoader
from llms.llm_engine import LLMEngine
from llms.schema import ChatCompletion, ChatCompletionChunk, Usage, ToolCall
from utils.system import system_info

class AgentCapability(Enum):
    """Agent能力枚举类"""
    USE_TOOL = "use_tool"
    USE_SHELL = "use_shell"
    USE_MCP = "use_mcp"
    
class AgentResponseMetadata(BaseModel):
    """Agent返回结果的元数据类"""
    request_context: Dict = Field(..., description="请求上下文")
    raw_response: ChatCompletion | List[ChatCompletionChunk] = Field(..., description="原始响应")

class AgentResponse(BaseModel):
    """大模型调用的返回结果类"""
    content: str = ""
    finish_reason: str = Field(..., description="结束原因")
    tool_calls: Optional[List[ToolCall]] = Field(None, description="工具调用列表")
    usage: Usage = Field(..., description="使用量统计")
    metadata: AgentResponseMetadata
    
    is_streaming: bool = False
    _stream_generator: Optional[Generator[str, None, None]] = None
    
    @property
    def prompt_tokens(self) -> int:
        """获取prompt的token数量"""
        return self.usage.prompt_tokens

    @property
    def completion_tokens(self) -> int:
        """获取completion的token数量"""
        return self.usage.completion_tokens

    @property
    def total_tokens(self) -> int:
        """获取总token数量"""
        return self.usage.total_tokens
    
    def set_stream_generator(self, generator: Generator[str, None, None]):
        """设置流式输出生成器
        Args:
            generator: 流式输出的生成器
        """
        self.is_streaming = True
        self._stream_generator = generator
        
    def stream(self) -> Generator[str, None, None]:
        """获取流式输出的生成器"""
        if not self.is_streaming or not self._stream_generator:
            yield self.content
            return

        for chunk in self._stream_generator:
            yield chunk

class Agent:
    """基础智能体类"""
    ROLE = "base"
    DESCRIPTION = "一个通用对话智能助手"
    
    def __init__(
        self, 
        name: str, 
        llm_engine: LLMEngine, 
        capabilities: Optional[List[AgentCapability]] = None,
        description: Optional[str] = None,
        **kwargs
    ):
        """
        初始化智能体
        Args:
            name: 智能体名称
            llm_engine: 语言模型引擎
            capabilities: 智能体能力列表
            description: 智能体描述
            **kwargs: 其他参数
        """
        self.name = name
        self.llm_engine = llm_engine
        self.capabilities = capabilities or []
        self.description = description or self.DESCRIPTION
        self.kwargs = kwargs
        self.messages = []
        
    @property
    def role(self):
        return self.ROLE
    
    def system_prompt(self) -> str:
        """渲染系统提示词"""
        return PromptLoader.get_instance().render_template(
            f"{self.role}/system.prompt",
            name=self.name,
            role=self.role,
            capabilities=self.capabilities,
            system_info=system_info()
        )
        