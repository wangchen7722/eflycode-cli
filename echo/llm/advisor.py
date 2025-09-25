from abc import ABC, abstractmethod
from typing import Callable, Union, List, Optional, Dict, Any, Type
from functools import reduce
from pydantic import BaseModel, Field

from echo.util.logger import logger
from echo.schema.llm import LLMRequest, LLMCallResponse, LLMStreamResponse

AdvisorCallHandler = Callable[[LLMRequest], LLMCallResponse]
AdvisorStreamHandler = Callable[[LLMRequest], LLMStreamResponse]


class AdvisorItem(BaseModel):
    """封装 Advisor 实例和优先级信息的数据类
    
    Attributes:
        advisor: Advisor 实例
        priority: 优先级，数值越大优先级越高
        is_builtin: 是否为系统内置 Advisor
        clazz: Advisor 类
    """
    advisor: Any = Field(description="Advisor 实例")
    priority: int = Field(default=0, description="优先级，数值越大优先级越高")
    is_builtin: bool = Field(default=False, description="是否为系统内置 Advisor")
    clazz: Type["Advisor"] = Field(default=None, description="Advisor 类")
    
    class Config:
        arbitrary_types_allowed = True
    
    def __lt__(self, other):
        """支持排序，系统内置优先级最高，然后按 priority 数值排序"""
        if not isinstance(other, AdvisorItem):
            return NotImplemented
        # 系统内置的优先级最高，然后按 priority 数值排序（数值越大优先级越高）
        return (not self.is_builtin, -self.priority) < (not other.is_builtin, -other.priority)


class Advisor(ABC):
    """模型请求Advisor"""
    
    # 是否为系统内置 Advisor，子类可以重写此属性
    is_builtin: bool = False

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

    def __init__(self, advisors: Union[List[Advisor], List[AdvisorItem]] = None):
        """初始化 AdvisorChain
        
        Args:
            advisors: Advisor 列表，可以是 Advisor 实例列表或 AdvisorItem 列表
        """
        self._advisor_items: List[AdvisorItem] = []
        if advisors:
            for advisor in advisors:
                self.add_advisor(advisor)

    @property
    def advisors(self) -> List[Advisor]:
        """获取按优先级排序的 Advisor 列表"""
        return [item.advisor for item in self._get_sorted_advisor_items()]

    def _get_sorted_advisor_items(self) -> List[AdvisorItem]:
        """获取按优先级排序的 AdvisorItem 列表"""
        return sorted(self._advisor_items)

    def add_advisor(self, advisor: Union[Advisor, AdvisorItem], priority: int = 0):
        """添加 Advisor 到链中
        
        Args:
            advisor: Advisor 实例或 AdvisorItem 实例
            priority: 优先级，仅在 advisor 为 Advisor 实例时有效
            is_builtin: 是否为系统内置，仅在 advisor 为 Advisor 实例时有效
        """
        if isinstance(advisor, AdvisorItem):
            self._advisor_items.append(advisor)
        else:
            advisor_item = AdvisorItem(
                advisor=advisor,
                priority=priority,
                is_builtin=getattr(advisor, "is_builtin", False)
            )
            self._advisor_items.append(advisor_item)

    def remove_advisor(self, advisor: Advisor):
        """从链中移除指定的 Advisor
        
        Args:
            advisor: 要移除的 Advisor 实例
        """
        self._advisor_items = [item for item in self._advisor_items if item.advisor != advisor]

    def clear(self):
        """清空所有 Advisor"""
        self._advisor_items.clear()

    def __len__(self):
        """返回 Advisor 数量"""
        return len(self._advisor_items)


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
    # {name: AdvisorItem}
    _advisors: Dict[str, AdvisorItem] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def register(cls, name: str, advisor_item: AdvisorItem):
        """注册Advisor类
        
        Args:
            name: Advisor名称
            advisor_item: AdvisorItem实例
        """
        if not issubclass(advisor_item.clazz, Advisor):
            raise ValueError(f"Advisor类 {advisor_item.clazz.__name__} 必须继承自 Advisor")
        
        cls._advisors[name] = advisor_item
    
    @classmethod
    def get_advisor(cls, name: str) -> Type[Advisor]:
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
        return cls._advisors[name].clazz
    
    @classmethod
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
        return cls._advisors[name].priority
    
    @classmethod
    def get_sorted_advisors(cls) -> list:
        """获取按优先级排序的Advisor列表（系统内置优先级最高）
        
        Returns:
            list: 按优先级排序的Advisor信息列表
        """
        advisors = list(cls._advisors.items())
        # 按优先级排序，按priority数值排序
        advisors.sort(key=lambda x: -x[1].priority)
        return advisors
    
    @classmethod
    def clear(cls):
        """清空所有注册的Advisor（主要用于测试）"""
        cls._advisors.clear()


def register_advisor(name: str = None, priority: int = 0):
    """Advisor注册装饰器
    
    Args:
        name: Advisor名称，如果不指定则使用类名
        priority: 优先级，数值越大优先级越高
        is_builtin: 是否为系统内置Advisor，系统内置的优先级最高
        
    Returns:
        装饰器函数
        
    Example:
        @register_advisor("tool_call", priority=10)
        class ToolCallAdvisor(Advisor):
            is_builtin = True
            pass
            
        @register_advisor()  # 使用类名作为注册名
        class CustomAdvisor(Advisor):
            pass
    """
    def decorator(advisor_class: type):
        advisor_name = name if name is not None else advisor_class.__name__
        
        # 优先使用类属性，如果没有则使用装饰器参数
        advisor_item = AdvisorItem(
            name=advisor_name,
            priority=priority,
            is_builtin=getattr(advisor_class, "is_builtin", False),
            clazz=advisor_class
        )
        
        AdvisorRegistry.register(advisor_name, advisor_item)
        return advisor_class
    
    return decorator