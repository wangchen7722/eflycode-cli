from pathlib import Path
from typing import Dict, Iterator, List, Optional

from eflycode.core.agent.session import Session
from eflycode.core.event.event_bus import EventBus
from eflycode.core.llm.advisor import Advisor
from eflycode.core.llm.protocol import (
    ChatCompletion,
    ChatCompletionChunk,
    DEFAULT_MAX_CONTEXT_LENGTH,
    Message,
    ToolDefinition,
)
from eflycode.core.llm.providers.base import LLMProvider
from eflycode.core.tool.base import BaseTool, ToolGroup
from eflycode.core.tool.errors import ToolExecutionError


class ChatConversation:
    """聊天会话，包含当前的响应和全部对话信息"""

    def __init__(self, completion: ChatCompletion, messages: List[Message]):
        """初始化聊天会话

        Args:
            completion: 当前的 ChatCompletion 响应
            messages: 全部对话消息列表
        """
        self.completion = completion
        self.messages = messages

    @property
    def content(self) -> str:
        """获取当前响应的内容"""
        return self.completion.message.content or ""

    @property
    def tool_calls(self) -> Optional[List]:
        """获取工具调用列表"""
        return self.completion.message.tool_calls


class TaskStatistics:
    """任务统计信息"""

    def __init__(
        self,
        total_tokens: int = 0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        iterations: int = 0,
        tool_calls_count: int = 0,
    ):
        """初始化任务统计信息

        Args:
            total_tokens: 总 token 数
            prompt_tokens: 提示 token 数
            completion_tokens: 完成 token 数
            iterations: 迭代次数
            tool_calls_count: 工具调用次数
        """
        self.total_tokens = total_tokens
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.iterations = iterations
        self.tool_calls_count = tool_calls_count

    def add_usage(self, usage) -> None:
        """添加使用量统计

        Args:
            usage: Usage 对象
        """
        if usage:
            self.prompt_tokens += usage.prompt_tokens
            self.completion_tokens += usage.completion_tokens
            self.total_tokens += usage.total_tokens


class TaskConversation:
    """任务会话，包含最终的响应、全部对话信息和任务统计"""

    def __init__(self, conversation: ChatConversation, statistics: TaskStatistics):
        """初始化任务会话

        Args:
            conversation: 最终的聊天会话
            statistics: 任务统计信息
        """
        self.conversation = conversation
        self.statistics = statistics

    @property
    def completion(self) -> ChatCompletion:
        """获取最终的 ChatCompletion"""
        return self.conversation.completion

    @property
    def messages(self) -> List[Message]:
        """获取全部对话消息"""
        return self.conversation.messages

    @property
    def content(self) -> str:
        """获取最终响应的内容"""
        return self.conversation.content


class BaseAgent:
    """Agent 基类，集成 LLMProvider 和工具系统"""

    ROLE = "default"  # Agent 角色，用于加载对应的系统提示词

    def __init__(
        self,
        model: str,
        provider: LLMProvider,
        tools: Optional[List[BaseTool]] = None,
        tool_groups: Optional[List[ToolGroup]] = None,
        event_bus: Optional[EventBus] = None,
        advisors: Optional[List[Advisor]] = None,
    ):
        """初始化 Agent

        Args:
            model: 模型名称
            provider: LLM Provider 实例
            tools: 工具列表
            tool_groups: 工具组列表
            event_bus: 事件总线，如果为 None 则创建新的
            advisors: Advisor 列表，会自动合并到 Provider 的 advisors 中
        """
        self.model_name = model
        self.event_bus = event_bus or EventBus()
        self.session = Session()
        self.max_context_length = DEFAULT_MAX_CONTEXT_LENGTH
        self._advisors: List[Advisor] = advisors or []

        self._tools: Dict[str, BaseTool] = {}
        self._tool_groups: List[ToolGroup] = []

        if tools:
            for tool in tools:
                self._tools[tool.name] = tool

        if tool_groups:
            self._tool_groups.extend(tool_groups)
            for group in tool_groups:
                for tool in group.tools:
                    self._tools[tool.name] = tool

        # 创建 SystemPromptAdvisor 并添加到 advisors
        # 延迟导入以避免循环导入
        from eflycode.core.prompt.system_prompt_advisor import SystemPromptAdvisor
        
        system_prompt_advisor = SystemPromptAdvisor(agent=self)
        self._advisors.append(system_prompt_advisor)

        # 设置 provider，并合并 advisors
        self.provider = provider
        if self._advisors and hasattr(provider, "add_advisors"):
            provider.add_advisors(self._advisors)

    def chat(self, message: str = "") -> ChatConversation:
        """发送消息并获取响应

        Args:
            message: 用户消息，如果为空则使用会话历史

        Returns:
            ChatConversation: 包含当前响应和全部对话信息的会话对象
        """
        if message:
            self.session.add_message("user", message)

        request = self.session.get_context(
            self.model_name,
            max_context_length=self.max_context_length,
            provider=self.provider,
        )
        request.tools = self.get_available_tools()

        if message:
            self.event_bus.emit("agent.message.start", agent=self, message=message)

        try:
            response = self.provider.call(request)
            content = response.message.content or ""
            tool_calls = response.message.tool_calls

            self.session.add_message("assistant", content=content, tool_calls=tool_calls)

            self.event_bus.emit("agent.message.stop", agent=self, response=response)

            return ChatConversation(completion=response, messages=self.session.get_messages())
        except Exception as e:
            self.event_bus.emit("agent.error", agent=self, error=e)
            raise

    def stream(self, message: str = "") -> Iterator[ChatCompletionChunk]:
        """流式发送消息并获取响应

        Args:
            message: 用户消息，如果为空则使用会话历史

        Yields:
            ChatCompletionChunk: 流式响应块
        """
        if message:
            self.session.add_message("user", message)

        request = self.session.get_context(
            self.model_name,
            max_context_length=self.max_context_length,
            provider=self.provider,
        )
        request.tools = self.get_available_tools()

        if message:
            self.event_bus.emit("agent.message.start", agent=self, message=message)

        try:
            full_content = ""
            last_chunk = None
            accumulated_tool_calls = {}
            
            for chunk in self.provider.stream(request):
                # 提取 delta 内容
                if chunk.delta and chunk.delta.content:
                    delta_content = chunk.delta.content
                    full_content += delta_content
                    # 触发增量事件
                    self.event_bus.emit("agent.message.delta", agent=self, delta=delta_content)
                
                # 累积 tool_calls（流式响应中 tool_calls 可能分布在多个 chunk 中）
                if chunk.delta and chunk.delta.tool_calls:
                    for delta_tc in chunk.delta.tool_calls:
                        if delta_tc.index not in accumulated_tool_calls:
                            from eflycode.core.llm.protocol import ToolCall, ToolCallFunction
                            tool_call = ToolCall(
                                id=delta_tc.id or "",
                                type=delta_tc.type or "function",
                                function=ToolCallFunction(
                                    name=delta_tc.function.name if delta_tc.function else "",
                                    arguments=delta_tc.function.arguments if delta_tc.function else "",
                                ),
                            )
                            accumulated_tool_calls[delta_tc.index] = tool_call
                            # 当检测到新的工具调用时，立即触发事件显示工具调用提示
                            if delta_tc.function and delta_tc.function.name:
                                self.event_bus.emit(
                                    "agent.tool.call.start",
                                    agent=self,
                                    tool_name=delta_tc.function.name,
                                    tool_call_id=delta_tc.id or "",
                                )
                        else:
                            # 累积 arguments
                            if delta_tc.function and delta_tc.function.arguments:
                                existing = accumulated_tool_calls[delta_tc.index]
                                existing.function.arguments += delta_tc.function.arguments
                
                last_chunk = chunk
                yield chunk
            
            # 流式完成后，将完整内容添加到会话
            if full_content or accumulated_tool_calls:
                # 将累积的 tool_calls 转换为列表
                tool_calls_list = None
                if accumulated_tool_calls:
                    tool_calls_list = [accumulated_tool_calls[i] for i in sorted(accumulated_tool_calls.keys())]
                    # 当工具调用完整时，触发工具正在执行事件
                    for tool_call in tool_calls_list:
                        self.event_bus.emit(
                            "agent.tool.call.ready",
                            agent=self,
                            tool_name=tool_call.function.name,
                            tool_call_id=tool_call.id,
                            arguments=tool_call.function.arguments_dict,
                        )
                self.session.add_message("assistant", content=full_content, tool_calls=tool_calls_list)
            
            # 构建完整的 ChatCompletion 用于触发 stop 事件
            if last_chunk:
                from eflycode.core.llm.protocol import ChatCompletion, Message as LLMMessage
                # 将累积的 tool_calls 转换为列表
                tool_calls_list = None
                if accumulated_tool_calls:
                    tool_calls_list = [accumulated_tool_calls[i] for i in sorted(accumulated_tool_calls.keys())]
                
                completion = ChatCompletion(
                    id=last_chunk.id,
                    object="chat.completion",
                    created=last_chunk.created,
                    model=last_chunk.model,
                    message=LLMMessage(
                        role="assistant",
                        content=full_content,
                        tool_calls=tool_calls_list,
                    ),
                    finish_reason=last_chunk.finish_reason,
                    usage=last_chunk.usage,
                )
                self.event_bus.emit("agent.message.stop", agent=self, response=completion)
        except Exception as e:
            self.event_bus.emit("agent.error", agent=self, error=e)
            raise

    def run_tool(self, tool_name: str, tool_call_id: str = "", **kwargs) -> str:
        """执行工具

        Args:
            tool_name: 工具名称
            tool_call_id: 工具调用 ID
            **kwargs: 工具参数

        Returns:
            str: 工具执行结果

        Raises:
            ToolExecutionError: 当工具执行失败时抛出
        """
        tool = self._tools.get(tool_name)
        if not tool:
            raise ToolExecutionError(
                message=f"工具不存在: {tool_name}",
                tool_name=tool_name,
            )

        self.event_bus.emit("agent.tool.call", agent=self, tool_name=tool_name, arguments=kwargs, tool_call_id=tool_call_id)

        try:
            result = tool.run(**kwargs)
            self.event_bus.emit("agent.tool.result", agent=self, tool_name=tool_name, result=result, tool_call_id=tool_call_id)
            return result
        except Exception as e:
            self.event_bus.emit("agent.tool.error", agent=self, tool_name=tool_name, error=e, tool_call_id=tool_call_id)
            raise

    def get_available_tools(self) -> List[ToolDefinition]:
        """获取可用工具列表

        Returns:
            List[ToolDefinition]: 工具定义列表
        """
        return [tool.definition for tool in self._tools.values()]

    def add_tool(self, tool: BaseTool) -> None:
        """添加工具

        Args:
            tool: 要添加的工具
        """
        self._tools[tool.name] = tool

    def remove_tool(self, tool_name: str) -> bool:
        """移除工具

        Args:
            tool_name: 工具名称

        Returns:
            bool: 是否成功移除
        """
        if tool_name in self._tools:
            del self._tools[tool_name]
            return True
        return False

    def add_tool_group(self, tool_group: ToolGroup) -> None:
        """添加工具组

        Args:
            tool_group: 要添加的工具组
        """
        self._tool_groups.append(tool_group)
        for tool in tool_group.tools:
            self._tools[tool.name] = tool

    def remove_tool_group(self, group_name: str) -> bool:
        """移除工具组

        Args:
            group_name: 工具组名称

        Returns:
            bool: 是否成功移除
        """
        for i, group in enumerate(self._tool_groups):
            if group.name == group_name:
                removed_group = self._tool_groups.pop(i)
                for tool in removed_group.tools:
                    self._tools.pop(tool.name, None)
                return True
        return False

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """获取工具

        Args:
            tool_name: 工具名称

        Returns:
            Optional[BaseTool]: 找到的工具，如果不存在则返回 None
        """
        return self._tools.get(tool_name)

    def _set_provider(self, provider: LLMProvider) -> None:
        """设置 Provider 并合并 advisors

        Args:
            provider: LLM Provider 实例
        """
        self.provider = provider
        if self._advisors and hasattr(provider, "add_advisors"):
            provider.add_advisors(self._advisors)

    def add_advisor(self, advisor: Advisor) -> None:
        """添加 Advisor 到 Agent

        Args:
            advisor: 要添加的 Advisor
        """
        self._advisors.append(advisor)
        # 如果 provider 已设置且支持 add_advisors，立即合并
        if self.provider and hasattr(self.provider, "add_advisors"):
            self.provider.add_advisors([advisor])

    def get_advisors(self) -> List[Advisor]:
        """获取 Agent 的 Advisor 列表

        Returns:
            List[Advisor]: Advisor 列表
        """
        return self._advisors.copy()

    def shutdown(self) -> None:
        """关闭 Agent，清理资源"""
        self.event_bus.shutdown(wait=True)
