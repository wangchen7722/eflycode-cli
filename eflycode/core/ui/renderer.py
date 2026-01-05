import time
from typing import Dict, List, Optional

from eflycode.core.ui.output import UIOutput
from eflycode.core.ui.ui_event_queue import UIEventQueue
from eflycode.core.utils.logger import logger


class Renderer:
    """渲染器，监听 UI 事件队列并输出

    职责：
    - 订阅 UIEventQueue 的事件
    - 维护渲染状态（pending_text、current_task 等）
    - 通过 tick 方法推进打字机效果和刷新显示
    - 所有输出通过 UIOutput 接口
    """

    def __init__(self, ui_queue: UIEventQueue, output: UIOutput):
        """初始化渲染器

        Args:
            ui_queue: UI 事件队列
            output: UI 输出接口
        """
        self._ui_queue = ui_queue
        self._output = output

        self.pending_text: str = ""
        self.current_text: str = ""
        self.current_task: Optional[str] = None
        self.tool_calls: List[Dict] = []

        self._chars_per_tick = 20
        self._subscribe_events()

    def _subscribe_events(self) -> None:
        """订阅 UI 事件"""
        self._ui_queue.subscribe("agent.task.start", self.handle_task_start)
        self._ui_queue.subscribe("agent.task.stop", self.handle_task_stop)
        self._ui_queue.subscribe("agent.message.delta", self.handle_message_delta)
        self._ui_queue.subscribe("agent.tool.call", self.handle_tool_call)
        self._ui_queue.subscribe("agent.tool.result", self.handle_tool_result)
        self._ui_queue.subscribe("agent.error", self.handle_error)

    def handle_task_start(self, **kwargs) -> None:
        """处理任务开始事件

        只更新状态，不阻塞

        Args:
            **kwargs: 事件参数，包含 user_input 等
        """
        task_name = kwargs.get("user_input", "未知任务")
        self.current_task = task_name
        self.pending_text = ""
        self.current_text = ""

    def handle_task_stop(self, **kwargs) -> None:
        """处理任务结束事件

        只更新状态，不阻塞

        Args:
            **kwargs: 事件参数，包含 result 等
        """
        result = kwargs.get("result", "")
        if result and result not in self.current_text:
            self.pending_text += result

    def handle_message_delta(self, **kwargs) -> None:
        """处理消息增量事件

        将 delta 追加到 pending_text，不阻塞

        Args:
            **kwargs: 事件参数，包含 delta 等
        """
        delta = kwargs.get("delta", "")
        if delta:
            self.pending_text += delta

    def handle_tool_call(self, **kwargs) -> None:
        """处理工具调用事件

        只更新状态，不阻塞

        Args:
            **kwargs: 事件参数，包含 tool_name、arguments 等
        """
        tool_name = kwargs.get("tool_name", "")
        arguments = kwargs.get("arguments", {})
        if tool_name:
            self.tool_calls.append({"name": tool_name, "arguments": arguments})

    def handle_tool_result(self, **kwargs) -> None:
        """处理工具执行结果事件

        只更新状态，不阻塞

        Args:
            **kwargs: 事件参数，包含 tool_name、result 等
        """
        tool_name = kwargs.get("tool_name", "")
        result = kwargs.get("result", "")
        for tool_call in self.tool_calls:
            if tool_call.get("name") == tool_name:
                tool_call["result"] = result
                break

    def handle_error(self, **kwargs) -> None:
        """处理错误事件

        只更新状态，不阻塞

        Args:
            **kwargs: 事件参数，包含 error 等
        """
        error = kwargs.get("error")
        if error:
            if isinstance(error, Exception):
                self._output.show_error(error)
            else:
                self._output.write(f"[错误] {error}\n")

    def tick(self, time_budget_ms: Optional[int] = None) -> None:
        """推进打字机效果和刷新显示

        每次只做少量工作，不阻塞主循环

        Args:
            time_budget_ms: 时间预算（毫秒）
        """
        start_time = time.time() if time_budget_ms is not None else None

        if self.current_task and not self.current_text:
            self._output.start_task(self.current_task)

        if self.pending_text:
            chunk = self.pending_text[: self._chars_per_tick]
            self.pending_text = self.pending_text[self._chars_per_tick :]
            self.current_text += chunk
            self._output.write(chunk)

            if start_time is not None:
                elapsed_ms = (time.time() - start_time) * 1000
                if elapsed_ms >= time_budget_ms:
                    return

        for tool_call in self.tool_calls:
            if "result" not in tool_call:
                self._output.show_tool_call(
                    tool_call.get("name", ""), tool_call.get("arguments", {})
                )
                tool_call["_shown"] = True
            elif tool_call.get("result") and not tool_call.get("_result_shown"):
                self._output.show_tool_result(
                    tool_call.get("name", ""), tool_call.get("result", "")
                )
                tool_call["_result_shown"] = True

            if start_time is not None:
                elapsed_ms = (time.time() - start_time) * 1000
                if elapsed_ms >= time_budget_ms:
                    return

        self._output.flush()

    def close(self) -> None:
        """关闭渲染器

        清理资源
        """
        if self.current_task:
            self._output.end_task()
        self._output.close()
