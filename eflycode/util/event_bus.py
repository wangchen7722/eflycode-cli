from __future__ import annotations

import functools

from typing import Any, DefaultDict, Generic, List, Callable, Optional, TypeVar
from collections import defaultdict
from dataclasses import dataclass
import time
import queue
import threading
from concurrent.futures import ThreadPoolExecutor

from eflycode.util.logger import logger


Listener = Callable[..., None]
Dispatcher = Callable[[Callable[[], None]], None]


TEvent = TypeVar("TEvent", bound=str)
TPayload = TypeVar("TPayload")


@dataclass(frozen=True, slots=True)
class _Subscription:
    """
    Immutable subscription descriptor used to describe delivery semantics.
    """

    listener: Listener
    threaded: bool
    dispatcher: Optional[Dispatcher]


class EventBus(Generic[TEvent, TPayload]):
    """
    Concurrent event bus with thread-safe publish/subscribe semantics.
    """
    
    def __init__(self, max_queue_size: int = 10000, max_workers: int = 10) -> None:
        """
        Initialize dispatcher, subscription registry, and worker pool.

        Arguments:
            max_queue_size: Upper bound for buffered events.
            max_workers: Thread pool size for asynchronous callbacks.
        Return Values:
            None
        Raised Exceptions:
            ValueError: Propagated from queue or ThreadPoolExecutor when misconfigured.
        """
        self._subscribers: DefaultDict[TEvent, List[_Subscription]] = defaultdict(list)
        self._queue: queue.Queue[tuple[TEvent, Any]] = queue.Queue(maxsize=max_queue_size)
        self._pool = ThreadPoolExecutor(max_workers=max_workers)
        self._running = True
        # RLock keeps reentrancy simple when a subscribed handler manages subscriptions.
        self._lock = threading.RLock()

        self._dispatcher = threading.Thread(target=self._worker, daemon=True, name="eventbus-dispatcher")
        self._dispatcher.start()
        
    def subscribe(
        self,
        event: TEvent,
        listener: Callable[..., None],
        *,
        threaded: bool = False,
        dispatcher: Optional[Dispatcher] = None,
    ) -> None:
        """
        Register a listener for an event.

        Arguments:
            event: Event identifier.
            listener: Callback to invoke.
            threaded: Execute callback inside the worker pool when True.
            dispatcher: Optional callable that enqueues listener execution onto an external loop. If provided, it
                takes precedence over the threaded flag.
        Return Values:
            None
        Raised Exceptions:
            ValueError: When event key is invalid.
        """
        with self._lock:
            self._subscribers[event].append(
                _Subscription(listener=listener, threaded=threaded, dispatcher=dispatcher)
            )
        
    def unsubscribe(self, event: TEvent, listener: Callable[..., None]) -> None:
        """
        Remove a previously registered listener.

        Arguments:
            event: Event identifier.
            listener: Callback to remove.
        Return Values:
            None
        Raised Exceptions:
            ValueError: When event identifier is invalid.
        """
        with self._lock:
            subs = self._subscribers.get(event, [])
            self._subscribers[event] = [sub for sub in subs if sub.listener != listener]
        
    def emit(self, event: TEvent, data: Optional[TPayload] = None) -> None:
        """
        Enqueue an event for asynchronous dispatch.

        Arguments:
            event: Event identifier.
            data: Payload to pass into listeners.
        Return Values:
            None
        Raised Exceptions:
            queue.Full: Logged when the buffer is saturated (event is dropped).
        """
        try:
            payload: Any = data if data is not None else {}
            self._queue.put((event, payload))
        except queue.Full:
            logger.warning("Event queue is full, dropped event %s", event)

    def emit_sync(self, event: TEvent, data: Optional[TPayload] = None) -> None:
        """
        Dispatch an event immediately in the caller thread.

        Arguments:
            event: Event identifier.
            data: Payload to pass into listeners.
        Return Values:
            None
        Raised Exceptions:
            Exception: Propagates from listener if not handled inside _safe_call.
        """
        payload: Any = data if data is not None else {}
        self._dispatch_to_listeners(event, payload)
              
    def _worker(self):
        """
        Background loop that drains the queue and dispatches events.
        """
        while self._running:
            try:
                event, data = self._queue.get(timeout=1)
            except queue.Empty:
                continue
            
            try:
                self._dispatch_to_listeners(event, data)
            except Exception as e:
                logger.exception("Unhandled exception raised when dispatching %s: %s", event, e)
            finally:
                try:
                    self._queue.task_done()
                except Exception:
                    pass

    def _dispatch_to_listeners(self, event: TEvent, data: Any) -> None:
        """
        Fan out the event to every subscriber snapshot.

        Arguments:
            event: Event identifier.
            data: Payload to pass into listeners.
        Return Values:
            None
        Raised Exceptions:
            Exception: Exceptions inside listener are logged but suppressed.
        """
        with self._lock:
            subs = list(self._subscribers.get(event, []))
        
        if not subs:
            return
            
        for sub in subs:
            try:
                call = functools.partial(sub.listener, event, data)

                if sub.dispatcher:
                    sub.dispatcher(lambda: self._safe_call(sub.listener, call, event))
                elif sub.threaded:
                    self._pool.submit(self._safe_call, sub.listener, call, event)
                else:
                    self._safe_call(sub.listener, call, event)
            except Exception as e:
                logger.exception("Failed to dispatch %s to %s: %s", event, sub.listener, e)

    @staticmethod
    def _safe_call(fn: Callable[..., None], call: Callable[[], None], event: str) -> None:
        """
        Execute the prepared call and trap exceptions.

        Arguments:
            fn: Raw listener for logging context.
            call: Prepared invocation closure.
            event: Event identifier used for context logging.
        Return Values:
            None
        Raised Exceptions:
            None (errors are logged).
        """
        try:
            call()
        except Exception as e:
            logger.exception("Listener %s failed while handling %s: %s", fn.__name__, event, e)

    def _has_active_workers(self) -> bool:
        """
        Determine whether the worker pool still owns running threads.
        """
        return any(t.is_alive() for t in getattr(self._pool, "_threads", []))
                
    def close(self, wait: bool = True, timeout: Optional[float] = 2.0):
        """
        Shut down the queue worker and thread pool.

        Arguments:
            wait: Block until background threads terminate when True.
            timeout: Upper bound in seconds for graceful shutdown.
        Return Values:
            None
        Raised Exceptions:
            TimeoutError: Implicitly raised when the dispatcher join exceeds timeout.
        """
        self._running = False
        if wait and self._dispatcher.is_alive():
            self._dispatcher.join(timeout=timeout)
        if wait:
            self._pool.shutdown(wait=False)
            start = time.monotonic()
            while True:
                if not self._has_active_workers():
                    break
                if time.monotonic() - start > (timeout or 2.0):
                    logger.warning("Thread pool failed to stop before timeout; forcing shutdown.")
                    break
                time.sleep(0.05)
        else:
            self._pool.shutdown(wait=False)
            
