from typing import Iterator, List, Optional

from openai import OpenAI

from eflycode.core.llm.advisor import Advisor, AdvisorChain
from eflycode.core.llm.protocol import (
    ChatCompletion,
    ChatCompletionChunk,
    DeltaMessage,
    DeltaToolCall,
    DeltaToolCallFunction,
    LLMConfig,
    LLMRequest,
    Message,
    ToolCall,
    ToolCallFunction,
    ToolDefinition,
    Usage,
)
from eflycode.core.llm.providers.base import LLMProvider, ProviderCapabilities
from eflycode.core.event.event_bus import get_global_event_bus


class OpenAiProvider(LLMProvider):
    """基于 OpenAI API 的 LLM Provider 实现"""

    def __init__(self, config: LLMConfig, advisors: Optional[List[Advisor]] = None):
        """初始化 OpenAI Provider

        Args:
            config: LLM 配置
            advisors: Advisor 列表，用于拦截和修改请求响应
        """
        self.config = config
        self._advisors: List[Advisor] = advisors or []
        self.advisor_chain = AdvisorChain(self._advisors.copy())
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout,
            max_retries=config.max_retries,
        )
        get_global_event_bus().subscribe(
            "app.config.llm.changed", self._handle_model_changed
        )

    def add_advisors(self, advisors: List[Advisor]) -> None:
        """添加 Advisor 到现有列表并更新 AdvisorChain

        Args:
            advisors: 要添加的 Advisor 列表
        """
        self._advisors.extend(advisors)
        self.advisor_chain = AdvisorChain(self._advisors.copy())

    def update_config(self, config: LLMConfig) -> None:
        """更新配置并重建客户端"""
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout,
            max_retries=config.max_retries,
        )

    def _handle_model_changed(self, **kwargs) -> None:
        event = kwargs.get("event")
        if event is None:
            return
        self.update_config(event.target)

    @property
    def capabilities(self) -> ProviderCapabilities:
        """返回 Provider 的能力"""
        return ProviderCapabilities(supports_streaming=True, supports_tools=True)

    def call(self, request: LLMRequest) -> ChatCompletion:
        """调用 OpenAI API 并返回响应

        Args:
            request: LLM 请求

        Returns:
            ChatCompletion: 处理后的响应
        """
        return self.advisor_chain.call(request, self._call_api)

    def stream(self, request: LLMRequest) -> Iterator[ChatCompletionChunk]:
        """流式调用 OpenAI API 并返回响应流

        Args:
            request: LLM 请求

        Yields:
            ChatCompletionChunk: 处理后的流式响应块
        """
        yield from self.advisor_chain.stream(request, self._stream_api)

    def _build_api_kwargs(
        self, request: LLMRequest, stream: bool = False
    ) -> dict:
        """构建 OpenAI API 调用的参数字典

        Args:
            request: LLM 请求
            stream: 是否为流式调用

        Returns:
            dict: OpenAI API 调用的参数字典
        """
        messages = self._convert_messages(request.messages)
        tools = self._convert_tools(request.tools) if request.tools else None
        generate_config = request.generate_config or {}

        kwargs = {
            "model": request.model,
            "messages": messages,
            "stream": stream,
        }

        if tools:
            kwargs["tools"] = tools

        if self.config.temperature is not None:
            kwargs["temperature"] = self.config.temperature
        elif "temperature" in generate_config:
            kwargs["temperature"] = generate_config["temperature"]

        if self.config.max_tokens is not None:
            kwargs["max_tokens"] = self.config.max_tokens
        elif "max_tokens" in generate_config:
            kwargs["max_tokens"] = generate_config["max_tokens"]

        if "top_p" in generate_config:
            kwargs["top_p"] = generate_config["top_p"]
        if "frequency_penalty" in generate_config:
            kwargs["frequency_penalty"] = generate_config["frequency_penalty"]
        if "presence_penalty" in generate_config:
            kwargs["presence_penalty"] = generate_config["presence_penalty"]

        return kwargs

    def _call_api(self, request: LLMRequest) -> ChatCompletion:
        """实际调用 OpenAI API

        Args:
            request: LLM 请求

        Returns:
            ChatCompletion: OpenAI 响应转换后的 ChatCompletion
        """
        kwargs = self._build_api_kwargs(request, stream=False)
        response = self.client.chat.completions.create(**kwargs)
        return self._convert_completion(response)

    def _stream_api(self, request: LLMRequest) -> Iterator[ChatCompletionChunk]:
        """实际流式调用 OpenAI API

        Args:
            request: LLM 请求

        Yields:
            ChatCompletionChunk: OpenAI 响应转换后的 ChatCompletionChunk
        """
        kwargs = self._build_api_kwargs(request, stream=True)
        stream = self.client.chat.completions.create(**kwargs)

        for chunk in stream:
            yield self._convert_chunk(chunk)

    def _convert_messages(self, messages: List[Message]) -> List[dict]:
        """转换消息格式为 OpenAI API 格式

        Args:
            messages: 消息列表

        Returns:
            List[dict]: OpenAI 格式的消息列表
        """
        result = []
        for msg in messages:
            openai_msg: dict = {"role": msg.role}
            if msg.content is not None:
                openai_msg["content"] = msg.content
            if msg.tool_call_id is not None:
                openai_msg["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls is not None:
                openai_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]
            result.append(openai_msg)
        return result

    def _convert_tools(self, tools: List[ToolDefinition]) -> List[dict]:
        """转换工具定义格式为 OpenAI API 格式

        Args:
            tools: 工具定义列表

        Returns:
            List[dict]: OpenAI 格式的工具列表
        """
        return [
            {
                "type": tool.type,
                "function": {
                    "name": tool.function.name,
                    "description": tool.function.description,
                    "parameters": {
                        "type": tool.function.parameters.type,
                        "properties": tool.function.parameters.properties,
                        "required": tool.function.parameters.required or [],
                    },
                },
            }
            for tool in tools
        ]

    def _convert_completion(self, response) -> ChatCompletion:
        """转换 OpenAI 响应为 ChatCompletion

        Args:
            response: OpenAI 响应对象

        Returns:
            ChatCompletion: 转换后的响应
        """
        message = response.choices[0].message

        tool_calls = None
        if message.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    type=tc.type,
                    function=ToolCallFunction(
                        name=tc.function.name,
                        arguments=tc.function.arguments or "",
                    ),
                )
                for tc in message.tool_calls
            ]

        usage = None
        if response.usage:
            usage = Usage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )

        return ChatCompletion(
            id=response.id,
            object="chat.completion",
            created=response.created,
            model=response.model,
            message=Message(
                role=message.role,
                content=message.content,
                tool_calls=tool_calls,
            ),
            finish_reason=response.choices[0].finish_reason,
            usage=usage,
        )

    def _convert_chunk(self, chunk) -> ChatCompletionChunk:
        """转换 OpenAI 流式响应块为 ChatCompletionChunk

        Args:
            chunk: OpenAI 流式响应块

        Returns:
            ChatCompletionChunk: 转换后的响应块
        """
        delta = chunk.choices[0].delta if chunk.choices else None

        delta_tool_calls = None
        if delta and delta.tool_calls:
            delta_tool_calls = [
                DeltaToolCall(
                    index=dtc.index,
                    id=dtc.id,
                    type=dtc.type,
                    function=(
                        DeltaToolCallFunction(
                            name=dtc.function.name,
                            arguments=dtc.function.arguments,
                        )
                        if dtc.function
                        else None
                    ),
                )
                for dtc in delta.tool_calls
            ]

        usage = None
        if chunk.usage:
            usage = Usage(
                prompt_tokens=chunk.usage.prompt_tokens,
                completion_tokens=chunk.usage.completion_tokens,
                total_tokens=chunk.usage.total_tokens,
            )

        return ChatCompletionChunk(
            id=chunk.id,
            object="chat.completion.chunk",
            created=chunk.created,
            model=chunk.model,
            delta=DeltaMessage(
                role=delta.role if delta else None,
                content=delta.content if delta else None,
                tool_calls=delta_tool_calls,
            ),
            finish_reason=chunk.choices[0].finish_reason if chunk.choices else None,
            usage=usage,
        )
