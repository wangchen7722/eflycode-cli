from typing import Dict, List, Optional, Generator, TypedDict, Any
from enum import Enum
from pydantic import BaseModel, Field

from echo.prompt.prompt_loader import PromptLoader
from echo.llms.llm_engine import LLMEngine
from echo.llms.schema import ChatCompletion, ChatCompletionChunk, Usage, ToolCall
from echo.utils.system import system_info
from echo.memory import AgentMemory, MemoryType


class AgentCapability(Enum):
    """Agent能力枚举类"""
    USE_MEMORY = "use_memory"
    USE_TOOL = "use_tool"
    USE_SHELL = "use_shell"
    USE_MCP = "use_mcp"


class AgentResponseMetadata(BaseModel):
    """Agent返回结果的元数据类"""
    request_context: Dict = Field(..., description="请求上下文")

class AgentResponseChunk(BaseModel):
    """Agent返回结果的流式输出类"""
    content: Optional[str] = Field(..., description="响应内容")
    finish_reason: Optional[str] = Field(None, description="结束原因")
    tool_calls: Optional[List[ToolCall]] = Field(None, description="工具调用列表")
    usage: Usage = Field(..., description="使用量统计")

class AgentResponse(BaseModel):
    """大模型调用的返回结果类"""
    content: Optional[str] = Field(..., description="响应内容")
    finish_reason: str = Field(..., description="结束原因")
    tool_calls: Optional[List[ToolCall]] = Field(None, description="工具调用列表")
    usage: Usage = Field(..., description="使用量统计")
    metadata: AgentResponseMetadata

    is_streaming: bool = False
    _stream_generator: Optional[Generator[AgentResponseChunk, None, None]] = None

    @property
    def prompt_tokens(self) -> int:
        """获取prompt的token数量"""
        return self.usage.prompt_tokens if self.usage else 0

    @property
    def completion_tokens(self) -> int:
        """获取completion的token数量"""
        return self.usage.completion_tokens if self.usage else 0

    @property
    def total_tokens(self) -> int:
        """获取总token数量"""
        return self.usage.total_tokens if self.usage else 0

    def set_stream_generator(self, generator: Generator[AgentResponseChunk, None, None]):
        """设置流式输出生成器
        Args:
            generator: 流式输出的生成器
        """
        self.is_streaming = True
        self._stream_generator = generator

    def stream(self) -> Generator[AgentResponseChunk, None, None]:
        """获取流式输出的生成器"""
        if not self.is_streaming or not self._stream_generator:
            yield AgentResponseChunk(
                content=self.content,
                finish_reason=self.finish_reason,
                tool_calls=self.tool_calls,
                usage=self.usage
            )
            return

        for chunk in self._stream_generator:
            yield chunk
            if chunk.finish_reason:
                self.finish_reason = chunk.finish_reason
            if chunk.usage:
                self.usage = chunk.usage
            if chunk.content:
                if not self.content:
                    self.content = ""
                self.content += chunk.content
            if chunk.tool_calls:
                if not self.tool_calls:
                    self.tool_calls = []
                self.tool_calls.extend(chunk.tool_calls)


class VectorDBConfig(TypedDict):
    """向量数据库配置类型"""
    vector_db_path: str
    embedding_model: Optional[str]
    short_term_capacity: int


class Agent:
    """基础智能体类"""
    ROLE = "base"
    DESCRIPTION = "一个通用对话智能助手"

    def __init__(
        self,
        name: str,
        llm_engine: LLMEngine,
        vector_db_config: Optional[VectorDBConfig] = None,
        capabilities: Optional[List[AgentCapability]] = None,
        description: Optional[str] = None,
        tools: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """初始化智能体
        Args:
            name: 智能体名称
            llm_engine: 语言模型引擎
            vector_db_config: 向量数据库配置
            capabilities: 智能体能力列表
            description: 智能体描述
            tools: 初始工具字典
            **kwargs: 其他参数
        """
        self.name = name
        self.llm_engine = llm_engine
        self.capabilities = capabilities or []
        self.description = description or self.DESCRIPTION
        self.vector_db_config = vector_db_config or {}
        self.kwargs = kwargs
        self._tools = tools or {}

        # 初始化记忆管理器
        self.memory = AgentMemory(
            vector_db_path=self.vector_db_config.get("vector_db_path", None),
            embedding_model=self.vector_db_config.get("embedding_model", None),
            short_term_capacity=self.vector_db_config.get("short_term_capacity", 10)
        )

    @property
    def tools(self) -> Dict[str, Any]:
        """获取工具字典"""
        return self._tools

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
        
    def retrieve_memories(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """检索相关记忆
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            
        Returns:
            List[MemoryItem]: 相关记忆列表
        """
        if self.memory.is_empty():
            return []
            
        # 从短期和长期记忆中检索
        agent_memories = self.memory.search_memory(query, top_k=10)
            
        return [
            memory.to_message()
            for memory in agent_memories
        ]

    def run(self, text: str, stream: bool = True) -> Generator[AgentResponse, None, None]:
        """运行智能体，处理用户输入并生成响应
        
        Args:
            text: 用户输入的消息
            stream: 是否流式输出
            
        Yields:
            AgentResponse: 智能体的响应结果
        """
        history_messages = self.retrieve_memories(text, top_k=5)

        messages = history_messages + [
            {"role": "user", "content": text}
        ]
        if messages[0]["role"] != "system":
            messages.insert(0, {
                "role": "system",
                "content": self.system_prompt()
            })

        try:
            # 调用LLM引擎生成响应
            response = self.llm_engine.generate(
                messages=messages,
                stream=stream
            )

            # 构建响应结果
            agent_response = AgentResponse(
                content="",
                finish_reason=None,
                tool_calls=None,
                usage=Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                metadata=AgentResponseMetadata(
                    request_context={"message": message},
                    raw_response=response if isinstance(response, ChatCompletion) else list(response)
                )
            )

            # 处理同步响应
            if isinstance(response, ChatCompletion):
                # 更新消息历史
                self.messages.append({
                    "role": "assistant",
                    "content": response.choices[0].message.content,
                    "tool_calls": response.choices[0].message.tool_calls
                })

                # 更新响应内容
                agent_response.content = response.choices[0].message.content
                agent_response.finish_reason = response.choices[0].finish_reason
                agent_response.tool_calls = response.choices[0].message.tool_calls
                agent_response.usage = response.usage

            # 处理流式响应
            else:
                def stream_generator():
                    content = ""
                    for chunk in response:
                        if chunk.choices[0].delta.content:
                            content += chunk.choices[0].delta.content
                            yield chunk.choices[0].delta.content
                    # 更新消息历史
                    self.messages.append({
                        "role": "assistant",
                        "content": content
                    })

                agent_response.set_stream_generator(stream_generator())

            yield agent_response

        except Exception as e:
            # 处理异常情况
            error_response = AgentResponse(
                content=str(e),
                finish_reason="error",
                usage=Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                metadata=AgentResponseMetadata(
                    request_context={"message": message},
                    raw_response=None
                )
            )
            yield error_response
