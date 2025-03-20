import json
import logging
import os.path
import uuid
from typing import Dict, List, Literal, Optional, Generator, Any, Required, Sequence, overload
from typing_extensions import TypedDict
from enum import Enum

from pydantic import BaseModel, Field

from echo.prompt.prompt_loader import PromptLoader
from echo.llms.llm_engine import LLMEngine
from echo.llms.schema import ChatCompletionChunk, Message, Usage, ToolCall
from echo.utils.system_utils import system_info
from echo.utils.tool_utils import apply_tool_calls_template
from echo.memory import AgentMemory
from echo.tools import BaseTool
from echo.utils.logger import get_logger


class AgentCapability(Enum):
    """Agent能力枚举类"""

    USE_TOOL = "use_tool"
    USE_MCP = "use_mcp"

    def __str__(self):
        return self.value


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
    tool_calls: Optional[Sequence[ToolCall]]
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
    stream_generator: Optional[Generator[AgentResponseChunk, None, None]] = Field(default=None,
                                                                                  alias="_stream_generator")

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
        self.is_streaming = False
        self.stream_generator = None


class AgentMessageParserResult(TypedDict, total=False):
    """
    工具调用解析结果
    Attributes:
        type (Literal["message", "tool_call"]): 结果类型
        content (str): 消息内容
        tool_call_name (Optional[str]): 工具名称
        tool_call_arguments (Optional[Dict[str, Any]]): 工具参数
        partial (bool): 是否为部分解析结果
    """
    partial: Required[bool]
    type: Required[Literal["message", "tool_call"]]
    content: Required[Optional[str]]
    tool_call_name: Required[Optional[str]]
    tool_call_arguments: Required[Optional[Dict[str, Any]]]


def agent_message_stream_parser(
        tools: Sequence[BaseTool],
        chat_completion_chunk_stream_generator: Generator[ChatCompletionChunk, None, None]
) -> Generator[AgentResponseChunk, None, None]:
    """解析工具调用消息

    Args:
        tools (List[BaseTool]): 工具列表
        chat_completion_chunk_stream_generator (str): 消息生成器
    """
    if not tools:
        for chunk in chat_completion_chunk_stream_generator:
            yield AgentResponseChunk(
                content=chunk["choices"][0]["delta"].get("content", None),
                finish_reason=chunk["choices"][0]["finish_reason"],
                tool_calls=None,
                usage=chunk.get("usage", None),
            )
        return
    # 计算最大工具名长度，防止在 content 中输出工具调用标签
    possible_tool_call_tag = [f"<{tool.name}>" for tool in tools]
    max_possible_tool_call_tag_length = max(
        [len(tag) for tag in possible_tool_call_tag]) if possible_tool_call_tag else 0
    # 累计接收到的字符
    accumulator = ""
    # 工具调用相关信息
    tool_map = {tool.name: tool for tool in tools}
    tool_call_param_name = None  # 当前正在解析的工具调用参数的名称
    tool_call_param_start_index = 0  # 当前正在解析的工具调用参数的起始位置
    tool_call_start_index = 0  # 这个指针并非指向工具tag的起始位置，而是指向第一个工具tag的结束位置（即参数解析的第一位）
    # 解析进度以及返回结果
    should_look_ahead = True
    look_ahead_char_count = max_possible_tool_call_tag_length
    index = -1
    result_index = 0
    result: Optional[AgentMessageParserResult] = None
    last_chunk: Optional[ChatCompletionChunk] = None

    for chunk in chat_completion_chunk_stream_generator:
        last_chunk = chunk
        if chunk is None:
            continue
        chunk_content = chunk["choices"][0]["delta"].get("content", "")
        for char in chunk_content:
            accumulator += char
            index += 1

            if should_look_ahead and look_ahead_char_count > 1:
                look_ahead_char_count -= 1
                continue

            if result is not None and result["type"] == "tool_call":
                result["content"] += char

            # 如果正在解析工具调用中的参数，则先处理参数内容
            if result is not None and result["type"] == "tool_call" and tool_call_param_name is not None:
                tool_call_param_string = accumulator[tool_call_param_start_index:]
                # 构造参数的闭合标签
                param_closing_tag = f"</{tool_call_param_name}>"
                if tool_call_param_string.endswith(param_closing_tag):
                    # 检测到参数的结束标签，结束参数解析
                    result["tool_call_arguments"][tool_call_param_name] = tool_call_param_string[
                                                                          :-len(param_closing_tag)].strip()
                    tool_call_param_name = None
                continue

            # 若当前正在工具调用中，但不在解析参数，则继续检查工具调用是否结束
            if result is not None and result["type"] == "tool_call":
                # 从工具调用的起始位置到目前位置的字符串
                tool_call_string = accumulator[tool_call_start_index:]
                # 构造工具调用的闭合标签
                tool_call_closing_tag = f"</{result['tool_call_name']}>"
                if tool_call_string.endswith(tool_call_closing_tag):
                    # 检测到工具调用的结束标签，结束工具调用块的解析
                    result["partial"] = False
                    yield AgentResponseChunk(
                        content=result["content"],
                        finish_reason="tool_calls",
                        tool_calls=[ToolCall(id=uuid.uuid4().hex, type="function", function={
                            "name": result["tool_call_name"],
                            "arguments": json.dumps(result["tool_call_arguments"])
                        })],
                        usage=chunk.get("usage", None),
                    )
                    result = None
                    result_index = index
                    look_ahead_char_count = max_possible_tool_call_tag_length
                    continue
                else:
                    # 检查是否有新的参数开始
                    for param_name in tool_map[result["tool_call_name"]].parameters:
                        param_opening_tag = f"<{param_name}>"
                        if tool_call_string.endswith(param_opening_tag):
                            # 检测到参数的起始标签，开始解析参数
                            tool_call_param_name = param_name
                            tool_call_param_start_index = len(accumulator)
                            break
                    # TODO: 特殊处理工具中同样出现闭合标签的情况

                    # 工具调用内容仍在累积中，继续处理下一个字符
                    continue

            # 检查是否有工具调用标签
            for tool_use_opening_tag in possible_tool_call_tag:
                if accumulator.endswith(tool_use_opening_tag):
                    # 如果有工具调用标签，则开始解析工具调用
                    result = {
                        "partial": True,
                        "type": "tool_call",
                        "content": tool_use_opening_tag,
                        "tool_call_name": tool_use_opening_tag[1:-1],
                        "tool_call_arguments": {},
                    }
                    tool_call_start_index = len(accumulator)
                    break  # 跳出循环，不再检查其他标签

            # 当前没有检查到工具调用，则说明当前字符是文本内容
            if result is None or result["type"] == "message":
                char_index = index - max_possible_tool_call_tag_length + 1
                content_char = accumulator[char_index]
                if result is None:
                    result = {"partial": True, "type": "message", "content": content_char, "tool_call_name": None,
                              "tool_call_arguments": None}
                else:
                    result["content"] = content_char
                yield AgentResponseChunk(content=content_char, finish_reason=chunk["choices"][0]["finish_reason"],
                                         tool_calls=None, usage=chunk.get("usage", None))
                result_index = index - max_possible_tool_call_tag_length + 1
    # 遍历结束后，检查是否还有未完成的工具调用（流未结束），若有则添加到内容块中
    yield AgentResponseChunk(
        content=accumulator[result_index + 1:],
        finish_reason=last_chunk["choices"][0]["finish_reason"] if last_chunk else "stop",
        tool_calls=None,
        usage=last_chunk["usage"] if last_chunk and "usage" in last_chunk else None
    )


class VectorDBConfig(TypedDict):
    """向量数据库配置类型"""

    vector_db_path: str
    embedding_model: Optional[str]
    short_term_capacity: int


logger: logging.Logger = get_logger(os.path.splitext(os.path.basename(__file__))[0])


class Agent:
    """基础智能体类"""

    ROLE = "base"
    DESCRIPTION = "一个通用对话智能助手"

    def __init__(
            self,
            llm_engine: LLMEngine,
            vector_db_config: Optional[VectorDBConfig] = None,
            capabilities: Optional[Sequence[AgentCapability]] = None,
            name: Optional[str] = None,
            description: Optional[str] = None,
            tools: Optional[Sequence[BaseTool]] = None,
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
        self._name = name or self.ROLE
        self._description = description or self.DESCRIPTION
        self.llm_engine = llm_engine
        self.capabilities = capabilities or []
        self.vector_db_config = vector_db_config or {}
        self.kwargs = kwargs
        self._history_messages: List[Message] = []
        self._history_messages_limit = 10
        if tools and AgentCapability.USE_TOOL not in self.capabilities:
            logger.warning("AgentCapability.USE_TOOL not in capabilities, tools will not be used.")
        self._tools = tools or []
        self._tool_map = {tool.NAME: tool for tool in self._tools}

        # 初始化记忆管理器
        self.memory = AgentMemory(
            vector_db_path=self.vector_db_config.get("vector_db_path", None),
            embedding_model=self.vector_db_config.get("embedding_model", None),
            short_term_capacity=self.vector_db_config.get("short_term_capacity", 10),
        )

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
        return PromptLoader.get_instance().render_template(
            f"{self.role}/system.prompt",
            name=self.name,
            role=self.role,
            capabilities=[str(capability) for capability in self.capabilities],
            tools=self.tools,
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
        if new_messages[0]["role"] != "system":
            new_messages.insert(0, {"role": "system", "content": self.system_prompt()})
        return new_messages

    def _run_no_stream(
            self,
            messages: List[Message], stream: Literal[False]
    ) -> AgentResponse:
        response = self.llm_engine.generate(messages=messages, stream=stream)
        return AgentResponse(
            content=response["choices"][0]["message"].get("content", None),
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
        return AgentResponse(
            content=None,
            finish_reason=None,
            tool_calls=None,
            usage=Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            metadata=None,
        ).set_stream_generator(agent_message_stream_parser(self.tools, response))

    @overload
    def run(self, content: str, stream: Literal[False]) -> AgentResponse:
        ...

    @overload
    def run(self, content: str, stream: Literal[True]) -> Generator[AgentResponseChunk, None, AgentResponse]:
        ...

    def run(
            self, content: str, stream: bool = False
    ) -> AgentResponse | Generator[AgentResponseChunk, None, AgentResponse]:
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
        self._history_messages.append({"role": "user", "content": content})

        if stream:
            response = self._run_stream(messages, True)
            for chunk in response.stream():
                yield chunk
        else:
            response = self._run_no_stream(messages, False)
        self._history_messages.append({"role": "assistant", "content": response.content})
        return response

    def execute_tool(self, tool_call: ToolCall) -> str:
        """执行工具调用

        Args:
            tool_call: 工具调用
        """
        if AgentCapability.USE_TOOL not in self.capabilities:
            return "不支持工具调用，请在提示用户 capabilities 中添加 AgentCapability.USE_TOOL"
        tool_name = tool_call["function"]["name"]
        tool = self._tool_map.get(tool_name, None)
        if tool:
            try:
                tool_response = tool.run(**json.loads(tool_call["function"]["arguments"]))
                return f"This is auto-generated response from tool call ({tool_name}):\n{tool_response}"
            except Exception as e:
                return f"工具调用失败：{e}"
        else:
            return f"未找到工具：{tool_name}"


if __name__ == "__main__":
    def stream_generator():
        message = "'<read_file>\n<path>D:/Codes/Python/echo/temp/requirements.txt</path>\n</read_file>'"
        for i in range(0, len(message), 3):
            char = message[i:i + 3]
            yield ChatCompletionChunk(**{
                "id": "123",
                "choices": [
                    {
                        "delta": {
                            "content": char
                        },
                        "finish_reason": None,
                        "tool_calls": None
                    }
                ]
            })


    from echo.tools.file_tool import ReadFileTool

    tools = [ReadFileTool()]
    for result in agent_message_stream_parser(tools, stream_generator()):
        print(result)
