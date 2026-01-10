import time
from typing import Optional

from prompt_toolkit.utils import get_cwidth

from eflycode.core.ui.output import UIOutput
from eflycode.core.ui.ui_event_queue import UIEventQueue

# 打字机效果配置常量
TYPEWRITER_CHARS_PER_TICK = 20
TYPEWRITER_OUTPUT_INTERVAL = 0.05  # 秒


class Renderer:
    """渲染器，监听 UI 事件队列并输出

    职责：
    - 订阅 UIEventQueue 的事件
    - 事件来了就显示，简单直接
    - 通过 tick 方法推进打字机效果
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
        self._task_started: bool = False
        
        # 用于打字机效果的缓冲区
        self._message_buffer: str = ""
        self._message_index: int = 0
        self._chars_per_tick: int = TYPEWRITER_CHARS_PER_TICK
        self._last_output_time: float = 0.0
        self._output_interval: float = TYPEWRITER_OUTPUT_INTERVAL

        self._subscribe_events()

    def _subscribe_events(self) -> None:
        """订阅 UI 事件"""
        self._ui_queue.subscribe("app.initialized", self.handle_app_initialized)
        self._ui_queue.subscribe("agent.task.start", self.handle_task_start)
        self._ui_queue.subscribe("agent.task.stop", self.handle_task_stop)
        self._ui_queue.subscribe("agent.message.start", self.handle_message_start)
        self._ui_queue.subscribe("agent.message.delta", self.handle_message_delta)
        self._ui_queue.subscribe("agent.message.stop", self.handle_message_stop)
        self._ui_queue.subscribe("agent.tool.call.start", self.handle_tool_call_start)
        self._ui_queue.subscribe("agent.tool.call.ready", self.handle_tool_call_ready)
        self._ui_queue.subscribe("agent.tool.result", self.handle_tool_result)
        self._ui_queue.subscribe("agent.error", self.handle_error)

    def _flush_message_buffer(self) -> None:
        """立即输出缓冲区中的所有内容"""
        if self._message_buffer and self._message_index < len(self._message_buffer):
            chunk = self._message_buffer[self._message_index:]
            if chunk:
                self._output.write(chunk)
        self._message_buffer = ""
        self._message_index = 0

    def _format_banner(self, title: str, body_lines: list[str]) -> str:
        content_lines = [title, ""] + body_lines
        width = max(get_cwidth(line) for line in content_lines)
        top = "╭" + "─" * (width + 2) + "╮"
        bottom = "╰" + "─" * (width + 2) + "╯"
        rendered = [top]
        for line in content_lines:
            pad = " " * (width - get_cwidth(line))
            rendered.append(f"│ {line}{pad} │")
        rendered.append(bottom)
        return "\n".join(rendered)

    def handle_app_initialized(self, **kwargs) -> None:
        """处理初始化完成事件，输出 banner"""
        config = kwargs.get("config")
        if config is None:
            return
        title = f">_ eflycode (v{config.system_version})"
        body_lines = [
            f"model:     {config.model_display_name}   /model to change",
            f"directory: {config.workspace_dir}",
        ]
        banner = self._format_banner(title, body_lines)
        self._output.write(f"{banner}\n")

    def handle_task_start(self, **kwargs) -> None:
        """处理任务开始事件

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

        Args:
            **kwargs: 事件参数，包含 result 等
        """
        # 输出缓冲区剩余内容
        self._flush_message_buffer()

        # 输出任务完成
        if self.current_task and self._task_started:
            self._output.end_task()

        self.current_task = None
        self._task_started = False

    def handle_message_start(self, **kwargs) -> None:
        """处理消息开始事件

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
            self._message_buffer += delta

    def handle_message_stop(self, **kwargs) -> None:
        """处理消息结束事件

        Args:
            **kwargs: 事件参数，包含 response 等
        """
        # 消息结束，不需要特殊处理
        # 剩余内容会在 tick 中继续输出，或在下一个事件前被 flush
        pass

    def handle_tool_call_start(self, **kwargs) -> None:
        """处理工具调用开始事件 - 直接显示

        Args:
            **kwargs: 事件参数，包含 tool_name、tool_call_id 等
        """
        tool_name = kwargs.get("tool_name", "")
        if tool_name:
            # 先输出缓冲区内容，再显示工具调用
            self._flush_message_buffer()
            self._output.show_tool_call_detected(tool_name)

    def handle_tool_call_ready(self, **kwargs) -> None:
        """处理工具调用就绪事件 - 直接显示

        Args:
            **kwargs: 事件参数，包含 tool_name、tool_call_id、arguments 等
        """
        tool_name = kwargs.get("tool_name", "")
        arguments = kwargs.get("arguments", {})
        if tool_name:
            self._output.show_tool_call_executing(tool_name, arguments)

    def handle_tool_result(self, **kwargs) -> None:
        """处理工具执行结果事件 - 直接显示

        Args:
            **kwargs: 事件参数，包含 tool_name、result 等
        """
        tool_name = kwargs.get("tool_name", "")
        result = kwargs.get("result", "")
        self._output.show_tool_result(tool_name, result)

    def handle_error(self, **kwargs) -> None:
        """处理错误事件 - 直接显示

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
        """刷新显示 - 只负责打字机效果

        Args:
            time_budget_ms: 时间预算，单位为毫秒
        """
        start_time = time.time() if time_budget_ms is not None else None
        current_time = time.time()

        # 显示任务开始
        if self.current_task and not self._task_started:
            self._output.start_task(self.current_task)
            self._task_started = True
            self._output.write("\n")

        # 打字机效果：逐步输出消息缓冲区中的内容
        if self._message_buffer and self._message_index < len(self._message_buffer):
            if current_time - self._last_output_time >= self._output_interval:
                remaining = len(self._message_buffer) - self._message_index
                chunk_size = min(self._chars_per_tick, remaining)
                
                chunk = self._message_buffer[self._message_index:self._message_index + chunk_size]
                self._output.write(chunk)
                self._message_index += chunk_size
                self._last_output_time = current_time
                
                # 输出完成，清空缓冲区
                if self._message_index >= len(self._message_buffer):
                    self._message_buffer = ""
                    self._message_index = 0
                    
            if start_time is not None:
                elapsed_ms = (time.time() - start_time) * 1000
                if elapsed_ms >= time_budget_ms:
                    return

        self._output.flush()

    def close(self) -> None:
        """关闭渲染器"""
        if self.current_task and self._task_started:
            self._output.end_task()
        self._output.close()
