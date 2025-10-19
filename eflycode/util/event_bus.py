import functools
from typing import DefaultDict, List, Callable, Optional, NamedTuple
from collections import defaultdict
import time
import queue
import threading
from concurrent.futures import ThreadPoolExecutor

from eflycode.util.logger import logger


class Sub(NamedTuple):
    listener: Callable[..., None]
    threaded: bool
    pass_event: bool


class EventBus:
    """
    事件总线
    """
    
    def __init__(self, max_queue_size: int = 10000, max_workers: int = 10) -> None:
        self._subscribers: DefaultDict[str, List[Callable[..., None]]] = defaultdict(list)
        self._queue = queue.Queue(maxsize=max_queue_size)
        self._pool = ThreadPoolExecutor(max_workers=max_workers)
        self._running = True

        self._dispatcher = threading.Thread(target=self._worker, daemon=True, name="eventbus-dispatcher")
        self._dispatcher.start()
        
    def subscribe(self, event: str, listener: Callable[..., None], *, threaded: bool = False, pass_event: bool = True) -> None:
        """
        订阅事件
        
        Args:
            event: 事件名称
            listener: 事件处理回调函数
            threaded: 是否在线程池中执行回调
            pass_event: 是否传递事件名给回调，True 时签名需为 (event, data)，False 时签名为 (data)
        """
        self._subscribers[event].append(Sub(listener, threaded=threaded, pass_event=pass_event))
        
    def unsubscribe(self, event: str, listener: Callable[..., None]) -> None:
        """
        取消订阅事件
        
        Args:
            event: 事件名称
            listener: 需要取消的回调函数
        """
        subs = self._subscribers.get(event, [])
        self._subscribers[event] = [sub for sub in subs if sub.listener != listener]
        
    def emit(self, event: str, data: Optional[dict] = None) -> None:
        """
        触发事件
        
        Args:
            event: 事件名称
            data: 事件数据，默认为空字典
        
        Exceptions:
            无显式抛出，队列满时记录警告日志
        """
        try:
            self._queue.put((event, data or {}))
        except queue.Full:
            logger.warning(f"事件队列已满，事件 {event} 被丢弃")

    def emit_sync(self, event: str, data: Optional[dict] = None) -> None:
        """
        同步触发事件, 直接调用订阅者
        
        Args:
            event: 事件名称
            data: 事件数据，默认为空字典
        """
        self._dispatch_to_listeners(event, data or {})
            
    def _worker(self):
        """
        后台线程，从队列中取出事件并处理
        
        Exceptions:
            事件分发中的异常会被捕获并记录日志，不会中断线程
        """
        while self._running:
            try:
                event, data = self._queue.get(timeout=1)
            except queue.Empty:
                continue
            
            try:
                # 仅分发一次，由 _dispatch_to_listeners 负责遍历订阅者
                self._dispatch_to_listeners(event, data)
            except Exception as e:
                logger.exception(f"分发事件 {event} 时触发异常: {e}")
            finally:
                # 标记当前事件处理完成
                try:
                    self._queue.task_done()
                except Exception:
                    pass

    def _dispatch_to_listeners(self, event: str, data: dict) -> None:
        """
        调用订阅者
        
        Args:
            event: 事件名称
            data: 事件数据
        """
        subs = list(self._subscribers.get(event, []))
        for sub in subs:
            fn = sub.listener
            if sub.pass_event:
                call = functools.partial(fn, event, data)
            else:
                call = functools.partial(fn, data)

            if sub.threaded:
                self._pool.submit(self._safe_call, fn, call, event)
            else:
                self._safe_call(fn, call, event)

    @staticmethod
    def _safe_call(fn: Callable[..., None], call: Callable[[], None], event: str) -> None:
        """
        安全调用函数，捕获异常
        
        Args:
            fn: 原始回调函数
            call: 已封装好的调用闭包
            event: 当前事件名称
        """
        try:
            call()
        except Exception as e:
            logger.exception(f"调用函数 {fn.__name__} 时触发异常: {e}")

    def _has_active_workers(self) -> bool:
        """检测线程池是否还有活跃任务"""
        return any(t.is_alive() for t in getattr(self._pool, "_threads", []))
                
    def close(self, wait: bool = True, timeout: Optional[float] = 2.0):
        """
        关闭事件总线
        
        Args:
            wait: 是否等待线程退出
            timeout: 等待分发线程退出的超时时间（秒）
        """
        self._running = False
        if wait and self._dispatcher.is_alive():
            self._dispatcher.join(timeout=timeout)
        # 线程池关闭，带超时控制
        if wait:
            # 先通知停止接受新任务
            self._pool.shutdown(wait=False)
            start = time.monotonic()
            while True:
                # 检查所有 worker 是否都已结束
                if not self._has_active_workers():
                    break
                if time.monotonic() - start > (timeout or 2.0):
                    # 超时退出，不再等待
                    logger.warning("ThreadPoolExecutor 未在超时内完全退出，强制关闭。")
                    break
                time.sleep(0.05)
        else:
            self._pool.shutdown(wait=False)
            
