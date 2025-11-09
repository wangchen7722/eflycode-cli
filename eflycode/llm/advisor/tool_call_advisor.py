from typing import List, Union
from eflycode.llm.advisor import Advisor
from eflycode.schema.llm import LLMRequest, Message
from eflycode.prompt.prompt_loader import PromptLoader
from eflycode.schema.llm import LLMCallResponse, LLMStreamResponse, ToolDefinition
from eflycode.parser.tool_call_parser import ToolCallStreamParser, ToolCallParser


class ToolCallAdvisor(Advisor):
    """当模型原生不支持工具调用时，使用此 Advisor 进行工具调用"""
    
    def __init__(self):
        """初始化 ToolCallAdvisor"""
        self.stream_parser_class = ToolCallStreamParser
        self.parser_class = ToolCallParser
    
    def get_priority(self) -> int:
        """获取 Advisor 的优先级"""
        return 10

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
        supports_native = (
                request.context and request.context.capability.supports_native_tool_call
        )
        if supports_native:
            return response
        parser = self.parser_class(request.tools)
        return parser.parse(response)

    def after_stream(self, request: LLMRequest, response: LLMStreamResponse) -> LLMStreamResponse:
        """在流式响应接收后调用，可用于修改响应数据"""
        supports_native = (
                request.context and request.context.capability.supports_native_tool_call
        )
        if supports_native:
            return response
        stream_parser = self.stream_parser_class(request.tools)
        return stream_parser.parse_stream(response)
