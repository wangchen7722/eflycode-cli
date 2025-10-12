from typing import DefaultDict, List, Callable, Optional
from collections import defaultdict
import queue
import threading

from echo.util.logger import logger


class EventBus:
    """
    事件总线
    """
    
    def __init__(self) -> None:
        self._subscribers: DefaultDict[str, List[Callable[..., None]]] = defaultdict(list)
        self._queue = queue.Queue()
        self._running = True
        threading.Thread(target=self._worker, daemon=True).start()
        
    def subscribe(self, event: str, listener: Callable[..., None]) -> None:
        """
        订阅事件
        """
        self._subscribers[event].append(listener)
        
    def unsubscribe(self, event: str, listener: Callable[..., None]) -> None:
        """
        取消订阅事件
        """
        self._subscribers[event].remove(listener)
        
    def emit(self, event: str, data: Optional[dict] = None) -> None:
        """
        触发事件
        """
        self._queue.put((event, data or {}))
            
    def _worker(self):
        """
        后台线程，从队列中取出事件并处理
        """
        while self._running:
            try:
                event, data = self._queue.get(timeout=1)
            except queue.Empty:
                continue
            
            for listener in self._subscribers.get(event, []):
                try:
                    listener(**data or {})
                except Exception as e:
                    logger.exception(f"订阅者 {listener.__name__} 处理事件 {event}时 触发异常: {e}")
                    continue
                
    def close(self):
        """
        关闭事件总线
        """
        self._running = False
