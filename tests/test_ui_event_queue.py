import threading
import time
import unittest
import unittest.mock as mock

from eflycode.core.event.ui_event_queue import UIEventQueue


class TestUIEventQueue(unittest.TestCase):
    """UIEventQueue 测试类"""

    def setUp(self):
        """设置测试环境"""
        self.ui_queue = UIEventQueue()

    def test_subscribe_and_emit(self):
        """测试订阅和发布事件"""
        handler = mock.Mock()
        self.ui_queue.subscribe("test.event", handler)
        self.ui_queue.emit("test.event", arg1="value1", arg2="value2")

        processed = self.ui_queue.process_events()
        self.assertEqual(processed, 1)
        handler.assert_called_once_with(arg1="value1", arg2="value2")

    def test_subscribe_multiple_handlers(self):
        """测试订阅多个 handler"""
        handler1 = mock.Mock()
        handler2 = mock.Mock()
        self.ui_queue.subscribe("test.event", handler1)
        self.ui_queue.subscribe("test.event", handler2)

        self.ui_queue.emit("test.event", arg="value")
        self.ui_queue.process_events()

        handler1.assert_called_once_with(arg="value")
        handler2.assert_called_once_with(arg="value")

    def test_priority(self):
        """测试 handler 优先级"""
        call_order = []

        def handler1():
            call_order.append(1)

        def handler2():
            call_order.append(2)

        def handler3():
            call_order.append(3)

        self.ui_queue.subscribe("test.event", handler1, priority=1)
        self.ui_queue.subscribe("test.event", handler2, priority=3)
        self.ui_queue.subscribe("test.event", handler3, priority=2)

        self.ui_queue.emit("test.event")
        self.ui_queue.process_events()

        self.assertEqual(call_order, [2, 3, 1])

    def test_unsubscribe(self):
        """测试取消订阅"""
        handler = mock.Mock()
        self.ui_queue.subscribe("test.event", handler)
        self.ui_queue.unsubscribe("test.event", handler)

        self.ui_queue.emit("test.event", arg="value")
        self.ui_queue.process_events()

        handler.assert_not_called()

    def test_thread_safe_emit(self):
        """测试线程安全的事件入队"""
        handler = mock.Mock()
        self.ui_queue.subscribe("test.event", handler)

        def emit_from_thread():
            for i in range(10):
                self.ui_queue.emit("test.event", index=i)

        thread = threading.Thread(target=emit_from_thread)
        thread.start()
        thread.join()

        processed = 0
        while True:
            count = self.ui_queue.process_events()
            if count == 0:
                break
            processed += count

        self.assertEqual(processed, 10)
        self.assertEqual(handler.call_count, 10)

    def test_process_events_max_events(self):
        """测试限制处理事件数量"""
        handler = mock.Mock()
        self.ui_queue.subscribe("test.event", handler)

        for i in range(5):
            self.ui_queue.emit("test.event", index=i)

        processed = self.ui_queue.process_events(max_events=3)
        self.assertEqual(processed, 3)
        self.assertEqual(handler.call_count, 3)

        processed = self.ui_queue.process_events()
        self.assertEqual(processed, 2)
        self.assertEqual(handler.call_count, 5)

    def test_clear(self):
        """测试清空队列和订阅"""
        handler = mock.Mock()
        self.ui_queue.subscribe("test.event", handler)

        self.ui_queue.emit("test.event", arg="value1")
        self.ui_queue.emit("test.event", arg="value2")

        self.ui_queue.clear()

        self.ui_queue.process_events()
        handler.assert_not_called()

        self.ui_queue.emit("test.event", arg="value3")
        self.ui_queue.process_events()
        handler.assert_not_called()

    def test_size(self):
        """测试获取队列大小"""
        self.ui_queue.emit("test.event", arg="value1")
        self.ui_queue.emit("test.event", arg="value2")
        self.ui_queue.emit("test.event", arg="value3")

        self.assertEqual(self.ui_queue.size(), 3)

        self.ui_queue.process_events(max_events=2)
        self.assertEqual(self.ui_queue.size(), 1)

    def test_debounce(self):
        """测试事件去抖"""
        ui_queue = UIEventQueue(debounce_delay=0.1)
        handler = mock.Mock()
        ui_queue.subscribe("test.event", handler)

        for i in range(5):
            ui_queue.emit("test.event", index=i)
            time.sleep(0.01)

        time.sleep(0.15)
        processed = ui_queue.process_events()

        self.assertEqual(processed, 1)
        handler.assert_called_once()
        self.assertEqual(handler.call_args[1]["index"], 4)

    def test_debounce_multiple_events(self):
        """测试多个事件类型的去抖"""
        ui_queue = UIEventQueue(debounce_delay=0.1)
        handler1 = mock.Mock()
        handler2 = mock.Mock()
        ui_queue.subscribe("event1", handler1)
        ui_queue.subscribe("event2", handler2)

        for i in range(3):
            ui_queue.emit("event1", index=i)
            ui_queue.emit("event2", index=i)
            time.sleep(0.01)

        time.sleep(0.15)
        processed = ui_queue.process_events()

        self.assertEqual(processed, 2)
        handler1.assert_called_once()
        handler2.assert_called_once()

    def test_handler_error_not_blocking(self):
        """测试 handler 错误不阻塞其他 handler"""
        def error_handler():
            raise ValueError("Test error")

        normal_handler = mock.Mock()

        self.ui_queue.subscribe("test.event", error_handler)
        self.ui_queue.subscribe("test.event", normal_handler)

        self.ui_queue.emit("test.event", arg="value")
        self.ui_queue.process_events()

        normal_handler.assert_called_once_with(arg="value")

    def test_event_order(self):
        """测试事件执行顺序"""
        call_order = []

        def handler(index):
            call_order.append(index)

        self.ui_queue.subscribe("test.event", handler)

        for i in range(5):
            self.ui_queue.emit("test.event", index=i)

        self.ui_queue.process_events()

        self.assertEqual(call_order, [0, 1, 2, 3, 4])


if __name__ == "__main__":
    unittest.main()

