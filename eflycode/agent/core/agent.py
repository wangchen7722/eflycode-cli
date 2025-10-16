import json
from abc import abstractmethod
from typing import (
    Generator,
    List,
    Optional,
    Sequence,
    Literal,
)

from agent.core.response_converter import AgentResponseConverter
from eflycode.ui.console import ConsoleUI
from eflycode.llm.llm_engine import LLMEngine
from eflycode.schema.llm import LLMPrompt, Message, ToolCall, ToolDefinition
from eflycode.schema.tool import ToolError
from eflycode.prompt.prompt_loader import PromptLoader
from eflycode.tool.base_tool import BaseTool
from eflycode.schema.agent import (
    AgentResponseChunk,
    AgentResponseChunkType,
    AgentResponse,
    ToolCallResponse
)
from eflycode.config import GlobalConfig


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

        self._history_messages: List[Message] = []
        self._history_messages_limit = 10

        self.agent_response_converter = AgentResponseConverter()

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
            tools=self._tool_map
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
        return self.agent_response_converter.convert(response)

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
        prompt = LLMPrompt(messages=messages, tools=self.tools)
        response = self.llm_engine.stream(prompt=prompt)
        response_content = ""

        try:
            for chunk in self.agent_response_converter.convert_stream(response):
                if chunk is None:
                    continue
                
                # 获取内容
                chunk_content = chunk.content or ""
                if chunk_content:
                    response_content += chunk_content
                yield chunk
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
