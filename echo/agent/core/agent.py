import json
import logging
from typing import (
    Generator,
    List,
    Optional,
    Sequence,
    Literal,
)

from echo.parser import stream_parser
from echo.util.logger import get_logger
from echo.util.system import get_system_info
from echo.llm.llm_engine import LLMEngine
from echo.schema.llm import ChatCompletionChunk, Message, ToolCall
from echo.prompt.prompt_loader import PromptLoader
from echo.tool.base_tool import BaseTool
from echo.parser.stream_parser import StreamResponseParser
from echo.schema.agent import (
    AgentResponseChunk,
    AgentResponse,
)
from echo.config import GlobalConfig


logger: logging.Logger = get_logger()

class Agent:
    """基础智能体类"""

    ROLE = "base"
    DESCRIPTION = "一个通用对话智能助手"

    def __init__(
            self,
            llm_engine: LLMEngine,
            name: Optional[str] = None,
            description: Optional[str] = None,
            system_prompt: Optional[str] = None,
            tools: Optional[Sequence[BaseTool]] = None,
            **kwargs,
    ):
        """初始化智能体
        Args:
            name: 智能体名称
            llm_engine: 语言模型引擎
            description: 智能体描述
            system_prompt: 系统提示词
            tools: 初始工具字典
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

        self.stream_parser = StreamResponseParser(self._tools)

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

    @property
    def system_prompt(self) -> str:
        """渲染系统提示词"""
        if self._system_prompt:
            return self._system_prompt
        system_info = get_system_info()
        return PromptLoader.get_instance().render_template(
            f"{self.role}/v1/system.prompt",
            name=self.name,
            role=self.role,
            tools=self._tool_map,
            system_info=system_info,
            stream_parser=self.stream_parser,
        )

    def _compose_messages(self, content: str) -> List[Message]:
        """构建消息列表"""
        messages = [
            {"role": "system", "content": self.system_prompt},
        ]
        messages.extend(self._history_messages)
        messages.append({"role": "user", "content": content})
        return messages

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
        for chunk in self.stream_parser.parse_stream(response):
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

    def _do_run(self, content: str, stream: Literal[True, False] = False) -> AgentResponse | Generator[AgentResponseChunk, None, None]:
        """运行智能体，处理用户输入并生成响应

        Args:
            content: 用户输入的消息
            stream: 是否流式输出

        Returns:
            AgentResponse: 智能体的响应结果
        """

        # 构建消息列表
        messages = self._compose_messages(content)

        if stream:
            response = self._run_stream(messages, stream_interval=5)
        else:
            response = self._run_no_stream(messages)
        return response

    def chat(self, content: str) -> AgentResponse:
        return self._do_run(content, stream=False)

    def stream(self, content: str) -> Generator[AgentResponseChunk, None, None]:
        return self._do_run(content, stream=True)

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
