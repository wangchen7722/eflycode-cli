from abc import ABC, abstractmethod
from typing import Callable
from functools import reduce

from echo.schema.llm import LLMRequest, LLMCallResponse, LLMStreamResponse

AdvisorCallHandler = Callable[[LLMRequest], LLMCallResponse]
AdvisorStreamHandler = Callable[[LLMRequest], LLMStreamResponse]

class Advisor(ABC):
    """模型请求Advisor"""

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

    def __init__(self, advisors: list[Advisor]):
        self.advisors = advisors


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


class AdvisorRegistry:
    """Advisor注册表，用于管理所有注册的Advisor类"""
    
    _instance = None
    # {name: {"class": AdvisorClass, "priority": int, "is_builtin": bool}}
    _advisors = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def register(cls, name: str, advisor_class: type, priority: int = 0, is_builtin: bool = False):
        """注册Advisor类
        
        Args:
            name: Advisor名称
            advisor_class: Advisor类
            priority: 优先级，数值越大优先级越高
            is_builtin: 是否为系统内置Advisor
        """
        if not issubclass(advisor_class, Advisor):
            raise ValueError(f"Advisor类 {advisor_class.__name__} 必须继承自 Advisor")
        
        cls._advisors[name] = {
            "class": advisor_class,
            "priority": priority,
            "is_builtin": is_builtin
        }
    
    @classmethod
    def get_advisor(cls, name: str) -> type:
        """获取指定名称的Advisor类
        
        Args:
            name: Advisor名称
            
        Returns:
            type: Advisor类
            
        Raises:
            KeyError: 当指定名称的Advisor不存在时
        """
        if name not in cls._advisors:
            raise KeyError(f"未找到名称为 '{name}' 的Advisor")
        return cls._advisors[name]["class"]
    
    def get_advisor_priority(cls, name: str) -> int:
        """获取指定名称的Advisor的优先级
        
        Args:
            name: Advisor名称
            
        Returns:
            int: Advisor的优先级
            
        Raises:
            KeyError: 当指定名称的Advisor不存在时
        """
        if name not in cls._advisors:
            raise KeyError(f"未找到名称为 '{name}' 的Advisor")
        return cls._advisors[name]["priority"]
    
    @classmethod
    def get_all_advisors(cls) -> dict:
        """获取所有注册的Advisor信息
        
        Returns:
            dict: 所有Advisor信息
        """
        return cls._advisors.copy()
    
    @classmethod
    def get_sorted_advisors(cls) -> list:
        """获取按优先级排序的Advisor列表（系统内置优先级最高）
        
        Returns:
            list: 按优先级排序的Advisor信息列表
        """
        advisors = list(cls._advisors.items())
        # 按优先级排序，系统内置的优先级最高，然后按priority数值排序
        advisors.sort(key=lambda x: (not x[1]["is_builtin"], -x[1]["priority"]))
        return advisors
    
    @classmethod
    def clear(cls):
        """清空所有注册的Advisor（主要用于测试）"""
        cls._advisors.clear()


def register_advisor(name: str = None, priority: int = 0, is_builtin: bool = False):
    """Advisor注册装饰器
    
    Args:
        name: Advisor名称，如果不指定则使用类名
        priority: 优先级，数值越大优先级越高
        is_builtin: 是否为系统内置Advisor，系统内置的优先级最高
        
    Returns:
        装饰器函数
        
    Example:
        @register_advisor("tool_call", priority=10, is_builtin=True)
        class ToolCallAdvisor(Advisor):
            pass
            
        @register_advisor()  # 使用类名作为注册名
        class CustomAdvisor(Advisor):
            pass
    """
    def decorator(advisor_class: type):
        advisor_name = name if name is not None else advisor_class.__name__
        AdvisorRegistry.register(advisor_name, advisor_class, priority, is_builtin)
        return advisor_class
    
    return decorator