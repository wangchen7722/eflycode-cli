import json
import threading
from typing import Literal, Optional, List
from enum import Enum

from eflycode.agent.core.agent import ConversationAgent
from eflycode.ui.command.command_handler import CommandHandler
from eflycode.schema.agent import AgentResponseChunk, AgentResponseChunkType, AgentResponse
from eflycode.schema.llm import ToolCall
from eflycode.ui.event import AgentUIEventType, UIEventType
from eflycode.util.event_bus import EventBus
from eflycode.util.logger import logger


class EventControllerState(Enum):
    """事件控制器状态"""

    # 初始化中
    INITIALIZING = "initializing"
    # 就绪状态，已初始化完成
    READY = "ready"
    # 运行中，用户输入或 Agent 响应
    RUNNING = "running"
    # 中断中，正在处理中断信号
    INTERRUPTING = "interrupting"
    # 已中断，等待用户决定
    INTERRUPTED = "interrupted"
    # 关闭中，正在清理资源
    STOPPING = "stopping"
    # 已关闭，运行循环结束
    STOPPED = "stopped"


class CancelToken:
    """可取消任务令牌，用于优雅停止流式响应或耗时调用"""

    def __init__(self):
        self._event = threading.Event()

    def cancel(self) -> None:
        """取消令牌

        Returns:
            None

        异常:
            无
        """
        self._event.set()

    def cancelled(self) -> bool:
        """检查令牌是否已被取消

        Returns:
            bool: 是否已取消

        异常:
            无
        """
        return self._event.is_set()


class AgentEventController:
    """Agent 事件控制器

    负责订阅 UI 事件、调度 Agent 的调用（支持流式输出），并通过事件总线反馈进度与结果。
    不再维护独立的后台主线程，整体为纯事件驱动模型。
    """

    def __init__(
            self,
            agent: ConversationAgent,
            event_bus: EventBus,
            stream_output: bool = True,
    ):
        """初始化事件控制器
        
        Args:
            agent: 对话智能体实例
            event_bus: 事件总线实例
            stream_output: 是否使用流式输出
        
        Returns:
            None
        
        异常:
            无
        """
        self.agent = agent
        self.event_bus = event_bus
        self.stream_output = stream_output

        self._state = EventControllerState.RUNNING
        self.command_handler = CommandHandler(event_bus, self)

        self._current_job_thread: Optional[threading.Thread] = None
        self._current_cancel: Optional[CancelToken] = None

        self._stopped_event = threading.Event()

        # 订阅事件
        self.event_bus.subscribe(UIEventType.USER_INPUT_RECEIVED, self._on_user_input_received, pass_event=False)
        self.event_bus.subscribe(UIEventType.STOP_APP, self._on_stop_app, pass_event=False)

        self._state = EventControllerState.READY

    @property
    def state(self) -> EventControllerState:
        """获取当前状态

        Returns:
            EventControllerState: 当前控制器状态
        
        异常:
            无
        """
        return self._state

    def _on_stop_app(self, data: dict) -> None:
        """收到停止应用事件

        Args:
            data: 事件数据

        Returns:
            None
        
        异常:
            无
        """
        self._state = EventControllerState.INTERRUPTING
        self._cancel_current_job()
        self._state = EventControllerState.STOPPED
        self._stopped_event.set()

    def _on_user_input_received(self, data: dict) -> None:
        """处理来自 UI 的用户输入事件

        Args:
            data: 包含用户输入文本的事件数据，键为 "text"

        Returns:
            None
        
        异常:
            无
        """
        user_input = (data or {}).get("text", "").strip()
        if not user_input:
            return

        if self.command_handler.is_command(user_input):
            self.command_handler.handle_command(user_input)
            return

        self._start_agent_job(user_input)

    def _start_agent_job(self, user_input: str) -> None:
        """启动一次 Agent 任务（在独立任务线程中处理，支持流式输出）

        Args:
            user_input: 用户输入的文本

        Returns:
            None
        
        异常:
            无；内部异常将转换为 UI 错误事件
        """
        self._cancel_current_job()
        cancel = CancelToken()
        self._current_cancel = cancel

        def _run_stream():
            try:
                self.event_bus.emit(AgentUIEventType.MESSAGE_START)
                if self.stream_output and hasattr(self.agent, "stream"):
                    stream_response = self.agent.stream(user_input)
                    for chunk in stream_response:
                        if cancel.cancelled():
                            break
                        self._emit_response_chunk(chunk)
                else:
                    response = self.agent.call(user_input)
                    if cancel.cancelled():
                        return
                    self._emit_response(response)
                self.event_bus.emit(AgentUIEventType.MESSAGE_END)
            except Exception as e:
                self.event_bus.emit(UIEventType.ERROR, {"error": f"Agent 处理失败: {str(e)}"})

        thread = threading.Thread(target=_run_stream, daemon=True)
        self._current_job_thread = thread
        thread.start()

    def _cancel_current_job(self) -> None:
        """取消当前正在运行的 Agent 任务

        Returns:
            None
        
        异常:
            无
        """
        if self._current_cancel:
            self._current_cancel.cancel()
            self._current_cancel = None
        if self._current_job_thread and self._current_job_thread.is_alive():
            # 延长等待时间，确保任务能够正确结束
            self._current_job_thread.join(timeout=2.0)
            if self._current_job_thread.is_alive():
                logger.warning("Agent任务线程未能在2秒内结束，可能存在资源泄漏")
            self._current_job_thread = None

    def _emit_response_chunk(self, chunk: AgentResponseChunk) -> None:
        """发送流式响应块到 UI

        Args:
            chunk: 流式响应块

        Returns:
            None
        
        异常:
            无
        """
        if chunk.type == AgentResponseChunkType.TEXT and chunk.content:
            self.event_bus.emit(AgentUIEventType.MESSAGE_UPDATE, {"text": chunk.content})
        elif chunk.type in [AgentResponseChunkType.TOOL_CALL_START,
                            AgentResponseChunkType.TOOL_CALL_END] and chunk.tool_calls:
            self._emit_tool_calls(chunk.type, chunk.tool_calls)
        elif chunk.type == AgentResponseChunkType.DONE:
            # 通过 DONE 信号结束消息，无需直接输出
            pass

    def _emit_response(self, response: AgentResponse) -> None:
        """发送完整响应到 UI

        Args:
            response: 完整的 Agent 响应

        Returns:
            None
        
        异常:
            无
        """
        if response.content:
            self.event_bus.emit(AgentUIEventType.MESSAGE_UPDATE, {"text": response.content})
        if response.tool_calls:
            self._emit_tool_calls(AgentResponseChunkType.TOOL_CALL_END, response.tool_calls)

    def _emit_tool_calls(self, tool_call_type: Literal[
        AgentResponseChunkType.TOOL_CALL_START, AgentResponseChunkType.TOOL_CALL_END],
                         tool_calls: List[ToolCall]) -> None:
        """发送工具调用信息到 UI

        Args:
            tool_call_type: 工具调用事件类型（开始或结束）
            tool_calls: 工具调用列表

        Returns:
            None
        
        异常:
            无
        """
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            try:
                tool_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                tool_args = tool_call.function.arguments

            if tool_call_type == AgentResponseChunkType.TOOL_CALL_START:
                self.event_bus.emit(AgentUIEventType.TOOL_CALL_START, {
                    "name": tool_name,
                })
            else:
                self.event_bus.emit(AgentUIEventType.TOOL_CALL_END, {
                    "name": tool_name,
                    "args": tool_args,
                })

    def stop(self) -> None:
        """停止事件控制器，优雅取消任务并通知 UI 退出

        Returns:
            None
        
        异常:
            无
        """
        if self._state == EventControllerState.STOPPED:
            return

        logger.info("正在停止Agent事件控制器...")

        # 先取消当前任务
        self._cancel_current_job()

        # 设置停止状态
        self._state = EventControllerState.STOPPING

        # 发送停止事件，让 UI 主线程自行处理退出
        self.event_bus.emit(UIEventType.STOP_APP)

        # 设置停止事件（用于取消当前流式任务等）
        self._stopped_event.set()

        self._state = EventControllerState.STOPPED
        logger.info("Agent事件控制器已停止")