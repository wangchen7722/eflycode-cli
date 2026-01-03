#!/usr/bin/env python3
"""
测试新的事件系统
"""
import unittest
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from eflycode.events import (
    UIEventType, WorkerEventType, BridgeEventType,
    create_ui_event_data, create_worker_event_data, create_bridge_event_data,
    convert_worker_event_to_ui_events, convert_ui_event_to_worker_events
)


class TestEventSystem(unittest.TestCase):
    """
    事件系统测试类
    """

    def test_event_creation(self):
        """
        测试事件数据创建

        测试创建不同类型的事件数据实例，并验证其属性。
        """
        # 创建UI事件数据
        ui_data = create_ui_event_data(UIEventType.SHOW_WELCOME,
                                       title="Welcome to eFlyCode",
                                       features=["AI Assistant", "Code Generation", "Terminal Integration"])

        self.assertIsNotNone(ui_data)
        self.assertEqual(ui_data.title, "Welcome to eFlyCode")
        self.assertEqual(len(ui_data.features), 3)

        # 验证字典转换
        data_dict = ui_data.to_dict()
        self.assertIn("title", data_dict)
        self.assertIn("timestamp", data_dict)

        # 创建Worker事件数据
        worker_data = create_worker_event_data(WorkerEventType.TASK_START,
                                               task_type="code_generation",
                                               input_data={"prompt": "create a function"},
                                               priority=1)

        self.assertIsNotNone(worker_data)
        self.assertEqual(worker_data.task_type, "code_generation")
        self.assertEqual(worker_data.priority, 1)

        # 创建Bridge事件数据
        bridge_data = create_bridge_event_data(BridgeEventType.BRIDGE_INIT,
                                               ui_channel_config={"theme": "dark"},
                                               worker_channel_config={"max_workers": 5})

        self.assertIsNotNone(bridge_data)
        self.assertEqual(bridge_data.ui_channel_config["theme"], "dark")

    def test_event_conversion(self):
        """
        测试事件转换

        测试Worker事件到UI事件，以及UI事件到Worker事件的转换功能。
        """
        # Worker事件转换为UI事件
        worker_event = WorkerEventType.TASK_START.value
        worker_data = {
            "task_id": "task_123",
            "task_type": "code_review",
            "input_data": {"file_path": "main.py"}
        }

        ui_events = convert_worker_event_to_ui_events(worker_event, worker_data)
        self.assertIsInstance(ui_events, list)
        self.assertGreater(len(ui_events), 0)

        # 检查转换结果包含正确的消息
        first_event = ui_events[0]
        self.assertIn("message", first_event)
        self.assertIn("task_review", first_event["message"])

        # UI事件转换为Worker事件
        ui_event = UIEventType.USER_INPUT_RECEIVED.value
        ui_data = {
            "text": "请帮我创建一个计算斐波那契数列的函数",
            "input_type": "text"
        }

        worker_events = convert_ui_event_to_worker_events(ui_event, ui_data)
        self.assertIsInstance(worker_events, list)
        self.assertGreater(len(worker_events), 0)

        # 检查转换结果
        first_worker_event = worker_events[0]
        self.assertIn("task_type", first_worker_event)
        self.assertIn("input_data", first_worker_event)

    def test_backward_compatibility(self):
        """
        测试向后兼容性

        验证新的事件系统是否与原有的事件API保持兼容。
        """
        # 导入旧的事件类型
        from eflycode.ui.event import UIEventType as OldUIEventType, AgentUIEventType

        # 验证事件名映射
        self.assertEqual(OldUIEventType.START_APP, UIEventType.START_APP.value)
        self.assertEqual(OldUIEventType.SHOW_WELCOME, UIEventType.SHOW_WELCOME.value)
        self.assertEqual(OldUIEventType.INFO, UIEventType.DISPLAY_INFO.value)

        # 验证Agent事件映射
        self.assertEqual(AgentUIEventType.THINK_START, WorkerEventType.REASONING_START.value)
        self.assertEqual(AgentUIEventType.TOOL_CALL_START, WorkerEventType.TOOL_CALL_REQUEST.value)
        self.assertEqual(AgentUIEventType.MESSAGE_UPDATE, WorkerEventType.MESSAGE_SEND.value)


if __name__ == "__main__":
    unittest.main()
