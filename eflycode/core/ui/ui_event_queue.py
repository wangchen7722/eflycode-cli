import queue
import threading
import time
from typing import Callable, Dict, List, Optional

from eflycode.core.utils.logger import logger


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


class QueuedEvent:
    """队列中的事件"""

    def __init__(self, event_type: str, kwargs: dict, timestamp: float):
        """初始化队列事件

        Args:
            event_type: 事件类型
            kwargs: 事件参数
            timestamp: 事件时间戳
        """
        self.event_type = event_type
        self.kwargs = kwargs
        self.timestamp = timestamp


class UIEventQueue:
    """UI 事件队列，用于主线程顺序执行的事件处理

    职责：
    - 线程安全的事件入队
    - 主线程按序消费
    - 可选的事件合并/去抖
    """

    def __init__(self, debounce_delay: Optional[float] = None):
        """初始化 UI 事件队列

        Args:
            debounce_delay: 去抖延迟时间，None 表示不去抖
        """
        self._handlers: Dict[str, List[HandlerInfo]] = {}
        self._event_queue: queue.Queue = queue.Queue()
        self._debounce_delay = debounce_delay
        self._debounce_timers: Dict[str, Optional[threading.Timer]] = {}
        self._debounce_pending: Dict[str, QueuedEvent] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, handler: Callable, priority: int = 0) -> None:
        """订阅事件

        Args:
            event_type: 事件类型
            handler: 事件处理函数，签名为 def handler(**kwargs) -> None
            priority: 优先级，数值越大优先级越高，默认 0
        """
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

        事件会被放入队列，等待主线程调用 process_events 时处理

        Args:
            event_type: 事件类型
            **kwargs: 事件参数
        """
        if self._debounce_delay is not None:
            self._emit_with_debounce(event_type, kwargs)
        else:
            queued_event = QueuedEvent(event_type, kwargs, time.time())
            self._event_queue.put(queued_event)

    def _emit_with_debounce(self, event_type: str, kwargs: dict) -> None:
        """带去抖的事件发布

        Args:
            event_type: 事件类型
            kwargs: 事件参数
        """
        with self._lock:
            if event_type in self._debounce_timers and self._debounce_timers[event_type] is not None:
                self._debounce_timers[event_type].cancel()

            queued_event = QueuedEvent(event_type, kwargs, time.time())
            self._debounce_pending[event_type] = queued_event

            def flush_event():
                with self._lock:
                    if event_type in self._debounce_pending:
                        event = self._debounce_pending.pop(event_type)
                        self._event_queue.put(event)
                    self._debounce_timers[event_type] = None

            timer = threading.Timer(self._debounce_delay, flush_event)
            self._debounce_timers[event_type] = timer
            timer.start()

    def process_events(self, max_events: Optional[int] = None, time_budget_ms: Optional[int] = None) -> int:
        """处理队列中的事件

        顺序处理队列中的事件，按照优先级执行 handler

        Args:
            max_events: 最多处理的事件数量，None 表示处理所有事件
            time_budget_ms: 时间预算（毫秒），超时后立即返回

        Returns:
            int: 实际处理的事件数量
        """
        start_time = time.time() if time_budget_ms is not None else None
        processed = 0

        while True:
            if max_events is not None and processed >= max_events:
                break

            if start_time is not None:
                elapsed_ms = (time.time() - start_time) * 1000
                if elapsed_ms >= time_budget_ms:
                    break

            try:
                queued_event = self._event_queue.get_nowait()
            except queue.Empty:
                break

            self._execute_event(queued_event)
            processed += 1

        return processed

    def _execute_event(self, queued_event: QueuedEvent) -> None:
        """执行单个事件

        Args:
            queued_event: 队列中的事件
        """
        event_type = queued_event.event_type
        if event_type not in self._handlers:
            return

        handlers = self._handlers[event_type].copy()

        for handler_info in handlers:
            try:
                handler_info.handler(**queued_event.kwargs)
            except Exception as e:
                logger.error(
                    f"Error executing UI event handler {handler_info.handler.__name__}: {e}",
                    exc_info=True,
                )

    def clear(self) -> None:
        """清空队列和订阅"""
        with self._lock:
            for timer in self._debounce_timers.values():
                if timer is not None:
                    timer.cancel()
            self._debounce_timers.clear()
            self._debounce_pending.clear()

        while not self._event_queue.empty():
            try:
                self._event_queue.get_nowait()
            except queue.Empty:
                break

        self._handlers.clear()

    def size(self) -> int:
        """获取队列中待处理的事件数量

        Returns:
            int: 队列大小
        """
        return self._event_queue.qsize()

