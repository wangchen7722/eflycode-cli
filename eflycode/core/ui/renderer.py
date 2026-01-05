import time
from typing import Dict, List, Optional

from eflycode.core.ui.output import UIOutput
from eflycode.core.ui.ui_event_queue import UIEventQueue


class Renderer:
    """渲染器，监听 UI 事件队列并输出

    职责：
    - 订阅 UIEventQueue 的事件
    - 维护渲染状态
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

        self.current_task: Optional[str] = None
        self.tool_calls: List[Dict] = []
        self._task_started: bool = False
        
        # 用于打字机效果的缓冲区
        self._message_buffer: str = ""
        self._message_index: int = 0
        self._chars_per_tick: int = 20
        self._last_output_time: float = 0.0
        self._output_interval: float = 0.05  # 每次输出的间隔（秒）

        self._subscribe_events()

    def _subscribe_events(self) -> None:
        """订阅 UI 事件"""
        self._ui_queue.subscribe("agent.task.start", self.handle_task_start)
        self._ui_queue.subscribe("agent.task.stop", self.handle_task_stop)
        self._ui_queue.subscribe("agent.message.start", self.handle_message_start)
        self._ui_queue.subscribe("agent.message.delta", self.handle_message_delta)
        self._ui_queue.subscribe("agent.message.stop", self.handle_message_stop)
        self._ui_queue.subscribe("agent.tool.call.start", self.handle_tool_call_start)
        self._ui_queue.subscribe("agent.tool.call.ready", self.handle_tool_call_ready)
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
        self._task_started = False
        # 清空消息缓冲区
        self._message_buffer = ""
        self._message_index = 0
        self._last_output_time = 0.0

    def handle_task_stop(self, **kwargs) -> None:
        """处理任务结束事件

        只更新状态，不阻塞

        Args:
            **kwargs: 事件参数，包含 result 等
        """
        # 任务结束时，确保所有待处理的文本都被处理
        pass

    def handle_message_start(self, **kwargs) -> None:
        """处理消息开始事件

        只更新状态，不阻塞

        Args:
            **kwargs: 事件参数
        """
        pass

    def handle_message_delta(self, **kwargs) -> None:
        """处理消息增量事件

        将 delta 添加到缓冲区，通过 tick 方法逐步输出

        Args:
            **kwargs: 事件参数，包含 delta 等
        """
        delta = kwargs.get("delta", "")
        if delta:
            # 将 delta 追加到缓冲区
            self._message_buffer += delta

    def handle_message_stop(self, **kwargs) -> None:
        """处理消息结束事件

        消息结束时，确保所有缓冲区内容都已输出，然后添加换行

        Args:
            **kwargs: 事件参数，包含 response 等
        """
        # 流式响应中，内容已经通过 delta 事件累积到缓冲区
        # 确保所有缓冲区内容都已输出后，添加换行
        # 如果缓冲区还有内容，会在 tick 中继续输出
        # 当缓冲区为空时，说明所有内容都已输出，此时添加换行
        if not self._message_buffer or self._message_index >= len(self._message_buffer):
            self._output.write("\n")
            self._message_buffer = ""
            self._message_index = 0

    def handle_tool_call_start(self, **kwargs) -> None:
        """处理工具调用开始事件

        流式输出中检测到工具调用时触发

        Args:
            **kwargs: 事件参数，包含 tool_name、tool_call_id 等
        """
        tool_name = kwargs.get("tool_name", "")
        tool_call_id = kwargs.get("tool_call_id", "")
        if tool_name:
            # 检查是否已存在该工具调用
            existing = None
            for tc in self.tool_calls:
                if tc.get("id") == tool_call_id:
                    existing = tc
                    break
            if not existing:
                self.tool_calls.append({
                    "name": tool_name,
                    "id": tool_call_id,
                    "status": "detected",
                })

    def handle_tool_call_ready(self, **kwargs) -> None:
        """处理工具调用就绪事件

        工具调用完整时触发

        Args:
            **kwargs: 事件参数，包含 tool_name、tool_call_id、arguments 等
        """
        tool_name = kwargs.get("tool_name", "")
        tool_call_id = kwargs.get("tool_call_id", "")
        arguments = kwargs.get("arguments", {})
        if tool_name:
            # 更新工具调用状态为正在执行
            for tc in self.tool_calls:
                if tc.get("id") == tool_call_id:
                    # 如果状态已经是 executing 且已经有 _executing_shown 标志，说明已经处理过，避免重复
                    if tc.get("status") != "executing" or not tc.get("_executing_shown"):
                        tc["status"] = "executing"
                        tc["arguments"] = arguments
                        # 重置 _executing_shown 标志，确保下次 tick 时会显示
                        tc["_executing_shown"] = False
                    break

    def handle_tool_call(self, **kwargs) -> None:
        """处理工具调用事件

        工具执行时触发，在流式模式下由 agent.tool.call.ready 处理
        保留此方法以兼容非流式模式，但不做任何处理

        Args:
            **kwargs: 事件参数，包含 tool_name、arguments 等
        """
        pass

    def handle_tool_result(self, **kwargs) -> None:
        """处理工具执行结果事件

        只更新状态，不阻塞

        Args:
            **kwargs: 事件参数，包含 tool_name、result 等
        """
        tool_name = kwargs.get("tool_name", "")
        result = kwargs.get("result", "")
        tool_call_id = kwargs.get("tool_call_id", "")
        for tool_call in self.tool_calls:
            if tool_call.get("name") == tool_name:
                # 如果提供了 tool_call_id，优先匹配 ID
                if tool_call_id and tool_call.get("id") == tool_call_id:
                    tool_call["result"] = result
                    tool_call["status"] = "completed"
                    break
                elif not tool_call_id:
                    tool_call["result"] = result
                    tool_call["status"] = "completed"
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
        """刷新显示

        每次只做少量工作，不阻塞主循环

        Args:
            time_budget_ms: 时间预算（毫秒）
        """
        start_time = time.time() if time_budget_ms is not None else None
        current_time = time.time()

        if self.current_task and not self._task_started:
            self._output.start_task(self.current_task)
            self._task_started = True
            # 任务开始后，消息内容应该在新行输出
            self._output.write("\n")

        # 打字机效果：逐步输出消息缓冲区中的内容
        if self._message_buffer and self._message_index < len(self._message_buffer):
            # 检查是否到了输出时间
            if current_time - self._last_output_time >= self._output_interval:
                # 计算本次要输出的字符数
                remaining = len(self._message_buffer) - self._message_index
                chunk_size = min(self._chars_per_tick, remaining)
                
                # 输出字符块
                chunk = self._message_buffer[self._message_index:self._message_index + chunk_size]
                self._output.write(chunk)
                self._message_index += chunk_size
                self._last_output_time = current_time
                
                # 如果输出完成，清空缓冲区
                if self._message_index >= len(self._message_buffer):
                    self._message_buffer = ""
                    self._message_index = 0

            if start_time is not None:
                elapsed_ms = (time.time() - start_time) * 1000
                if elapsed_ms >= time_budget_ms:
                    return

        for tool_call in self.tool_calls:
            status = tool_call.get("status", "executing")
            tool_name = tool_call.get("name", "")
            
            if status == "detected" and not tool_call.get("_detected_shown"):
                self._output.write("\n")
                self._output.show_tool_call_detected(tool_name)
                tool_call["_detected_shown"] = True
            elif status == "executing" and not tool_call.get("_executing_shown"):
                self._output.show_tool_call_executing(tool_name, tool_call.get("arguments", {}))
                tool_call["_executing_shown"] = True
            elif status == "completed" and tool_call.get("result") and not tool_call.get("_result_shown"):
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
        if self.current_task and self._task_started:
            self._output.end_task()
        self._output.close()
