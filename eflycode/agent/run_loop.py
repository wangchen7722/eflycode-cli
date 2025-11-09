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


class RunLoopState(Enum):
    """运行循环状态"""

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
        self._event.set()

    def cancelled(self) -> bool:
        return self._event.is_set()


class AgentRunLoop:
    """Agent 运行循环"""

    def __init__(
            self,
            agent: ConversationAgent,
            event_bus: EventBus,
            stream_output: bool = True,
    ):
        """初始化运行循环
        
        Args:
            agent: 对话智能体实例
            event_bus: 事件总线实例
            stream_output: 是否使用流式输出
        """
        self.agent = agent
        self.event_bus = event_bus
        self.stream_output = stream_output

        self._state = RunLoopState.INITIALIZING
        self._running = False
        self.command_handler = CommandHandler(event_bus, self)

        self._current_job_thread: Optional[threading.Thread] = None
        self._current_cancel: Optional[CancelToken] = None

        self._stopped_event = threading.Event()
        self._agent_thread: Optional[threading.Thread] = None

        # 订阅事件
        self.event_bus.subscribe(UIEventType.USER_INPUT_RECEIVED, self._on_user_input_received, pass_event=False)
        self.event_bus.subscribe(UIEventType.STOP_APP, self._on_stop_app, pass_event=False)

        self._state = RunLoopState.READY

    @property
    def state(self) -> RunLoopState:
        """获取当前状态"""
        return self._state

    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running

    def start_in_background(self) -> None:
        """
        在后台线程中启动Agent运行循环
        """
        if self._running:
            return

        def _run_agent():
            self._running = True
            self._state = RunLoopState.RUNNING
            
            # 移除启动时的事件发送，由UI主动控制
            # self.event_bus.emit(UIEventType.START_APP)
            # self.event_bus.emit(UIEventType.SHOW_WELCOME)
            
            # 等待停止信号
            self._stopped_event.wait()

        self._agent_thread = threading.Thread(target=_run_agent, daemon=True, name="agent-runloop")
        self._agent_thread.start()

    def run(self) -> None:
        """启动运行循环（保持向后兼容）"""
        self.start_in_background()
        
        # 如果在主线程调用，等待完成
        if self._agent_thread and threading.current_thread() == threading.main_thread():
            try:
                self._agent_thread.join()
            except KeyboardInterrupt:
                self.stop()

    def _on_stop_app(self, data: dict):
        """收到停止应用事件"""
        self._state = RunLoopState.INTERRUPTING
        self._cancel_current_job()
        self._state = RunLoopState.STOPPED
        self._running = False
        self._stopped_event.set()

    def _on_user_input_received(self, data: dict) -> None:
        """收到来自 UI 的输入事件"""
        user_input = (data or {}).get("text", "").strip()
        if not user_input:
            return

        if self.command_handler.is_command(user_input):
            self.command_handler.handle_command(user_input)
            return

        self._start_agent_job(user_input)

    def _start_agent_job(self, user_input: str):
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
        """取消当前正在运行的任务"""
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
        """发送响应块"""
        if chunk.type == AgentResponseChunkType.TEXT and chunk.content:
            self.event_bus.emit(AgentUIEventType.MESSAGE_UPDATE, {"text": chunk.content})
        elif chunk.type in [AgentResponseChunkType.TOOL_CALL_START,
                            AgentResponseChunkType.TOOL_CALL_END] and chunk.tool_calls:
            self._emit_tool_calls(chunk.type, chunk.tool_calls)
        elif chunk.type == AgentResponseChunkType.DONE:
            # 移除self.ui.print()调用，通过事件发送结束信号
            pass

    def _emit_response(self, response: AgentResponse) -> None:
        """发送完整响应"""
        if response.content:
            self.event_bus.emit(AgentUIEventType.MESSAGE_UPDATE, {"text": response.content})
        if response.tool_calls:
            self._emit_tool_calls(AgentResponseChunkType.TOOL_CALL_END, response.tool_calls)

    def _emit_tool_calls(self, tool_call_type: Literal[
        AgentResponseChunkType.TOOL_CALL_START, AgentResponseChunkType.TOOL_CALL_END],
                         tool_calls: List[ToolCall]) -> None:
        """发送工具调用信息"""
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
        """停止运行循环"""
        if not self._running:
            return
            
        logger.info("正在停止Agent运行循环...")
        
        # 先取消当前任务
        self._cancel_current_job()
        
        # 设置停止状态
        self._state = RunLoopState.STOPPING
        self._running = False
        
        # 发送停止事件
        self.event_bus.emit(UIEventType.STOP_APP)
        
        # 设置停止事件
        self._stopped_event.set()
        
        # 等待Agent线程结束
        if self._agent_thread and self._agent_thread.is_alive():
            self._agent_thread.join(timeout=1.0)
            if self._agent_thread.is_alive():
                logger.warning("Agent主线程未能在1秒内结束")
        
        self._state = RunLoopState.STOPPED
        logger.info("Agent运行循环已停止")
