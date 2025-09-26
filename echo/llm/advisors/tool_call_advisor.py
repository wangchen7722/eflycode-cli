from typing import List, Type, Union
from echo.llm.advisor import Advisor, register_advisor
from echo.schema.llm import LLMRequest, Message
from echo.prompt.prompt_loader import PromptLoader
from echo.schema.llm import LLMCallResponse, LLMStreamResponse, ToolDefinition
from echo.parser.tool_call_parser import ToolCallStreamParser, ToolCallParser


@register_advisor("buildin_tool_call_advisor", priority=10)
class ToolCallAdvisor(Advisor):
    """当模型原生不支持工具调用时，使用此 Advisor 进行工具调用"""
    
    # 标识为系统内置 Advisor
    is_builtin: bool = True
    stream_parser_class: Type[ToolCallStreamParser]
    parser_class: Type[ToolCallParser]

    def _convert_messages(self, messages: List[Message], tools: List[ToolDefinition], parser: Union[ToolCallStreamParser, ToolCallParser]) -> List[Message]:
        if not tools:
            return messages

        # 非原生工具支持工具调用，需要添加特定的系统提示词，并将 tool 消息转为 user 消息
        tool_call_system_prompt = PromptLoader.get_instance().render_template(
            "tool_call/tool_call_system.prompt",
            tools=tools,
            tool_call_parser=parser
        )
        if messages[0].role == "system":
            messages[0].content += "\n\n" + tool_call_system_prompt
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
            request.messages = self._convert_messages(request.messages, request.tools, parser=self.parser_class(request.tools))
        return request

    def before_stream(self, request: LLMRequest) -> LLMRequest:
        supports_native = (
                request.context and request.context.capability.supports_native_tool_call
        )
        if not supports_native:
            request.messages = self._convert_messages(request.messages, request.tools, parser=self.stream_parser_class(request.tools))
        return request

    def after_call(self, request: LLMRequest, response: LLMCallResponse) -> LLMCallResponse:
        """在非流式响应接收后调用，可用于修改响应数据"""
        parser = self.parser_class(request.tools)
        return parser.parse(response)

    def after_stream(self, request: LLMRequest, response: LLMStreamResponse) -> LLMStreamResponse:
        """在流式响应接收后调用，可用于修改响应数据"""
        stream_parser = self.stream_parser_class(request.tools)
        return stream_parser.parse_stream(response)
