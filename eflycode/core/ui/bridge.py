from typing import Callable, List, Optional

from eflycode.core.event.event_bus import EventBus
from eflycode.core.ui.ui_event_queue import UIEventQueue
from eflycode.core.utils.logger import logger


class EventBridge:
    """事件桥接器，将 EventBus 的事件转发到 UIEventQueue

    职责：
    - 订阅 EventBus 的事件
    - 在 handler 内部调用 ui_queue.emit(...) 转发事件
    - EventBus 不需要知道 UI 的存在
    """

    def __init__(
        self,
        event_bus: EventBus,
        ui_queue: UIEventQueue,
        event_types: Optional[List[str]] = None,
    ):
        """初始化事件桥接器

        Args:
            event_bus: 源事件总线
            ui_queue: 目标 UI 事件队列
            event_types: 要桥接的事件类型列表，None 表示桥接所有事件
        """
        self._event_bus = event_bus
        self._ui_queue = ui_queue
        self._event_types = event_types
        self._active = False
        self._handlers: List[tuple[str, Callable]] = []

    def start(self) -> None:
        """开始桥接"""
        if self._active:
            return

        self._active = True

        if self._event_types is None:
            self._subscribe_all_events()
        else:
            for event_type in self._event_types:
                self._subscribe_event(event_type)

    def _subscribe_all_events(self) -> None:
        """订阅所有事件类型

        通过监听 EventBus 的内部状态变化来实现，或者使用通配符机制
        由于 EventBus 不支持通配符，这里采用动态订阅的方式
        当有新事件类型时，需要手动添加
        """
        logger.warning(
            "EventBridge: 桥接所有事件类型需要手动订阅，建议明确指定 event_types"
        )

    def _subscribe_event(self, event_type: str) -> None:
        """订阅单个事件类型

        Args:
            event_type: 事件类型
        """
        handler = self._create_bridge_handler(event_type)
        self._event_bus.subscribe(event_type, handler)
        self._handlers.append((event_type, handler))

    def _create_bridge_handler(self, event_type: str) -> Callable:
        """创建桥接 handler

        Args:
            event_type: 事件类型

        Returns:
            Callable: 桥接 handler 函数
        """
        def bridge_handler(**kwargs) -> None:
            """桥接 handler，转发事件到 UIQueue"""
            try:
                self._ui_queue.emit(event_type, **kwargs)
            except Exception as e:
                logger.error(f"Error bridging event {event_type}: {e}", exc_info=True)

        return bridge_handler

    def stop(self) -> None:
        """停止桥接"""
        if not self._active:
            return

        for event_type, handler in self._handlers:
            try:
                self._event_bus.unsubscribe(event_type, handler)
            except Exception as e:
                logger.error(f"Error unsubscribing event {event_type}: {e}", exc_info=True)

        self._handlers.clear()
        self._active = False

    def add_event_type(self, event_type: str) -> None:
        """动态添加要桥接的事件类型

        Args:
            event_type: 事件类型
        """
        if not self._active:
            return

        if event_type in [et for et, _ in self._handlers]:
            return

        self._subscribe_event(event_type)

    def remove_event_type(self, event_type: str) -> None:
        """移除要桥接的事件类型

        Args:
            event_type: 事件类型
        """
        handlers_to_remove = [
            (et, h) for et, h in self._handlers if et == event_type
        ]

        for event_type, handler in handlers_to_remove:
            try:
                self._event_bus.unsubscribe(event_type, handler)
                self._handlers.remove((event_type, handler))
            except Exception as e:
                logger.error(f"Error removing event type {event_type}: {e}", exc_info=True)

    @property
    def is_active(self) -> bool:
        """获取桥接器是否处于活动状态

        Returns:
            bool: 是否活动
        """
        return self._active

