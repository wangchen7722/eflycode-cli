from abc import ABC, abstractmethod
from enum import Enum
from typing import Callable
import threading

from eflycode.util.event_bus import EventBus
from eflycode.util.logger import logger


class UIEvent(Enum):
    """
    UI事件基类
    """
    ...


class BaseUIController(ABC):
    """基础UI控制器"""

    def __init__(self, event_bus: EventBus, supported_event_classes: list[type[UIEvent]]) -> None:
        self.event_bus: EventBus = event_bus
        self.__lock = threading.Lock()
        self.__custom_event_handlers: dict[UIEvent, Callable[[dict], None]] = {}

        for event_class in supported_event_classes:
            self.__bind_events(event_class)

    def __handle_event(self, event: UIEvent, data: dict) -> None:
        """处理事件"""
        with self.__lock:
            handler = self.__custom_event_handlers.get(event)
        if handler:
            handler(data)
        else:
            handler_fn = f"_handle_{event.name.lower()}"
            if hasattr(self, handler_fn):
                getattr(self, handler_fn)(data)
            else:
                logger.warning(f"未注册处理函数的事件 {event}")

    def __bind_events(self, event_class: type[UIEvent]):
        """绑定事件"""
        for event in event_class:
            self.event_bus.subscribe(event, self.__handle_event)

    def register_event_handler(self, event: UIEvent, handler: Callable[[dict], None]) -> None:
        """注册事件处理函数"""
        with self.__lock:
            if event in self.__custom_event_handlers:
                raise ValueError(f"事件 {event} 已注册处理函数")
            self.__custom_event_handlers[event] = handler

    @abstractmethod
    def initialize(self):
        """初始化 UI 控制器"""
        ...

    @abstractmethod
    def run(self):
        """运行UI控制器"""
        ...

    @abstractmethod
    def stop(self):
        """停止UI控制器"""
        ...

    @abstractmethod
    def shutdown(self):
        """关闭UI控制器"""
        ...
