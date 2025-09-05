import json
import logging
from typing import (
    Generator,
    List,
    Optional,
    Sequence,
    overload,
    Literal,
)

from echo.util.logger import get_logger
from echo.llm.llm_engine import LLMEngine
from echo.llm.schema import ChatCompletionChunk, Message, ToolCall
from echo.prompt.prompt_loader import PromptLoader
from echo.tool.base_tool import BaseTool
from echo.parser.stream_parser import StreamResponseParser
from echo.parser.schema import (
    AgentResponseChunk,
    AgentResponse,
)
from echo.config import (
    CompressionConfig,
    RetrievalConfig,
    MemoryConfig, GlobalConfig
)

logger: logging.Logger = get_logger()


def agent_message_stream_parser(
        tools: Sequence[BaseTool],
        chat_completion_chunk_stream_generator: Generator[ChatCompletionChunk, None, None],
) -> Generator[AgentResponseChunk, None, None]:
    """使用StateMachineStreamParser解析流式响应中的工具调用
    
    Args:
        tools: 可用的工具列表
        chat_completion_chunk_stream_generator: 聊天完成块的流式生成器
        
    Yields:
        AgentResponseChunk: 解析后的响应块
    """
    parser = StreamResponseParser(tools)
    yield from parser.parse_stream(chat_completion_chunk_stream_generator)


class Agent:
    """基础智能体类"""

    ROLE = "base"
    DESCRIPTION = "一个通用对话智能助手"

    def __init__(
            self,
            llm_engine: LLMEngine,
            name: Optional[str] = None,
            description: Optional[str] = None,
            tools: Optional[Sequence[BaseTool]] = None,
            system_prompt: Optional[str] = None,
            # 新增的企业级功能配置
            compression_config: Optional[CompressionConfig] = None,
            retrieval_config: Optional[RetrievalConfig] = None,
            memory_config: Optional[MemoryConfig] = None,
            enable_context_compression: bool = True,
            enable_context_retrieval: bool = True,
            enable_memory_management: bool = True,
            **kwargs,
    ):
        """初始化智能体
        Args:
            name: 智能体名称
            llm_engine: 语言模型引擎
            description: 智能体描述
            tools: 初始工具字典
            compression_config: 上下文压缩配置
            retrieval_config: 上下文检索配置
            memory_config: 记忆管理配置
            enable_context_compression: 是否启用上下文压缩
            enable_context_retrieval: 是否启用上下文检索
            enable_memory_management: 是否启用记忆管理
            **kwargs: 其他参数
        """
        self._name = name or self.ROLE
        self._description = description or self.DESCRIPTION
        self._system_prompt = system_prompt
        self.llm_engine = llm_engine
        self.kwargs = kwargs

        # 获取全局配置
        self._global_config = GlobalConfig.get_instance()
        self._history_messages: List[Message] = []
        self._history_messages_limit = 10

        self._tools = tools or []
        self._tool_map = {tool.name: tool for tool in self._tools}

    @property
    def tools(self) -> Sequence[BaseTool]:
        """获取工具字典"""
        return self._tools

    @property
    def role(self):
        return self.ROLE.strip()

    @property
    def name(self):
        return self._name.strip()

    @property
    def description(self):
        return self.DESCRIPTION.strip()

    def system_prompt(self) -> str:
        """渲染系统提示词"""
        if self._system_prompt:
            return self._system_prompt
        # system_info = get_system_info()
        # workspace_info = get_workspace_info(system_info["work_dir"])
        return PromptLoader.get_instance().render_template(
            f"{self.role}/system.prompt",
            name=self.name,
            role=self.role,
            tools=self.tools,
            # system_info=system_info,
            # workspace=workspace_info
        )

    # def retrieve_memories(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    #     """检索相关记忆
    #
    #     Args:
    #         query: 查询文本
    #         top_k: 返回结果数量
    #
    #     Returns:
    #         List[MemoryItem]: 相关记忆列表
    #     """
    #     if self.memory.is_empty():
    #         return []
    #
    #     # 从短期和长期记忆中检索
    #     agent_memories = self.memory.search_memory(query, top_k=10)
    #
    #     return [memory.to_message() for memory in agent_memories]

    def _run_no_stream(
            self, messages: List[Message], **kwargs
    ) -> AgentResponse:
        response = self.llm_engine.generate(messages=messages, stream=False, **kwargs)
        self._history_messages.append(response["choices"][0]["message"])
        return AgentResponse(
            content=response["choices"][0]["message"].get("content", None),
            finish_reason=response["choices"][0]["finish_reason"],
            tool_calls=response["choices"][0]["message"].get("tool_calls", None),
            usage=response["usage"],
        )

    def _run_stream(
            self, messages: List[Message], **kwargs
    ) -> Generator[AgentResponseChunk, None, None]:
        stream_interval = kwargs.get("stream_interval", 3)
        response = self.llm_engine.generate(messages=messages, stream=True, **kwargs)
        response_content = ""
        last_chunk: Optional[AgentResponseChunk] = None
        buffer = ""
        for chunk in agent_message_stream_parser(self.tools, response):
            if chunk.content:
                response_content += chunk.content
            if last_chunk is None:
                # 第一个块
                last_chunk = chunk
            if chunk.type == last_chunk.type:
                # 合并连续的文本块
                buffer += chunk.content
                if len(buffer) >= stream_interval:
                    yield AgentResponseChunk(
                        type=chunk.type,
                        content=buffer,
                        finish_reason=chunk.finish_reason,
                        tool_calls=chunk.tool_calls,
                        usage=chunk.usage,
                    )
                    buffer = ""
            else:
                # 输出上一个块
                if buffer:
                    yield AgentResponseChunk(
                        type=last_chunk.type,
                        content=buffer,
                        finish_reason=last_chunk.finish_reason,
                        tool_calls=last_chunk.tool_calls,
                        usage=last_chunk.usage,
                    )
                    buffer = ""
                yield chunk
            last_chunk = chunk
        self._history_messages.append(
            {"role": "assistant", "content": response_content}
        )
        # logger.debug(f"{self.name}: {response_content}")
        # logger.debug(
        #     json.dumps({
        #         "messages": messages,
        #         "response": response_content,
        #     })
        # )

    @overload
    def run(self, content: str, stream: Literal[False] = False) -> AgentResponse:
        ...

    @overload
    def run(self, content: str, stream: Literal[True]) -> Generator[AgentResponseChunk, None, None]:
        ...

    def run(self, content: str, stream: bool = False) -> AgentResponse | Generator[AgentResponseChunk, None, None]:
        """运行智能体，处理用户输入并生成响应

        Args:
            content: 用户输入的消息
            stream: 是否流式输出
            context: 额外的上下文信息

        Returns:
            AgentResponse: 智能体的响应结果
        """

        # 构建消息列表
        messages = self._history_messages.copy()

        messages.append({"role": "user", "content": content})
        self._history_messages.append({"role": "user", "content": content})

        if stream:
            response = self._run_stream(messages, stream_interval=5)
        else:
            response = self._run_no_stream(messages)
        return response

    def execute_tool(self, tool_call: ToolCall) -> str:
        """执行工具调用

        Args:
            tool_call: 工具调用
        """
        tool_name = tool_call["function"]["name"]
        tool_call_arguments = json.loads(tool_call["function"]["arguments"])
        tool = self._tool_map.get(tool_name, None)
        if not tool:
            return f"未找到工具：{tool_name}"
        try:
            tool_response = tool.run(**tool_call_arguments)

            return f"This is system-generated message.\nThe result of tool call ({tool_name}) is shown below:\n{tool_response}"
        except Exception as e:

            return f"工具调用失败：{e}"
