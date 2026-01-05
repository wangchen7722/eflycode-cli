from abc import ABC
from typing import Callable, Iterator, List, Optional

from eflycode.core.llm.protocol import ChatCompletion, ChatCompletionChunk, LLMRequest


class Advisor(ABC):
    """Advisor 抽象基类，提供钩子方法用于拦截和修改 LLM 请求和响应"""

    def before_call(self, request: LLMRequest) -> LLMRequest:
        """在请求发送前调用，可用于修改请求参数

        Args:
            request: LLM请求

        Returns:
            LLMRequest: 修改后的请求
        """
        return request

    def after_call(self, request: LLMRequest, response: ChatCompletion) -> ChatCompletion:
        """在响应接收后调用，可用于修改响应数据

        Args:
            request: LLM请求
            response: LLM响应

        Returns:
            ChatCompletion: 修改后的响应
        """
        return response

    def on_call_error(self, request: LLMRequest, error: Exception) -> ChatCompletion:
        """在请求处理过程中发生错误时调用，可用于处理异常情况

        Args:
            request: LLM请求
            error: 发生的异常

        Returns:
            ChatCompletion: 错误响应

        Raises:
            Exception: 默认行为是重新抛出异常
        """
        raise error

    def before_stream(self, request: LLMRequest) -> LLMRequest:
        """在流式请求发送前调用，可用于修改请求参数

        Args:
            request: LLM请求

        Returns:
            LLMRequest: 修改后的请求
        """
        return request

    def after_stream(self, request: LLMRequest, response: ChatCompletionChunk) -> ChatCompletionChunk:
        """在流式响应接收后调用，可用于修改响应数据

        Args:
            request: LLM请求
            response: LLM流式响应

        Returns:
            ChatCompletionChunk: 修改后的响应
        """
        return response

    def on_stream_error(self, request: LLMRequest, error: Exception) -> ChatCompletionChunk:
        """在流式请求处理过程中发生错误时调用，可用于处理异常情况

        Args:
            request: LLM请求
            error: 发生的异常

        Returns:
            ChatCompletionChunk: 错误响应

        Raises:
            Exception: 默认行为是重新抛出异常
        """
        raise error


class AdvisorChain:
    """管理多个 Advisor 的执行顺序，实现洋葱模型"""

    def __init__(self, advisors: Optional[List[Advisor]] = None):
        """初始化 Advisor 链

        Args:
            advisors: Advisor 列表，按顺序执行 before 钩子，逆序执行 after 钩子
        """
        self.advisors = advisors or []

    def call(
        self,
        request: LLMRequest,
        api_call: Callable[[LLMRequest], ChatCompletion],
    ) -> ChatCompletion:
        """执行调用，按顺序执行 before_call，调用 API，按逆序执行 after_call

        Args:
            request: LLM请求
            api_call: 实际的 API 调用函数

        Returns:
            ChatCompletion: 处理后的响应

        Raises:
            Exception: 如果错误处理钩子重新抛出异常
        """
        processed_request = request
        for advisor in self.advisors:
            processed_request = advisor.before_call(processed_request)

        try:
            response = api_call(processed_request)
        except Exception as error:
            for advisor in reversed(self.advisors):
                try:
                    return advisor.on_call_error(processed_request, error)
                except Exception:
                    continue
            raise

        for advisor in reversed(self.advisors):
            response = advisor.after_call(processed_request, response)

        return response

    def stream(
        self,
        request: LLMRequest,
        api_stream: Callable[[LLMRequest], Iterator[ChatCompletionChunk]],
    ) -> Iterator[ChatCompletionChunk]:
        """执行流式调用，按顺序执行 before_stream，流式调用 API，对每个 chunk 按逆序执行 after_stream

        Args:
            request: LLM请求
            api_stream: 实际的流式 API 调用函数

        Yields:
            ChatCompletionChunk: 处理后的流式响应块

        Raises:
            Exception: 如果错误处理钩子重新抛出异常
        """
        processed_request = request
        for advisor in self.advisors:
            processed_request = advisor.before_stream(processed_request)

        try:
            for chunk in api_stream(processed_request):
                processed_chunk = chunk
                for advisor in reversed(self.advisors):
                    processed_chunk = advisor.after_stream(processed_request, processed_chunk)
                yield processed_chunk
        except Exception as error:
            for advisor in reversed(self.advisors):
                try:
                    yield advisor.on_stream_error(processed_request, error)
                    return
                except Exception:
                    continue
            raise

