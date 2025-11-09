import re
from abc import ABC, abstractmethod
from typing import Callable, List, Type
from functools import reduce

from eflycode.schema.llm import LLMRequest, LLMCallResponse, LLMStreamResponse

AdvisorCallHandler = Callable[[LLMRequest], LLMCallResponse]
AdvisorStreamHandler = Callable[[LLMRequest], LLMStreamResponse]


class Advisor(ABC):
    """模型请求Advisor"""
    
    @abstractmethod
    def get_priority(self) -> int:
        """获取 Advisor 的优先级
        
        Returns:
            int: 优先级，数值越大优先级越高
        """
        ...

    def handle_call(self, request: LLMRequest, next_handler: AdvisorCallHandler) -> LLMCallResponse:
        request = self.before_call(request)
        try:
            resp = next_handler(request)
            return self.after_call(request, resp)
        except Exception as e:
            return self.on_call_error(request, e)

    def handle_stream(self, request: LLMRequest, next_handler: AdvisorStreamHandler) -> LLMStreamResponse:
        request = self.before_stream(request)
        try:
            resp = next_handler(request)
            return self.after_stream(request, resp)
        except Exception as e:
            return self.on_stream_error(request, e)

    def before_call(self, request: LLMRequest) -> LLMRequest:
        """在请求发送前调用，可用于修改请求参数

        Args:
            request: LLM请求

        Returns:
            LLMRequest: 修改后的请求
        """
        return request

    def after_call(self, request: LLMRequest, response: LLMCallResponse) -> LLMCallResponse:
        """在响应接收后调用，可用于修改响应数据

        Args:
            request: LLM请求
            response: LLM响应

        Returns:
            LLMCallResponse: 修改后的响应
        """
        return response
    

    def on_call_error(self, request: LLMRequest, error: Exception) -> LLMCallResponse:
        """在请求处理过程中发生错误时调用，可用于处理异常情况

        Args:
            request: LLM请求
            error: 发生的异常

        Returns:
            LLMResponse: 错误响应
        """
        raise error

    def before_stream(self, request: LLMRequest) -> LLMRequest:
        """在请求发送前调用，可用于修改请求参数

        Args:
            request: LLM请求

        Returns:
            LLMRequest: 修改后的请求
        """
        return request

    def after_stream(self, request: LLMRequest, response: LLMStreamResponse) -> LLMStreamResponse:
        """在响应接收后调用，可用于修改响应数据

        Args:
            request: LLM请求
            response: LLM响应

        Returns:
            LLMStreamResponse: 修改后的响应
        """
        return response

    def on_stream_error(self, request: LLMRequest, error: Exception) -> LLMStreamResponse:
        """在请求处理过程中发生错误时调用，可用于处理异常情况

        Args:
            request: LLM请求
            error: 发生的异常

        Returns:
            LLMStreamResponse: 错误响应
        """
        raise error
    

class AdvisorChain:
    """Advisor 链，负责管理和执行 Advisor 的调用顺序"""

    def __init__(self, advisors: List[Advisor] = None):
        """初始化 AdvisorChain
        
        Args:
            advisors: Advisor 实例列表
        """
        self._advisors: List[Advisor] = []
        if advisors:
            for advisor in advisors:
                self.add_advisor(advisor)

    @property
    def advisors(self) -> List[Advisor]:
        """获取按优先级排序的 Advisor 列表"""
        return self._get_sorted_advisors()

    def _get_sorted_advisors(self) -> List[Advisor]:
        """获取按优先级排序的 Advisor 列表"""
        return sorted(self._advisors, key=lambda advisor: -advisor.get_priority())

    def add_advisor(self, advisor: Advisor):
        """添加 Advisor 到链中
        
        Args:
            advisor: Advisor 实例
        """
        self._advisors.append(advisor)

    def remove_advisor(self, advisor: Advisor):
        """从链中移除指定的 Advisor
        
        Args:
            advisor: 要移除的 Advisor 实例
        """
        self._advisors = [item for item in self._advisors if item != advisor]

    def clear(self):
        """清空所有 Advisor"""
        self._advisors.clear()

    def __len__(self):
        """返回 Advisor 数量"""
        return len(self._advisors)


    def wrap_call(self, final_handler: AdvisorCallHandler) -> AdvisorCallHandler:
        """构造非流式调用的处理链"""

        def _wrap(next_handler: AdvisorCallHandler, advisor: Advisor) -> AdvisorCallHandler:
            return lambda req: advisor.handle_call(req, next_handler)

        # 从后往前逐层包裹
        return reduce(_wrap, reversed(self.advisors), final_handler)

    def wrap_stream(self, final_handler: AdvisorStreamHandler) -> AdvisorStreamHandler:
        """构造流式调用的处理链"""

        def _wrap(next_handler: AdvisorStreamHandler, advisor: Advisor) -> AdvisorStreamHandler:
            return lambda req: advisor.handle_stream(req, next_handler)

        return reduce(_wrap, reversed(self.advisors), final_handler)
