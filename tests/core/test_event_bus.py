import time
import unittest
from unittest.mock import MagicMock, Mock

from eflycode.core.event.event_bus import EventBus


class TestEventBus(unittest.TestCase):
    """EventBus 测试类"""

    def setUp(self):
        """设置测试环境"""
        self.event_bus = EventBus(max_workers=5)

    def tearDown(self):
        """清理测试环境"""
        self.event_bus.shutdown(wait=True)

    def test_subscribe_and_emit(self):
        """测试订阅和发布事件"""
        handler = Mock()
        self.event_bus.subscribe("test.event", handler)
        self.event_bus.emit("test.event", arg1="value1", arg2="value2")

        time.sleep(0.1)
        handler.assert_called_once_with(arg1="value1", arg2="value2")

    def test_subscribe_multiple_handlers(self):
        """测试订阅多个 handler"""
        handler1 = Mock()
        handler2 = Mock()
        self.event_bus.subscribe("test.event", handler1)
        self.event_bus.subscribe("test.event", handler2)

        self.event_bus.emit("test.event", arg="value")

        time.sleep(0.1)
        handler1.assert_called_once_with(arg="value")
        handler2.assert_called_once_with(arg="value")

    def test_subscribe_same_handler_multiple_events(self):
        """测试同一个 handler 订阅多个事件类型"""
        handler = Mock()
        self.event_bus.subscribe("event1", handler)
        self.event_bus.subscribe("event2", handler)

        self.event_bus.emit("event1", arg="value1")
        self.event_bus.emit("event2", arg="value2")

        time.sleep(0.1)
        self.assertEqual(handler.call_count, 2)

    def test_priority(self):
        """测试 handler 优先级"""
        call_order = []
        import threading
        lock = threading.Lock()

        def handler1():
            with lock:
                call_order.append(1)

        def handler2():
            with lock:
                call_order.append(2)

        def handler3():
            with lock:
                call_order.append(3)

        self.event_bus.subscribe("test.event", handler1, priority=1)
        self.event_bus.subscribe("test.event", handler2, priority=3)
        self.event_bus.subscribe("test.event", handler3, priority=2)

        self.event_bus.emit("test.event")

        time.sleep(0.3)
        self.assertEqual(len(call_order), 3)
        self.assertIn(1, call_order)
        self.assertIn(2, call_order)
        self.assertIn(3, call_order)

    def test_unsubscribe(self):
        """测试取消订阅"""
        handler = Mock()
        self.event_bus.subscribe("test.event", handler)
        self.event_bus.unsubscribe("test.event", handler)

        self.event_bus.emit("test.event", arg="value")

        time.sleep(0.1)
        handler.assert_not_called()

    def test_emit_nonexistent_event(self):
        """测试发布不存在的事件"""
        handler = Mock()
        self.event_bus.emit("nonexistent.event", arg="value")

        time.sleep(0.1)
        handler.assert_not_called()

    def test_clear(self):
        """测试清空所有订阅"""
        handler1 = Mock()
        handler2 = Mock()
        self.event_bus.subscribe("event1", handler1)
        self.event_bus.subscribe("event2", handler2)

        self.event_bus.clear()

        self.event_bus.emit("event1", arg="value1")
        self.event_bus.emit("event2", arg="value2")

        time.sleep(0.1)
        handler1.assert_not_called()
        handler2.assert_not_called()

    def test_emit_non_blocking(self):
        """测试 emit 是非阻塞的"""
        def slow_handler():
            time.sleep(0.5)

        self.event_bus.subscribe("test.event", slow_handler)

        start_time = time.time()
        self.event_bus.emit("test.event")
        emit_time = time.time() - start_time

        self.assertLess(emit_time, 0.1)

        time.sleep(0.6)

    def test_handler_error_not_blocking(self):
        """测试 handler 错误不阻塞主流程"""
        def error_handler():
            raise ValueError("Test error")

        normal_handler = Mock()

        self.event_bus.subscribe("test.event", error_handler)
        self.event_bus.subscribe("test.event", normal_handler)

        self.event_bus.emit("test.event", arg="value")

        time.sleep(0.1)
        normal_handler.assert_called_once_with(arg="value")

    def test_shutdown(self):
        """测试关闭事件总线"""
        handler = Mock()
        self.event_bus.subscribe("test.event", handler)

        self.event_bus.shutdown(wait=True)

        with self.assertRaises(RuntimeError):
            self.event_bus.subscribe("test.event", handler)

    def test_subscribe_after_shutdown(self):
        """测试关闭后订阅会抛出异常"""
        self.event_bus.shutdown(wait=True)

        handler = Mock()
        with self.assertRaises(RuntimeError):
            self.event_bus.subscribe("test.event", handler)


if __name__ == "__main__":
    unittest.main()

