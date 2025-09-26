import json
from abc import abstractmethod
from typing import (
    Generator,
    List,
    Optional,
    Sequence,
    Literal,
)

from echo.ui.console import ConsoleUI
from echo.llm.llm_engine import LLMEngine
from echo.schema.llm import LLMPrompt, Message, ToolCall, ToolDefinition
from echo.schema.tool import ToolError
from echo.prompt.prompt_loader import PromptLoader
from echo.tool.base_tool import BaseTool
from echo.parser.stream_parser import StreamResponseParser
from echo.schema.agent import (
    AgentResponseChunk,
    AgentResponseChunkType,
    AgentResponse,
    ToolCallResponse
)
from echo.config import GlobalConfig


class BaseAgent:
    """基础智能体类"""

    ROLE = "base"
    DESCRIPTION = "所有智能体的基类，仅用来定义接口，没有任何功能。"

    def __init__(self, name: Optional[str] = None, description: Optional[str] = None):
        self._name = name or self.ROLE
        self._description = description or self.DESCRIPTION

    @property
    def role(self):
        return self.ROLE.strip()

    @property
    def name(self):
        return self._name.strip()

    @property
    def description(self):
        return self.DESCRIPTION.strip()

    @abstractmethod
    def call(self, content: str) -> AgentResponse:
        """运行智能体"""
        pass


class ToolCallMixin:
    """工具调用混入类，为智能体提供工具调用能力"""

    def __init__(self, tools: Optional[Sequence[BaseTool]] = None, **kwargs):
        super().__init__(**kwargs)
        self._tools = tools or []
        self._tool_map = {tool.name: tool for tool in self._tools}

    @property
    def tools(self) -> List[ToolDefinition]:
        """获取工具定义列表
        
        Returns:
            List[ToolDefinition]: 工具定义列表
        """
        return [tool.definition for tool in self._tools]

    def execute_tool(self, tool_call: ToolCall) -> ToolCallResponse:
        """执行工具调用

        Args:
            tool_call: 工具调用对象

        Returns:
            ToolCallResponse: 工具调用响应结果
        """
        tool_name = tool_call.function.name
        tool_call_arguments = tool_call.function.arguments
        tool = self._tool_map.get(tool_name, None)
        
        if not tool:
            tool_call_response_message = PromptLoader.get_instance().render_template(
                "tool_call/tool_call_not_found.prompt",
                tool_name=tool_name,
                tools=self._tool_map,
            )
            return ToolCallResponse(
                tool_name=tool_name,
                arguments=tool_call_arguments,
                success=False,
                result=f"工具 {tool_name} 不存在",
                message=tool_call_response_message,
            )
        
        try:
            tool_response = tool.run(**json.loads(tool_call_arguments))
            tool_call_response_message = PromptLoader.get_instance().render_template(
                "tool_call/tool_call_succeeded.prompt",
                tool_name=tool_name,
                tool_response=tool_response,
            )
            return ToolCallResponse(
                tool_name=tool_name,
                arguments=tool_call_arguments,
                success=True,
                result=tool_response,
                message=tool_call_response_message,
            )
        except ToolError as e:
            tool_call_response_message = PromptLoader.get_instance().render_template(
                "tool_call/tool_call_failed.prompt",
                tool_name=tool_name,
                tool_response=str(e),
            )
            return ToolCallResponse(
                tool_name=tool_name,
                arguments=tool_call_arguments,
                success=False,
                result=str(e),
                message=tool_call_response_message,
            )


class ConversationAgent(ToolCallMixin, BaseAgent):
    """对话智能体，支持工具调用"""
    
    ROLE = "conversation"
    DESCRIPTION = "一个通用对话智能助手"

    def __init__(
            self,
            llm_engine: LLMEngine,
            system_prompt: Optional[str] = None,
            name: Optional[str] = None,
            description: Optional[str] = None,
            tools: Optional[List[BaseTool]] = None,
            **kwargs,
    ):
        """初始化智能体
        
        Args:
            llm_engine: 语言模型引擎
            system_prompt: 系统提示词
            name: 智能体名称
            description: 智能体描述
            tools: 工具列表
            **kwargs: 其他参数
        """
        super().__init__(name=name, description=description, tools=tools, **kwargs)
        self._system_prompt = system_prompt
        self.llm_engine = llm_engine
        self.kwargs = kwargs

        # 获取全局配置
        self._global_config = GlobalConfig.get_instance()
        self._history_messages: List[Message] = []
        self._history_messages_limit = 10

        self.stream_parser = StreamResponseParser(self._tools)

    @property
    def system_prompt(self) -> str:
        """渲染系统提示词
        
        Returns:
            str: 渲染后的系统提示词
        """
        if self._system_prompt:
            return self._system_prompt
        return PromptLoader.get_instance().render_template(
            f"{self.role}/system.prompt",
            name=self.name,
            role=self.role,
            tools=self._tool_map,
            stream_parser=self.stream_parser,
        )

    def _compose_messages(self) -> List[Message]:
        """构建消息列表
        
        Returns:
            List[Message]: 消息列表
        """
        messages = [
            Message(role="system", content=self.system_prompt),
        ]
        messages.extend(self._history_messages)
        return messages

    def _run_no_stream(
            self, messages: List[Message]
    ) -> AgentResponse:
        """非流式运行智能体
        
        Args:
            messages: 消息列表
            
        Returns:
            AgentResponse: 智能体响应
        """
        prompt = LLMPrompt(messages=messages, tools=self.tools)
        response = self.llm_engine.call(prompt=prompt)
        self._history_messages.append(response.choices[0].message)
        return AgentResponse(
            messages=messages,
            content=response.choices[0].message.content,
            finish_reason=response.choices[0].finish_reason,
            tool_calls=response.choices[0].message.tool_calls,
            usage=response.usage,
        )

    def _run_stream(
            self, messages: List[Message], **kwargs
    ) -> Generator[AgentResponseChunk, None, None]:
        """流式运行智能体
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Yields:
            AgentResponseChunk: 智能体响应块
        """
        stream_interval = kwargs.get("stream_interval", 3)
        prompt = LLMPrompt(messages=messages, tools=self.tools)
        response = self.llm_engine.stream(prompt=prompt)
        response_content = ""
        last_chunk: Optional[AgentResponseChunk] = None
        buffer = ""

        try:
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
        finally:
            # 确保无论生成器是否被提前终止，都会记录消息历史
            if response_content:
                self._history_messages.append(Message(role="assistant", content=response_content))

    def _do_run(self, content: str, stream: Literal[True, False] = False) -> AgentResponse | Generator[
        AgentResponseChunk, None, None]:
        """运行智能体，处理用户输入并生成响应

        Args:
            content: 用户输入的消息
            stream: 是否流式输出

        Returns:
            AgentResponse | Generator[AgentResponseChunk, None, None]: 智能体的响应结果
        """
        user_message = Message(role="user", content=content)
        self._history_messages.append(user_message)

        # 构建消息列表
        messages = self._compose_messages()

        if stream:
            response = self._run_stream(messages, stream_interval=5)
        else:
            response = self._run_no_stream(messages)
        return response

    def call(self, content: str) -> AgentResponse:
        """实现基类的抽象方法
        
        Args:
            content: 用户输入内容
            
        Returns:
            AgentResponse: 智能体响应
        """
        return self.chat(content)

    def chat(self, content: str) -> AgentResponse:
        """聊天方法
        
        Args:
            content: 用户输入内容
            
        Returns:
            AgentResponse: 智能体响应
        """
        return self._do_run(content, stream=False)

    def stream(self, content: str) -> Generator[AgentResponseChunk, None, None]:
        """流式聊天方法
        
        Args:
            content: 用户输入内容
            
        Yields:
            AgentResponseChunk: 智能体响应块
        """
        return self._do_run(content, stream=True)


class InteractiveConversationAgent(ConversationAgent):
    """交互式对话智能体"""

    def __init__(
            self,
            ui: ConsoleUI,
            llm_engine: LLMEngine,
            system_prompt: Optional[str] = None,
            name: Optional[str] = None,
            description: Optional[str] = None,
            tools: Optional[Sequence[BaseTool]] = None,
            **kwargs,
    ):
        """初始化交互式对话智能体
        
        Args:
            ui: 控制台UI实例
            llm_engine: 语言模型引擎
            system_prompt: 系统提示词
            name: 智能体名称
            description: 智能体描述
            tools: 工具列表
            **kwargs: 其他参数
        """
        super().__init__(
            llm_engine=llm_engine,
            system_prompt=system_prompt,
            name=name,
            description=description,
            tools=tools,
            **kwargs,
        )
        self._ui = ui

    @property
    def ui(self) -> ConsoleUI:
        """获取UI实例
        
        Returns:
            ConsoleUI: 控制台UI实例
        """
        return self._ui

    def interactive_chat(self) -> None:
        """交互式聊天"""
        conversation_count = 0
        user_input = None
        while True:
            try:
                if user_input is None:
                    user_input = self.ui.acquire_user_input()
                if not user_input:
                    continue

                streaming_response = self.stream(user_input)
                user_input = None

                for chunk in streaming_response:
                    self.ui.print(chunk.model_dump_json())
                    if chunk.type == AgentResponseChunkType.TEXT:
                        # if chunk.content:
                        #     self.ui.print(chunk.content.strip())
                        continue
                    elif chunk.type == AgentResponseChunkType.TOOL_CALL:
                        if chunk.tool_calls is None or len(chunk.tool_calls) == 0:
                            raise RuntimeError("工具调用不能为空")
                        tool_call = chunk.tool_calls[0]
                        tool_name = tool_call.function.name
                        tool_args = json.loads(tool_call.function.arguments)
                        tool_call_display = self._tool_map[tool_name].display(**tool_args)
                        # self.ui.panel([tool_name], tool_call_display, color="blue")
                        tool_call_response = self.execute_tool(tool_call)
                        # if tool_call_response.success:
                        #     self.ui.panel([tool_name], tool_call_response.result, color="green")
                        # else:
                        #     self.ui.panel([tool_name], tool_call_response.result, color="red")
                        user_input = tool_call_response.message
                        # break
                    elif chunk.type == AgentResponseChunkType.DONE:
                        if chunk.metadata is not None and "raw_content" in chunk.metadata:
                            self.ui.print(chunk.metadata["raw_content"])

                conversation_count += 1
            except KeyboardInterrupt:
                break
            except RuntimeError as e:
                self.ui.error(f"运行时错误: {str(e)}")
                continue
