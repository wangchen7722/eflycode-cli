from typing import List
from echo.llm.advisor import Advisor
from echo.schema.llm import LLMRequest, Message
from echo.prompt.prompt_loader import PromptLoader
from echo.schema.llm import LLMCallResponse, LLMStreamResponse, ToolDefinition
from echo.parser.tool_call_parser import ToolCallStreamParser, ToolCallParser


class ToolCallAdvisor(Advisor):
    """当模型原生不支持工具调用时，使用此 Advisor 进行工具调用"""
    def __init__(self, tools: List[ToolDefinition]):
        super().__init__()
        self.stream_parser = ToolCallStreamParser(tools)
        self.parser = ToolCallParser(tools)

    def _convert_messages(self, messages: List[Message], tools: List[ToolDefinition]) -> List[Message]:
        if not tools:
            return messages
        
        # 非原生工具支持工具调用，需要添加特定的系统提示词，并将 tool 消息转为 user 消息
        tool_call_system_prompt = PromptLoader.get_instance().render_template(
            "tool_call/tool_call_system.prompt",
            tools=tools,
            stream_parser=self.stream_parser
        )
        if messages[0].role == "system":
            messages[0].content += tool_call_system_prompt
        else:
            messages.insert(0, Message(role="system", content=tool_call_system_prompt))
        # 将 tool 消息转为 user 消息
        for message in messages:
            if message.role == "tool":
                message.role = "user"
        return messages


    def before_call(self, request: LLMRequest) -> LLMRequest:
        supports_native = (
            request.context and request.context.capability.supports_native_tool_call
        )
        if not supports_native:
            request.messages = self._convert_messages(request.messages, request.tools)
        return request

    def before_stream(self, request: LLMRequest) -> LLMRequest:
        supports_native = (
            request.context and request.context.capability.supports_native_tool_call
        )
        if not supports_native:
            request.messages = self._convert_messages(request.messages, request.tools)
        return request

    def after_call(self, request: LLMRequest, response: LLMCallResponse) -> LLMCallResponse:
        """在非流式响应接收后调用，可用于修改响应数据"""
        return self.parser.parse(response)

    def after_stream(self, request: LLMRequest, response: LLMStreamResponse) -> LLMStreamResponse:
        """在流式响应接收后调用，可用于修改响应数据"""
        return self.stream_parser.parse_stream(response)