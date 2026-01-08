import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List

logger = logging.getLogger(__name__)

# 事件总线配置常量
EVENT_BUS_MAX_WORKERS = 10


class HandlerInfo:
    """Handler 信息"""

    def __init__(self, event_type: str, handler: Callable, priority: int = 0):
        """初始化 Handler 信息

        Args:
            event_type: 事件类型
            handler: 事件处理函数
            priority: 优先级，数值越大优先级越高
        """
        self.event_type = event_type
        self.handler = handler
        self.priority = priority

    def __eq__(self, other):
        """判断两个 HandlerInfo 是否相等"""
        if not isinstance(other, HandlerInfo):
            return False
        return self.event_type == other.event_type and self.handler is other.handler

    def __hash__(self):
        """计算哈希值"""
        return hash((self.event_type, id(self.handler)))


class EventBus:
    """事件总线，使用线程池实现异步非阻塞事件处理"""

    def __init__(self, max_workers: int = EVENT_BUS_MAX_WORKERS):
        """初始化事件总线

        Args:
            max_workers: 线程池最大工作线程数
        """
        self._handlers: Dict[str, List[HandlerInfo]] = {}
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._shutdown = False

    def subscribe(self, event_type: str, handler: Callable, priority: int = 0) -> None:
        """订阅事件

        Args:
            event_type: 事件类型
            handler: 事件处理函数，签名为 def handler(**kwargs) -> None
            priority: 优先级，数值越大优先级越高，默认 0
        """
        if self._shutdown:
            raise RuntimeError("EventBus has been shut down")

        if event_type not in self._handlers:
            self._handlers[event_type] = []

        handler_info = HandlerInfo(event_type, handler, priority)
        if handler_info not in self._handlers[event_type]:
            self._handlers[event_type].append(handler_info)
            self._handlers[event_type].sort(key=lambda x: x.priority, reverse=True)

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """取消订阅事件

        Args:
            event_type: 事件类型
            handler: 要取消的事件处理函数
        """
        if event_type not in self._handlers:
            return

        handler_info = HandlerInfo(event_type, handler)
        if handler_info in self._handlers[event_type]:
            self._handlers[event_type].remove(handler_info)

    def emit(self, event_type: str, **kwargs) -> None:
        """发布事件

        异步非阻塞，立即返回，不等待 handler 执行完成

        Args:
            event_type: 事件类型
            **kwargs: 事件参数
        """
        if self._shutdown:
            return

        if event_type not in self._handlers:
            return

        handlers = self._handlers[event_type].copy()

        for handler_info in handlers:
            self._executor.submit(self._execute_handler, handler_info.handler, kwargs)

    def _execute_handler(self, handler: Callable, kwargs: dict) -> None:
        """在线程池中执行 handler

        Args:
            handler: 事件处理函数
            kwargs: 事件参数
        """
        try:
            handler(**kwargs)
        except Exception as e:
            logger.error(f"Error executing event handler {handler.__name__}: {e}", exc_info=True)

    def clear(self) -> None:
        """清空所有订阅"""
        self._handlers.clear()

    def shutdown(self, wait: bool = True) -> None:
        """关闭线程池

        Args:
            wait: 是否等待所有任务完成
        """
        self._shutdown = True
        self._executor.shutdown(wait=wait)

