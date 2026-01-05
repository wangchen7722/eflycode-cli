import time
import unittest
import unittest.mock as mock

from eflycode.core.ui.bridge import EventBridge
from eflycode.core.event.event_bus import EventBus
from eflycode.core.ui.ui_event_queue import UIEventQueue


class TestEventBridge(unittest.TestCase):
    """EventBridge 测试类"""

    def setUp(self):
        """设置测试环境"""
        self.event_bus = EventBus()
        self.ui_queue = UIEventQueue()

    def tearDown(self):
        """清理测试环境"""
        self.event_bus.shutdown(wait=True)

    def test_bridge_single_event(self):
        """测试桥接单个事件"""
        bridge = EventBridge(
            event_bus=self.event_bus,
            ui_queue=self.ui_queue,
            event_types=["test.event"],
        )
        bridge.start()

        handler = mock.Mock()
        self.ui_queue.subscribe("test.event", handler)

        self.event_bus.emit("test.event", arg1="value1", arg2="value2")

        time.sleep(0.1)
        self.ui_queue.process_events()

        handler.assert_called_once_with(arg1="value1", arg2="value2")
        bridge.stop()

    def test_bridge_multiple_events(self):
        """测试桥接多个事件"""
        bridge = EventBridge(
            event_bus=self.event_bus,
            ui_queue=self.ui_queue,
            event_types=["event1", "event2"],
        )
        bridge.start()

        handler1 = mock.Mock()
        handler2 = mock.Mock()
        self.ui_queue.subscribe("event1", handler1)
        self.ui_queue.subscribe("event2", handler2)

        self.event_bus.emit("event1", arg="value1")
        self.event_bus.emit("event2", arg="value2")

        time.sleep(0.1)
        self.ui_queue.process_events()

        handler1.assert_called_once_with(arg="value1")
        handler2.assert_called_once_with(arg="value2")
        bridge.stop()

    def test_bridge_filtered_events(self):
        """测试只桥接指定的事件类型"""
        bridge = EventBridge(
            event_bus=self.event_bus,
            ui_queue=self.ui_queue,
            event_types=["event1"],
        )
        bridge.start()

        handler1 = mock.Mock()
        handler2 = mock.Mock()
        self.ui_queue.subscribe("event1", handler1)
        self.ui_queue.subscribe("event2", handler2)

        self.event_bus.emit("event1", arg="value1")
        self.event_bus.emit("event2", arg="value2")

        time.sleep(0.1)
        self.ui_queue.process_events()

        handler1.assert_called_once_with(arg="value1")
        handler2.assert_not_called()
        bridge.stop()

    def test_stop_bridge(self):
        """测试停止桥接"""
        bridge = EventBridge(
            event_bus=self.event_bus,
            ui_queue=self.ui_queue,
            event_types=["test.event"],
        )
        bridge.start()

        handler = mock.Mock()
        self.ui_queue.subscribe("test.event", handler)

        self.event_bus.emit("test.event", arg="value1")

        time.sleep(0.1)
        self.ui_queue.process_events()
        handler.assert_called_once()

        bridge.stop()

        handler.reset_mock()
        self.event_bus.emit("test.event", arg="value2")

        time.sleep(0.1)
        self.ui_queue.process_events()
        handler.assert_not_called()

    def test_add_event_type(self):
        """测试动态添加事件类型"""
        bridge = EventBridge(
            event_bus=self.event_bus,
            ui_queue=self.ui_queue,
            event_types=["event1"],
        )
        bridge.start()

        handler1 = mock.Mock()
        handler2 = mock.Mock()
        self.ui_queue.subscribe("event1", handler1)
        self.ui_queue.subscribe("event2", handler2)

        self.event_bus.emit("event1", arg="value1")
        self.event_bus.emit("event2", arg="value2")

        time.sleep(0.1)
        self.ui_queue.process_events()

        handler1.assert_called_once()
        handler2.assert_not_called()

        bridge.add_event_type("event2")

        self.event_bus.emit("event2", arg="value3")

        time.sleep(0.1)
        self.ui_queue.process_events()

        handler2.assert_called_once_with(arg="value3")
        bridge.stop()

    def test_remove_event_type(self):
        """测试移除事件类型"""
        bridge = EventBridge(
            event_bus=self.event_bus,
            ui_queue=self.ui_queue,
            event_types=["event1", "event2"],
        )
        bridge.start()

        handler1 = mock.Mock()
        handler2 = mock.Mock()
        self.ui_queue.subscribe("event1", handler1)
        self.ui_queue.subscribe("event2", handler2)

        self.event_bus.emit("event1", arg="value1")
        self.event_bus.emit("event2", arg="value2")

        time.sleep(0.1)
        self.ui_queue.process_events()

        handler1.assert_called_once()
        handler2.assert_called_once()

        bridge.remove_event_type("event2")

        handler1.reset_mock()
        handler2.reset_mock()

        self.event_bus.emit("event1", arg="value3")
        self.event_bus.emit("event2", arg="value4")

        time.sleep(0.1)
        self.ui_queue.process_events()

        handler1.assert_called_once_with(arg="value3")
        handler2.assert_not_called()
        bridge.stop()

    def test_is_active(self):
        """测试桥接器活动状态"""
        bridge = EventBridge(
            event_bus=self.event_bus,
            ui_queue=self.ui_queue,
            event_types=["test.event"],
        )

        self.assertFalse(bridge.is_active)

        bridge.start()
        self.assertTrue(bridge.is_active)

        bridge.stop()
        self.assertFalse(bridge.is_active)

    def test_double_start(self):
        """测试重复启动桥接器"""
        bridge = EventBridge(
            event_bus=self.event_bus,
            ui_queue=self.ui_queue,
            event_types=["test.event"],
        )

        bridge.start()
        self.assertTrue(bridge.is_active)

        bridge.start()
        self.assertTrue(bridge.is_active)

        bridge.stop()

    def test_bridge_error_handling(self):
        """测试桥接错误处理"""
        bridge = EventBridge(
            event_bus=self.event_bus,
            ui_queue=self.ui_queue,
            event_types=["test.event"],
        )
        bridge.start()

        handler = mock.Mock()
        self.ui_queue.subscribe("test.event", handler)

        self.event_bus.emit("test.event", arg="value")

        time.sleep(0.1)
        self.ui_queue.process_events()

        handler.assert_called_once()
        bridge.stop()


if __name__ == "__main__":
    unittest.main()

