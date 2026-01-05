"""Renderer 测试用例"""

import unittest

from eflycode.core.llm.protocol import ChatCompletion, Message
from eflycode.core.ui.output import UIOutput
from eflycode.core.ui.renderer import Renderer
from eflycode.core.ui.ui_event_queue import UIEventQueue


class MockOutput(UIOutput):
    """Mock 输出实现"""

    def __init__(self):
        self.written = []
        self.tool_calls = []
        self.tool_results = []
        self.errors = []
        self.task_started = None
        self.task_ended = False

    def write(self, text: str) -> None:
        self.written.append(text)

    def clear(self) -> None:
        self.written.clear()

    def flush(self) -> None:
        pass

    def start_task(self, task_name: str) -> None:
        self.task_started = task_name

    def end_task(self) -> None:
        self.task_ended = True

    def show_tool_call(self, tool_name: str, arguments: dict) -> None:
        self.tool_calls.append({"name": tool_name, "arguments": arguments})

    def show_tool_call_detected(self, tool_name: str) -> None:
        self.tool_calls.append({"name": tool_name, "status": "detected"})

    def show_tool_call_executing(self, tool_name: str, arguments: dict) -> None:
        for tc in self.tool_calls:
            if tc.get("name") == tool_name and tc.get("status") == "detected":
                tc["status"] = "executing"
                tc["arguments"] = arguments
                break

    def show_tool_result(self, tool_name: str, result: str) -> None:
        self.tool_results.append({"name": tool_name, "result": result})

    def show_error(self, error: Exception) -> None:
        self.errors.append(error)

    def close(self) -> None:
        pass


class TestRenderer(unittest.TestCase):
    """Renderer 测试类"""

    def setUp(self):
        """设置测试环境"""
        self.ui_queue = UIEventQueue()
        self.output = MockOutput()
        self.renderer = Renderer(self.ui_queue, self.output)

    def test_init(self):
        """测试初始化"""
        self.assertIsNotNone(self.renderer._ui_queue)
        self.assertIsNotNone(self.renderer._output)
        self.assertEqual(self.renderer.current_task, None)
        self.assertEqual(len(self.renderer.tool_calls), 0)

    def test_handle_task_start(self):
        """测试处理任务开始事件"""
        self.ui_queue.emit("agent.task.start", user_input="Test task")

        # 处理事件队列
        self.ui_queue.process_events()
        self.renderer.tick()

        self.assertEqual(self.renderer.current_task, "Test task")
        self.assertEqual(self.output.task_started, "Test task")

    def test_handle_message_delta(self):
        """测试处理消息增量事件"""
        self.ui_queue.emit("agent.message.delta", delta="Hello")
        self.ui_queue.emit("agent.message.delta", delta=" World")

        # 处理事件队列
        self.ui_queue.process_events()

        # 消息应该被添加到缓冲区
        self.assertEqual(self.renderer._message_buffer, "Hello World")

    def test_handle_message_stop(self):
        """测试处理消息结束事件"""
        # 先添加一些 delta
        self.ui_queue.emit("agent.message.delta", delta="Hello")
        self.ui_queue.process_events()
        self.renderer.tick()

        # 然后触发 stop
        completion = ChatCompletion(
            id="chatcmpl-1",
            object="chat.completion",
            created=1234567890,
            model="gpt-4",
            message=Message(role="assistant", content="Hello"),
        )
        self.ui_queue.emit("agent.message.stop", response=completion)
        self.ui_queue.process_events()

        # tick 应该输出内容
        import time
        time.sleep(0.1)  # 等待输出间隔
        self.renderer.tick()

        # 验证内容被输出
        self.assertGreater(len(self.output.written), 0)

    def test_handle_tool_call_start(self):
        """测试处理工具调用开始事件"""
        self.ui_queue.emit("agent.tool.call.start", tool_name="test_tool", tool_call_id="call_1")

        # 处理事件队列
        self.ui_queue.process_events()
        self.renderer.tick()

        self.assertEqual(len(self.renderer.tool_calls), 1)
        self.assertEqual(self.renderer.tool_calls[0]["name"], "test_tool")
        self.assertEqual(self.renderer.tool_calls[0]["status"], "detected")
        self.assertEqual(self.renderer.tool_calls[0]["id"], "call_1")

    def test_handle_tool_call_ready(self):
        """测试处理工具调用就绪事件"""
        # 先触发 start 事件
        self.ui_queue.emit("agent.tool.call.start", tool_name="test_tool", tool_call_id="call_1")
        self.ui_queue.process_events()
        self.renderer.tick()

        # 然后触发 ready 事件
        self.ui_queue.emit("agent.tool.call.ready", tool_name="test_tool", tool_call_id="call_1", arguments={"arg1": "value1"})
        self.ui_queue.process_events()
        self.renderer.tick()

        self.assertEqual(len(self.renderer.tool_calls), 1)
        self.assertEqual(self.renderer.tool_calls[0]["name"], "test_tool")
        self.assertEqual(self.renderer.tool_calls[0]["status"], "executing")
        self.assertEqual(self.renderer.tool_calls[0]["arguments"]["arg1"], "value1")

    def test_handle_tool_result(self):
        """测试处理工具执行结果事件"""
        # 先添加工具调用（通过新的事件流程）
        self.ui_queue.emit("agent.tool.call.start", tool_name="test_tool", tool_call_id="call_1")
        self.ui_queue.emit("agent.tool.call.ready", tool_name="test_tool", tool_call_id="call_1", arguments={})
        self.ui_queue.process_events()
        self.renderer.tick()

        # 然后添加结果
        self.ui_queue.emit("agent.tool.result", tool_name="test_tool", tool_call_id="call_1", result="success")
        self.ui_queue.process_events()
        self.renderer.tick()

        # 验证结果被关联到工具调用
        self.assertEqual(len(self.renderer.tool_calls), 1)
        self.assertEqual(self.renderer.tool_calls[0].get("result"), "success")
        self.assertEqual(self.renderer.tool_calls[0].get("status"), "completed")

    def test_handle_error(self):
        """测试处理错误事件"""
        error = Exception("Test error")
        self.ui_queue.emit("agent.error", error=error)

        # 处理事件队列
        self.ui_queue.process_events()
        self.renderer.tick()

        self.assertEqual(len(self.output.errors), 1)
        self.assertEqual(self.output.errors[0], error)

    def test_tick_typewriter_effect(self):
        """测试打字机效果"""
        # 添加消息到缓冲区
        self.renderer._message_buffer = "Hello World"
        self.renderer._message_index = 0

        # 多次 tick 应该逐步输出
        import time
        for _ in range(5):
            time.sleep(0.06)  # 超过输出间隔
            self.renderer.tick()

        # 验证有内容被输出
        self.assertGreater(len(self.output.written), 0)

    def test_tick_tool_call_display(self):
        """测试工具调用显示"""
        # 添加工具调用（通过新的事件流程）
        self.ui_queue.emit("agent.tool.call.start", tool_name="test_tool", tool_call_id="call_1")
        self.ui_queue.process_events()
        self.renderer.tick()

        # 验证工具调用被添加到 renderer
        self.assertEqual(len(self.renderer.tool_calls), 1)
        # 验证检测到工具调用被显示
        self.assertEqual(len(self.output.tool_calls), 1)
        self.assertEqual(self.output.tool_calls[0]["status"], "detected")

        # 触发 ready 事件
        self.ui_queue.emit("agent.tool.call.ready", tool_name="test_tool", tool_call_id="call_1", arguments={"arg": "value"})
        self.ui_queue.process_events()
        self.renderer.tick()

        # 验证工具正在执行被显示
        self.assertEqual(self.renderer.tool_calls[0]["status"], "executing")

    def test_tick_tool_result_display(self):
        """测试工具结果显示"""
        # 添加工具调用（通过新的事件流程）
        self.ui_queue.emit("agent.tool.call.start", tool_name="test_tool", tool_call_id="call_1")
        self.ui_queue.emit("agent.tool.call.ready", tool_name="test_tool", tool_call_id="call_1", arguments={})
        self.ui_queue.process_events()
        self.renderer.tick()

        # 添加结果
        self.ui_queue.emit("agent.tool.result", tool_name="test_tool", tool_call_id="call_1", result="result")
        self.ui_queue.process_events()
        self.renderer.tick()

        # 验证结果被显示
        self.assertEqual(len(self.output.tool_results), 1)

    def test_close(self):
        """测试关闭渲染器"""
        # 启动任务
        self.ui_queue.emit("agent.task.start", user_input="Test")
        self.ui_queue.process_events()
        self.renderer.tick()

        # 关闭
        self.renderer.close()

        # 验证任务结束
        self.assertTrue(self.output.task_ended)

    def test_multiple_tool_calls(self):
        """测试多个工具调用"""
        self.ui_queue.emit("agent.tool.call.start", tool_name="tool1", tool_call_id="call_1")
        self.ui_queue.emit("agent.tool.call.start", tool_name="tool2", tool_call_id="call_2")
        self.ui_queue.process_events()
        self.renderer.tick()

        self.assertEqual(len(self.renderer.tool_calls), 2)
        self.assertEqual(self.renderer.tool_calls[0]["name"], "tool1")
        self.assertEqual(self.renderer.tool_calls[1]["name"], "tool2")

    def test_message_buffer_clearing(self):
        """测试消息缓冲区清空"""
        # 添加消息
        self.renderer._message_buffer = "Test"
        self.renderer._message_index = 0

        # 任务开始应该清空缓冲区
        self.ui_queue.emit("agent.task.start", user_input="New task")
        self.renderer.tick()

        self.assertEqual(self.renderer._message_buffer, "")


if __name__ == "__main__":
    unittest.main()

