from typing import Dict, List, Literal, Optional, Generator, TypedDict, Any, Tuple, Required
from enum import Enum

from pydantic import BaseModel, Field

from echo.prompt.prompt_loader import PromptLoader
from echo.llms.llm_engine import LLMEngine
from echo.llms.schema import ChatCompletionChunk, Message, Usage, ToolCall
from echo.utils.system_utils import system_info
from echo.utils.tool_utils import apply_tool_calls_template
from echo.memory import AgentMemory


class AgentCapability(Enum):
    """Agent能力枚举类"""

    USE_MEMORY = "use_memory"
    USE_TOOL = "use_tool"
    USE_SHELL = "use_shell"
    USE_MCP = "use_mcp"


class AgentResponseMetadata(TypedDict, total=False):
    """Agent返回结果的元数据类，用于存储请求相关的上下文信息

    Attributes:
        request_context (Dict[str, Any]): 请求上下文信息，可以包含原始请求消息、时间戳等
            示例: {"message": "用户输入", "timestamp": "2024-01-01 12:00:00"}
    """    
    request_context: Required[Dict[str, Any]]


class AgentResponseChunk(BaseModel):
    """Agent返回结果的流式输出类，用于处理大语言模型的流式响应

    Attributes:
        content (Optional[str]): 当前chunk的文本内容
            示例: "这是一段生成的文本"
        finish_reason (Optional[str]): 当前chunk的结束原因
            示例: "stop", "length", "tool_calls", "content_filter", "function_call"
        tool_calls (Optional[List[ToolCall]]): 当前chunk中包含的工具调用
            示例: [{"name": "search", "arguments": {"query": "搜索内容"}}]
        usage (Usage): 当前chunk的token使用统计
            示例: {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
    """

    content: Optional[str]
    finish_reason: Optional[str]
    tool_calls: Optional[List[ToolCall]]
    usage: Optional[Usage]


class AgentResponse(BaseModel):
    """大模型调用的返回结果类，包含完整的响应内容和元数据信息

    Attributes:
        content (Optional[str]): 完整的响应文本内容
            示例: "这是完整的响应文本"
        finish_reason (Optional[str]): 响应结束的原因
            示例: "stop", "length", "tool_calls", "content_filter", "function_call"
        tool_calls (Optional[List[ToolCall]]): 响应中包含的所有工具调用
            示例: [{"name": "search", "arguments": {"query": "搜索内容"}}]
        usage (Usage): 完整响应的token使用统计
            示例: {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300}
        metadata (AgentResponseMetadata): 响应相关的元数据信息
            示例: {"request_context": {"message": "用户输入"}}
        is_streaming (bool): 是否为流式响应
            示例: True
        _stream_generator (Optional[Generator[AgentResponseChunk, None, None]]): 流式响应的生成器
            示例: <generator object stream at 0x...>
    """

    content: Optional[str]
    finish_reason: Optional[str]
    tool_calls: Optional[List[ToolCall]]
    usage: Optional[Usage]
    metadata: Optional[AgentResponseMetadata]

    is_streaming: Optional[bool] = Field(default=False, alias="_is_streaming")
    stream_generator: Optional[Generator[AgentResponseChunk, None, None]] = Field(default=None, alias="_stream_generator")

    def set_stream_generator(
        self, generator: Generator[AgentResponseChunk, None, None]
    ):
        """设置流式输出生成器
        Args:
            generator: 流式输出的生成器
        """
        self.is_streaming = True
        self.stream_generator = generator
        return self

    def stream(self) -> Generator[AgentResponseChunk, None, None]:
        """获取流式输出的生成器"""
        if not self.is_streaming or not self.stream_generator:
            yield AgentResponseChunk(
                content=self.content,
                finish_reason=self.finish_reason,
                tool_calls=self.tool_calls,
                usage=self.usage,
            )
            return

        for chunk in self.stream_generator:
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
        **kwargs,
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
        self._history_messages: List[Message] = []
        self._history_messages_limit = 10
        self._tools = tools or {}

        # 初始化记忆管理器
        self.memory = AgentMemory(
            vector_db_path=self.vector_db_config.get("vector_db_path", None),
            embedding_model=self.vector_db_config.get("embedding_model", None),
            short_term_capacity=self.vector_db_config.get("short_term_capacity", 10),
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
            system_info=system_info(),
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

        return [memory.to_message() for memory in agent_memories]

    def _parse_content(self, content: str) -> Tuple[str, Optional[List[ToolCall]]]:
        """解析消息内容，提取工具调用对象

        Args:
            content: 消息

        Returns:
            List[ToolCall]: 工具调用对象
        """
        ...

    def _preprocess_messages(
        self, messages: List[Message]
    ) -> List[Message]:
        """预处理消息列表，添加系统提示词和角色信息

        Args:
            messages: 消息列表

        Returns:
            List[Dict[str, Any]]: 预处理后的消息列表
        """
        # 将 tool_call 的格式变为 message 格式
        new_messages = []
        for message in messages:
            tool_calls = message.get("tool_calls", None)
            if tool_calls:
                new_messages.append({
                    "role": "assistant",
                    "content": apply_tool_calls_template(tool_calls)
                })
            else:
                new_messages.append(message)
        if messages[0]["role"]!= "system":
            messages.insert(0, {"role": "system", "content": self.system_prompt()})
        return new_messages

    def _run_no_stream(
        self,
        messages: List[Message], stream: Literal[False]
    ) -> AgentResponse:
        response = self.llm_engine.generate(messages=messages, stream=stream)
        return AgentResponse(
            content=response["choices"][0]["message"]["content"],
            finish_reason=response["choices"][0]["finish_reason"],
            tool_calls=response["choices"][0]["message"].get("tool_calls", None),
            usage=response["usage"],
            metadata=None,
        )


    def _run_stream(
        self,
        messages: List[Message], stream: Literal[True]
    ) -> AgentResponse:
       response = self.llm_engine.generate(messages=messages, stream=stream)
       def stream_generator(generator: Generator[ChatCompletionChunk, None, None]):
            for chunk in generator:
                yield AgentResponseChunk(
                    content=chunk["choices"][0]["delta"]["content"],
                    finish_reason=chunk["choices"][0]["finish_reason"],
                    tool_calls=chunk["choices"][0]["delta"].get("tool_calls", None),
                    usage=chunk["usage"],
                )
       return AgentResponse(
            content=None,
            finish_reason=None,
            tool_calls=None,
            usage=Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            metadata=None,
        ).set_stream_generator(stream_generator(response))

    def run(
        self, content: str, stream: bool = False
    ) -> AgentResponse:
        """运行智能体，处理用户输入并生成响应

        Args:
            content: 用户输入的消息
            stream: 是否流式输出

        Returns:
            AgentResponse: 智能体的响应结果
        """
        # history_messages = self.retrieve_memories(content, top_k=5)

        messages = self._history_messages + [{"role": "user", "content": content}]
        messages = self._preprocess_messages(messages)
        if stream:
            response = self._run_stream(messages, True)
        else:
            response = self._run_no_stream(messages, False)
        return response
        # response.metadata = 
        # try:
        #     # 调用LLM引擎生成响应
        #     response = self.llm_engine.generate(messages=messages, stream=stream)

        #     # 构建响应结果
        #     agent_response = AgentResponse(
        #         content="",
        #         finish_reason=None,
        #         tool_calls=None,
        #         usage=Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        #         metadata=AgentResponseMetadata(request_context={"message": content}),
                
        #     )

        #     # 处理同步响应
        #     if not stream:
        #         messages.append(
        #             {
        #                 "role": "assistant",
        #                 "content": response["choices"][0].message.content,
        #                 "tool_calls": response.choices[0].message.tool_calls,
        #             }
        #         )
        #         if response.choices[0].message.content:
        #             response_content, tool_calls = self._parse_content(
        #                 response.choices[0].message.content
        #             )
        #         else:
        #             response_content = None
        #             tool_calls = response.choices[0].message.tool_calls

        #         # 更新响应内容
        #         agent_response.content = response_content
        #         agent_response.tool_calls = tool_calls
        #         agent_response.finish_reason = response.choices[0].finish_reason
        #         agent_response.usage = response.usage

        #     # 处理流式响应
        #     else:

        #         def stream_generator():
        #             content = ""
        #             for chunk in response:
        #                 if chunk.choices[0].delta.content:
        #                     content += chunk.choices[0].delta.content
        #                     yield chunk.choices[0].delta.content
        #             # 更新消息历史
        #             self.messages.append({"role": "assistant", "content": content})

        #         agent_response.set_stream_generator(stream_generator())

        #     yield agent_response

        # except Exception as e:
        #     # 处理异常情况
        #     error_response = AgentResponse(
        #         content=str(e),
        #         finish_reason="error",
        #         usage=Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        #         metadata=AgentResponseMetadata(
        #             request_context={"message": message}, raw_response=None
        #         ),
        #     )
        #     yield error_response
