import json
import logging
import time
import uuid
from typing import (
    Dict,
    List,
    Literal,
    Optional,
    Generator,
    Any,
    Required,
    Sequence,
    overload
)
from typing_extensions import TypedDict
from enum import Enum

from pydantic import BaseModel

from echoai.prompt.prompt_loader import PromptLoader
from echoai.llms.llm_engine import LLMEngine
from echoai.llms.schema import ChatCompletionChunk, Message, Usage, ToolCall
from echoai.utils.system_utils import get_system_info, get_workspace_info
from echoai.utils.tool_utils import apply_tool_calls_template
from echoai.memory import AgentMemory
from echoai.tools import BaseTool, BaseMemoryTool
from echoai.utils.logger import get_logger

logger: logging.Logger = get_logger()


class AgentResponseChunkType(Enum):
    TEXT = "text"
    TOOL_CALL = "tool_call"
    DONE = "done"

    def __str__(self):
        return self.value

    def __repr__(self):
        return self.value


class AgentResponseChunk(BaseModel):
    """Agent返回结果的流式输出类，用于处理大语言模型的流式响应

    Attributes:
        type (AgentResponseChunkType): 当前chunk的类型
        content (Optional[str]): 当前chunk的文本内容
            示例: "这是一段生成的文本"
        finish_reason (Optional[str]): 当前chunk的结束原因
            示例: "stop", "length", "tool_calls", "content_filter", "function_call"
        tool_calls (Optional[List[ToolCall]]): 当前chunk中包含的工具调用
            示例: [{"name": "search", "arguments": {"query": "搜索内容"}}]
        usage (Usage): 当前chunk的token使用统计
            示例: {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
    """

    type: AgentResponseChunkType
    content: str
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
    """

    content: Optional[str]
    finish_reason: Optional[str]
    tool_calls: Optional[List[ToolCall]]
    usage: Optional[Usage]


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
        chat_completion_chunk_stream_generator: Generator[ChatCompletionChunk, None, None],
) -> Generator[AgentResponseChunk, None, None]:
    """状态机解析器，通过在遇到 '<' 时就进行工具名前缀检测，
    以便尽早判断是否为工具调用标签，减少HTML标签对连续性的影响，同时实现流式输出：
    每个字符（或标签被判断后）都会立即 yield 一个 AgentResponseChunk。

    状态说明：
      - TEXT：普通文本状态，直接逐字符 yield 输出。
      - POTENTIAL_TAG：遇到 '<' 后进入，实时检测缓冲内容是否为候选标签的前缀。
      - TOOL：工具调用块内状态，累积工具调用内部内容，同时逐字符 yield 输出。
      - PARAM：在工具调用块内，正在解析某个参数的内容，逐字符 yield 输出。

    根据不同状态下候选标签的不同，分别判断是否匹配工具调用开始、参数开始或结束标签。
    """
    # 全局候选工具起始标签，例如 "<read_file>"，用于 TEXT 状态下检测
    candidate_tags_text = {f"<{tool.name}>": tool for tool in tools}
    tool_map = {tool.name: tool for tool in tools}

    # 状态定义
    STATE_TEXT = "TEXT"
    STATE_POTENTIAL_TAG = "POTENTIAL_TAG"
    STATE_TOOL = "TOOL"
    STATE_PARAM = "PARAM"

    state = STATE_TEXT
    tag_buffer = ""  # 标签缓冲区
    # TEXT: 在普通文本状态下遇到 <，可能是工具调用的开始标签
    # TOOL: 在工具调用内部遇到 <，可能是参数的开始标签或工具调用的结束标签
    # PARAM: 在参数解析状态下遇到 <，可能是参数的结束标签
    tag_context = None  # POTENTIAL_TAG 的上下文，可能为 "TEXT", "TOOL", "PARAM"
    tool_call: Optional[dict] = (
        None  # 正在解析的工具调用信息 {"name": ..., "arguments": {}, "content": ""}
    )
    current_param: Optional[str] = None  # 当前解析的参数名
    param_buffer = ""  # 参数内容缓冲
    last_finish_reason = None
    last_usage = None

    # 辅助函数：判断 s 是否为候选标签中任意一个的前缀
    def is_prefix(s: str, candidates: list[str]) -> bool:
        return any(candidate.startswith(s) for candidate in candidates)

    # 辅助函数：判断 s 是否与候选标签完全匹配，返回匹配的标签（若匹配则返回该候选标签，否则返回 None）
    def exact_match(s: str, candidates: list[str]) -> Optional[str]:
        for candidate in candidates:
            if s == candidate:
                return candidate
        return None

    # 主循环：逐个 chunk 处理
    for chunk in chat_completion_chunk_stream_generator:
        if chunk is None:
            continue
        last_usage = chunk.get("usage", None)
        last_finish_reason = chunk["choices"][0].get("finish_reason", None)
        chunk_content = chunk["choices"][0]["delta"].get("content", "")
        for char in chunk_content:
            if state == STATE_TEXT:
                if char == "<":
                    state = STATE_POTENTIAL_TAG
                    tag_context = "TEXT"
                    tag_buffer = "<"
                else:
                    # 直接 yield 每个普通字符
                    yield AgentResponseChunk(
                        type=AgentResponseChunkType.TEXT,
                        content=char,
                        finish_reason=None,
                        tool_calls=None,
                        usage=None,
                    )
            elif state == STATE_POTENTIAL_TAG:
                tag_buffer += char
                # 根据上下文确定候选标签
                if tag_context == "TEXT":
                    candidates = list(candidate_tags_text.keys())
                elif tag_context == "TOOL":
                    candidates = []
                    if tool_call is not None:
                        # 当前工具调用的结束标签
                        candidates.append(f"</{tool_call['name']}>")
                        # 允许的参数起始标签
                        allowed_params = (
                            tool_map[tool_call["name"]].parameters
                            if tool_call and tool_call["name"] in tool_map
                            else []
                        )
                        for p in allowed_params:
                            candidates.append(f"<{p}>")
                    else:
                        candidates = []
                elif tag_context == "PARAM":
                    candidates = (
                        [f"</{current_param}>"] if current_param is not None else []
                    )
                else:
                    candidates = []

                # 如果当前 tag_buffer 不是任何候选标签的前缀，则认为不是工具相关标签
                if not candidates or not is_prefix(tag_buffer, candidates):
                    # 修复：根据上下文恢复到正确的状态
                    if tag_context == "TOOL":
                        state = STATE_TOOL
                        if tool_call is not None:
                            tool_call["content"] += tag_buffer  # 将标签内容添加到工具调用内容中
                        # 作为工具调用内容输出，而非普通文本
                        yield AgentResponseChunk(
                            type=AgentResponseChunkType.TOOL_CALL,
                            content=tag_buffer,
                            finish_reason=None,
                            tool_calls=None,
                            usage=None,
                        )
                    elif tag_context == "PARAM":
                        state = STATE_PARAM
                        if tool_call is not None:
                            tool_call["content"] += tag_buffer
                        param_buffer += tag_buffer
                        yield AgentResponseChunk(
                            type=AgentResponseChunkType.TOOL_CALL,
                            content=tag_buffer,
                            finish_reason=None,
                            tool_calls=None,
                            usage=None,
                        )
                    else:  # 默认回到 TEXT 状态
                        # 将 tag_buffer 逐字符 yield 作为普通文本输出
                        yield AgentResponseChunk(
                            type=AgentResponseChunkType.TEXT,
                            content=tag_buffer,
                            finish_reason=None,
                            tool_calls=None,
                            usage=None,
                        )
                        state = STATE_TEXT
                    tag_buffer = ""
                    tag_context = None
                else:
                    # 如果 tag_buffer 完全匹配某个候选标签，则根据上下文进行处理
                    matched_candidate = exact_match(tag_buffer, candidates)
                    if matched_candidate is None:
                        continue
                    if tag_context == "TEXT":
                        # 匹配到工具调用的起始标签，例如 "<read_file>"
                        tool_name = candidate_tags_text[matched_candidate].name
                        tool_call = {
                            "name": tool_name,
                            "arguments": {},
                            "content": matched_candidate,
                        }
                        state = STATE_TOOL
                        tag_buffer = ""
                        tag_context = None
                        yield AgentResponseChunk(
                            type=AgentResponseChunkType.TOOL_CALL,
                            content=matched_candidate,
                            finish_reason=None,
                            tool_calls=None,
                            usage=None,
                        )
                    elif tag_context == "TOOL":
                        if (
                                tool_call is not None
                                and matched_candidate == f"</{tool_call['name']}>"
                        ):
                            # 匹配到工具调用结束标签，结束工具调用，yield 工具调用 chunk
                            yield AgentResponseChunk(
                                type=AgentResponseChunkType.TOOL_CALL,
                                content=matched_candidate,
                                finish_reason="tool_calls",
                                tool_calls=[
                                    ToolCall(
                                        id=uuid.uuid4().hex,
                                        type="function",
                                        function={
                                            "name": tool_call["name"],
                                            "arguments": json.dumps(
                                                tool_call["arguments"]
                                            ),
                                        },
                                    )
                                ],
                                usage=None,
                            )
                            tool_call = None
                            state = STATE_TEXT
                            tag_buffer = ""
                            tag_context = None
                        else:
                            yield AgentResponseChunk(
                                type=AgentResponseChunkType.TOOL_CALL,
                                content=matched_candidate,
                                finish_reason=None,
                                tool_calls=None,
                                usage=None,
                            )
                            # 进入参数解析状态（这里匹配到参数起始标签）
                            tool_call["content"] += matched_candidate
                            param_name = matched_candidate[1:-1]
                            current_param = param_name
                            state = STATE_PARAM
                            tag_buffer = ""
                            tag_context = None
                            param_buffer = ""
                    elif tag_context == "PARAM":
                        # 在参数状态中，只允许匹配参数结束标签
                        if (
                                current_param is not None
                                and matched_candidate == f"</{current_param}>"
                        ):
                            if tool_call is not None:
                                tool_call["content"] += matched_candidate
                                tool_call["arguments"][current_param] = (
                                    param_buffer.strip()
                                )
                            yield AgentResponseChunk(
                                type=AgentResponseChunkType.TOOL_CALL,
                                content=matched_candidate,
                                finish_reason=None,
                                tool_calls=None,
                                usage=None,
                            )
                            current_param = None
                            state = STATE_TOOL
                            tag_buffer = ""
                            tag_context = None
                        else:
                            # 理论上不应进入此分支；如果发生，则按普通文本处理
                            if tool_call is not None:
                                tool_call["content"] += tag_buffer
                            param_buffer += tag_buffer
                            yield AgentResponseChunk(
                                type=AgentResponseChunkType.TOOL_CALL,
                                content=tag_buffer,
                                finish_reason=None,
                                tool_calls=None,
                                usage=None,
                            )
                            tag_buffer = ""
                            state = STATE_PARAM
                            tag_context = None
            elif state == STATE_TOOL:
                if char == "<":
                    state = STATE_POTENTIAL_TAG
                    tag_context = "TOOL"
                    tag_buffer = "<"
                else:
                    # 在工具调用块内，既累积内容又逐字符输出
                    tool_call["content"] += char
                    yield AgentResponseChunk(
                        type=AgentResponseChunkType.TOOL_CALL,
                        content=char,
                        finish_reason=None,
                        tool_calls=None,
                        usage=None,
                    )
            elif state == STATE_PARAM:
                if char == "<":
                    state = STATE_POTENTIAL_TAG
                    tag_context = "PARAM"
                    tag_buffer = "<"
                else:
                    tool_call["content"] += char
                    param_buffer += char
                    yield AgentResponseChunk(
                        type=AgentResponseChunkType.TOOL_CALL,
                        content=char,
                        finish_reason=None,
                        tool_calls=None,
                        usage=None,
                    )

    # 流结束后处理残留数据
    if state == STATE_POTENTIAL_TAG:
        # 根据上下文处理残留的标签缓冲
        if tag_context == "TOOL" and tool_call is not None:
            tool_call["content"] += tag_buffer
            yield AgentResponseChunk(
                type=AgentResponseChunkType.TOOL_CALL,
                content=tag_buffer,
                finish_reason=None,
                tool_calls=None,
                usage=None,
            )
        elif tag_context == "PARAM" and tool_call is not None:
            tool_call["content"] += tag_buffer
            param_buffer += tag_buffer
            yield AgentResponseChunk(
                type=AgentResponseChunkType.TOOL_CALL,
                content=tag_buffer,
                finish_reason=None,
                tool_calls=None,
                usage=None,
            )
        else:
            # 将 tag_buffer 逐字符 yield 作为普通文本输出
            for ch in tag_buffer:
                yield AgentResponseChunk(
                    type=AgentResponseChunkType.TEXT,
                    content=ch,
                    finish_reason=None,
                    tool_calls=None,
                    usage=None,
                )
    elif state == STATE_TOOL and tool_call:
        # 工具调用未正常结束，仍维持工具调用状态
        yield AgentResponseChunk(
            type=AgentResponseChunkType.TOOL_CALL,
            content="",
            finish_reason=last_finish_reason,
            tool_calls=[
                ToolCall(
                    id=uuid.uuid4().hex,
                    type="function",
                    function={
                        "name": tool_call["name"],
                        "arguments": json.dumps(tool_call["arguments"]),
                    },
                )
            ],
            usage=last_usage,
        )
    elif state == STATE_PARAM and tool_call and current_param:
        # 参数未正常结束，添加到工具调用参数中
        tool_call["arguments"][current_param] = param_buffer.strip()
        yield AgentResponseChunk(
            type=AgentResponseChunkType.TOOL_CALL,
            content="",
            finish_reason=last_finish_reason,
            tool_calls=[
                ToolCall(
                    id=uuid.uuid4().hex,
                    type="function",
                    function={
                        "name": tool_call["name"],
                        "arguments": json.dumps(tool_call["arguments"]),
                    },
                )
            ],
            usage=last_usage,
        )

    # 最终完成标记
    yield AgentResponseChunk(
        type=AgentResponseChunkType.DONE,
        content="",
        finish_reason=last_finish_reason,
        tool_calls=None,
        usage=last_usage,
    )


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
        llm_engine: LLMEngine,
        vector_db_config: Optional[VectorDBConfig] = None,
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
        self.vector_db_config = vector_db_config or {}
        self.kwargs = kwargs
        self._history_messages: List[Message] = []
        self._history_messages_limit = 10
        # 初始化工具
        self.auto_approve = kwargs.get("auto_approve", False)

        self._tools = tools or []
        self._tool_map = {tool.name: tool for tool in self._tools}

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
        system_info = get_system_info()
        workspace_info = get_workspace_info(system_info["work_dir"])
        return PromptLoader.get_instance().render_template(
            f"{self.role}/system.prompt",
            name=self.name,
            role=self.role,
            tools=self.tools,
            system_info=system_info,
            workspace=workspace_info
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

    def _preprocess_messages(self, messages: List[Message]) -> List[Message]:
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
                new_messages.append(
                    {
                        "role": "assistant",
                        "content": apply_tool_calls_template(tool_calls),
                    }
                )
            else:
                new_messages.append(message)
        if new_messages[0]["role"] != "system":
            new_messages.insert(0, {"role": "system", "content": self.system_prompt()})
        return new_messages

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
        logger.debug(
            json.dumps({
                "messages": messages,
                "response": response_content,
            })
        )
    
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

        Returns:
            AgentResponse: 智能体的响应结果
        """
        # history_messages = self.retrieve_memories(content, top_k=5)
        # content = content + "\n---\nThe following info is automatically generated by the system.\n" + PromptLoader.get_instance().render_template(
        #     "partials/workspace.prompt",
        #     workspace=get_workspace_info(get_system_info()["work_dir"])
        # )

        messages = self._history_messages + [{"role": "user", "content": content}]
        messages = self._preprocess_messages(messages)
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

    def run_loop(self):
        from echoai.ui.console import ConsoleUI, LoadingUI

        ui = ConsoleUI.get_instance()
        enable_stream = True
        user_input = None
        # tool_call_progress: Optional[LoadingUI] = None
        while True:
            if user_input is None:
                user_input = ui.acquire_user_input()
            if user_input.strip() == "exit" or user_input.strip() == "quit":
                break
            agent_response = self.run(user_input, stream=enable_stream)
            user_input = None
            if enable_stream:
                for chunk in agent_response:
                    if chunk.type == AgentResponseChunkType.TEXT:
                        # 文本输出
                        if not chunk.content:
                            continue
                        ui.show_text(chunk.content, end="")
                    elif chunk.type == AgentResponseChunkType.TOOL_CALL:
                        if chunk.content:
                            ui.show_text(chunk.content, end="")
                        # 工具调用
                        # if tool_call_progress is None:
                            # tool_call_progress = ui.create_loading(
                            #     "loading " + chunk.content[1:-1] + " ..."
                            # )
                            # tool_call_progress.start()
                        if chunk.finish_reason != "tool_calls":
                            # 说明工具调用正在生成，跳过
                            continue
                        if chunk.tool_calls is None:
                            # 说明工具调用未生成，跳过
                            continue
                        # tool_call_progress.stop()
                        # tool_call_progress = None
                        # 这里有且仅会有一个工具调用
                        user_input = ""
                        for tool_call in chunk.tool_calls:
                            tool_call_name = tool_call["function"]["name"]
                            tool_call_arguments = json.loads(
                                tool_call["function"]["arguments"]
                            )
                            tool_call_arguments_str = "\n".join(
                                [f"{k}={v}" for k, v in tool_call_arguments.items()]
                            )
                            # 换行
                            ui.show_text("", end="")
                            ui.show_panel(
                                [self.name, tool_call_name],
                                f"Arguments:\n{tool_call_arguments_str}",
                            )
                            tool = self._tool_map.get(tool_call_name, None)
                            if not self.auto_approve and tool.is_approval:
                                # 征求用户同意
                                if not tool:
                                    user_input = f"This is system-generated message. {tool_call_name} is not found."
                                    break
                                tool_display = tool.display(self.name)
                                ui.show_text(tool_display)
                                user_approval = ui.acquire_user_input("\[yes/no]")
                                if user_approval.strip().lower() in ["no", "n"]:
                                    user_input = f"This is system-generated message. User refused to execute the tool: {tool_call_name}"
                                    break
                                elif user_approval.strip().lower() not in ["yes", "y"]:
                                    user_input = f"This is system-generated message. User refused to execute the tool: {tool_call_name} and say: {user_approval}"
                                    break
                            with ui.create_loading(tool_call_name):
                                tool_call_result = self.execute_tool(tool_call)
                                time.sleep(0.1)  # 等待一段时间，保证控制台能够输出 loading
                            ui.show_panel(
                                [self.name, tool_call_name], f"Result:\n{tool_call_result}"
                            )
                            user_input += tool_call_result + "\n"
                    elif chunk.type == AgentResponseChunkType.DONE:
                        # 流式输出结束
                        ui.show_text("")  # 换行
                    else:
                        raise ValueError(
                            f"Unknown agent response chunk type: {chunk.type}"
                        )
