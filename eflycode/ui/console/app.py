from enum import Enum
import threading
from typing import Iterable, List, Optional, Callable

from prompt_toolkit.document import Document
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.layout import HSplit, Layout
from prompt_toolkit.application import Application
from prompt_toolkit.keys import Keys
from prompt_toolkit.completion import Completer, Completion, CompleteEvent
from prompt_toolkit.buffer import Buffer

from eflycode.ui.event import UIEventType, AgentUIEventType, AgentUIEventHandlerMixin
from eflycode.ui.console.ui import ConsoleUI
from eflycode.ui.components import GlowingTextWidget, ThinkingWidget, InputWidget
from eflycode.ui.colors import PTK_STYLE
from eflycode.util.event_bus import EventBus
from eflycode.util.logger import logger
from eflycode.env import Environment
from eflycode.ui.command import BaseCommand, get_builtin_commands
from eflycode.ui.console.completer import SmartCompleter


class UIState(Enum):
    """UI 状态"""
    INPUT = "input"
    TOOL_CALL = "tool_call"
    THINKING = "thinking"


class ConsoleUIApplication(ConsoleUI):
    """控制台 UI 应用"""

    def __init__(self, on_input_callback: Callable[[str], None], event_bus: EventBus) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._event_bus = event_bus
        self._state: UIState = UIState.INPUT
        self._running = False
        self._layout: Layout = self._create_input_layout()
        self._app: Application = Application(
            layout=self._layout,
            style=PTK_STYLE,
            mouse_support=True,
            full_screen=False,
            erase_when_done=False
        )
        self._mount_key_bindings()
        self._on_input_callback = on_input_callback
        self._input_widget: InputWidget | None = None
        self._tool_call_widget: GlowingTextWidget | None = None
        self._thinking_widget: ThinkingWidget | None = None

        self._app_thread: Optional[threading.Thread] = None

    def run_in_background(self):
        """后台运行应用"""
        if self._running:
            return

        def _run():
            self._running = True
            try:
                self._app.run(handle_sigint=False)
            finally:
                self._running = False

        self._app_thread = threading.Thread(target=_run, daemon=True)
        self._app_thread.start()

    def run(self) -> None:
        """
        启动UI应用程序（阻塞式运行）
        
        Raises:
            KeyboardInterrupt: 用户中断
            Exception: 其他运行时异常
        """
        self._running = True
        try:
            # 使用handle_sigint=False，通过按键绑定处理Ctrl+C
            self._app.run(handle_sigint=False)
        finally:
            self._running = False

    def exit(self) -> None:
        """
        安全退出UI应用程序
        可以从任何线程调用
        """
        if self._app and self._app.is_running:
            self._app.exit()

    def is_running(self) -> bool:
        """
        检查UI应用程序是否正在运行
        
        Returns:
            bool: 是否正在运行
        """
        return self._running and self._app and self._app.is_running

    def run_ui(self, fn: Callable[[], None]) -> None:
        """
        在UI线程中安全执行函数
        可以从任何线程调用，确保UI操作在正确的线程中执行
        
        Args:
            fn: 要在UI线程中执行的函数
        """
        if self._app and self._app.is_running:
            # 使用prompt_toolkit的call_from_executor将操作封送到UI线程
            self._app.call_from_executor(fn)
        else:
            # 如果UI未运行，直接执行（通常在初始化阶段）
            fn()

    def stop(self) -> None:
        """
        停止UI应用程序（别名方法）
        """
        self.exit()

    def start_tool_call(self, name: str):
        """开始工具调用"""
        def _start_tool_call():
            with self._lock:
                self._state = UIState.TOOL_CALL
                self._app.layout = self._create_tool_call_layout(f"Calling {name}")
                if self._tool_call_widget:
                    self._tool_call_widget.start()
                self._app.invalidate()
        
        self.run_ui(_start_tool_call)

    def execute_tool_call(self, name: str, args: str):
        """执行工具调用"""
        def _execute_tool_call():
            with self._lock:
                if self._state != UIState.TOOL_CALL:
                    return

                if self._tool_call_widget:
                    # 将内容替换为执行信息
                    self._tool_call_widget.update_text(f"Running {name}")
        
        self.run_ui(_execute_tool_call)

    def finish_tool_call(self, name: str, args: str, result: str):
        """完成工具调用"""
        def _finish_tool_call():
            with self._lock:
                if self._state != UIState.TOOL_CALL:
                    return

                if self._tool_call_widget:
                    # 停止动画线程
                    self._tool_call_widget.stop()
                    # 将内容替换为执行信息
                    self._tool_call_widget.update_text(f"{name} completed")
                    # 手动刷新
                    self._app.invalidate()

            if result:
                self.panel(
                    titles=["Tool Call - " + name],
                    content="\n".join([f"Args: {args}", f"Result: {result}"]),
                    color="green",
                )

            self.show_input()
        
        self.run_ui(_finish_tool_call)

    def fail_tool_call(self, name: str, args: str, error: str):
        """失败工具调用"""
        def _fail_tool_call():
            with self._lock:
                if self._state != UIState.TOOL_CALL:
                    return

                if self._tool_call_widget:
                    # 停止动画线程
                    self._tool_call_widget.stop()
                    # 将内容替换为执行信息
                    self._tool_call_widget.update_text(f"{name} failed")
                    # 手动刷新
                    self._app.invalidate()

            if error:
                self.panel(
                    titles=["Tool Call - " + name],
                    content="\n".join([f"Args: {args}", f"Error: {error}"]),
                    color="red",
                )

            self.show_input()
        
        self.run_ui(_fail_tool_call)

    def show_input(self):
        """显示输入窗口"""
        def _show_input():
            with self._lock:
                self._state = UIState.INPUT
                self._app.layout = self._create_input_layout()
                self._app.invalidate()
        
        self.run_ui(_show_input)

    def _mount_key_bindings(self) -> None:
        """挂载按键绑定"""
        key_bindings = KeyBindings()

        # Ctrl + C 用于优雅退出应用
        @key_bindings.add(Keys.ControlC)
        def _handle_ctrl_c(event: KeyPressEvent):
            logger.info("收到中断信号，正在关闭...")
            self._event_bus.emit(UIEventType.STOP_APP)

        # Alt + Enter 用于插入换行
        @key_bindings.add(Keys.Escape, Keys.Enter)
        def _handle_ctrl_enter(event: KeyPressEvent):
            event.current_buffer.insert_text("\n")

        # Enter 用于提交输入
        @key_bindings.add(Keys.Enter)
        def _handle_enter(event: KeyPressEvent):
            current_buffer = event.current_buffer
            # 如果当前是补全状态，则不插入换行
            if current_buffer.complete_state:
                completion = current_buffer.complete_state.current_completion
                if completion:
                    current_buffer.apply_completion(completion)
                else:
                    if current_buffer.text:
                        current_buffer.validate_and_handle()
            else:
                if current_buffer.text:
                    current_buffer.validate_and_handle()

        # Backspace 删除前一个字符并触发补全
        @key_bindings.add(Keys.Backspace)
        def _handle_backspace(event: KeyPressEvent):
            buffer = event.current_buffer
            if buffer.text:
                buffer.delete_before_cursor(count=1)
                if len(buffer.text) > 0 and buffer.text[-1] in ["/", "#", "@"]:
                    buffer.start_completion(select_first=False)

        self._app.key_bindings = key_bindings

    def _create_tool_call_layout(self, text: str) -> Layout:
        """创建工具调用布局"""
        return Layout(
            HSplit([
                self._create_tool_call_window(text),
                self._create_input_window(),
            ])
        )

    def _create_input_layout(self) -> Layout:
        """创建主布局"""
        input_window = self._create_input_window()
        return Layout(input_window)

    def _create_tool_call_window(self, text: str):
        self._tool_call_widget = GlowingTextWidget(
            get_app=lambda: self._app,
            text=text,
            speed=0.05,
            radius=1
        )
        return self._tool_call_widget

    def _create_thinking_window(self):
        self._thinking_widget = ThinkingWidget(
            get_app=lambda: self._app,
            title="Thinking...",
        )
        return self._thinking_widget

    def _create_input_window(self, placeholder: str = "ask, code, or command..."):
        """创建输入窗口"""

        def accept_handler(buffer: Buffer):
            """处理输入确认"""
            text = buffer.text
            if text and self._on_input_callback:
                self._on_input_callback(text)
            # 清空输入缓冲区
            buffer.reset()
            return True

        input_buffer = Buffer(
            completer=SmartCompleter(),
            complete_while_typing=True,
            history=FileHistory(Environment.get_instance().get_runtime_config().settings_dir / ".eflycode_history"),
            auto_suggest=AutoSuggestFromHistory(),
            multiline=True,
            accept_handler=accept_handler,
        )

        self._input_widget = InputWidget(
            buffer=input_buffer,
            prompt=" > ",
            placeholder=placeholder
        )
        return self._input_widget


class ConsoleAgentEventUI(AgentUIEventHandlerMixin):
    """
    控制台事件UI
    """

    def __init__(self, event_bus: EventBus) -> None:
        AgentUIEventHandlerMixin.__init__(self, event_bus)
        self.app = ConsoleUIApplication(on_input_callback=self._emit_user_input, event_bus=self._event_bus)
        
        # 显式订阅Agent相关事件
        self._event_bus.subscribe(AgentUIEventType.MESSAGE_START, self.handle_event)
        self._event_bus.subscribe(AgentUIEventType.MESSAGE_UPDATE, self.handle_event)
        self._event_bus.subscribe(AgentUIEventType.MESSAGE_END, self.handle_event)
        self._event_bus.subscribe(AgentUIEventType.TOOL_CALL_START, self.handle_event)
        self._event_bus.subscribe(AgentUIEventType.TOOL_CALL_END, self.handle_event)
        self._event_bus.subscribe(AgentUIEventType.TOOL_CALL_FINISH, self.handle_event)
        self._event_bus.subscribe(AgentUIEventType.TOOL_CALL_ERROR, self.handle_event)
        
        # 订阅UI相关事件
        self._event_bus.subscribe(UIEventType.START_APP, self.handle_event)
        self._event_bus.subscribe(UIEventType.SHOW_WELCOME, self.handle_event)
        self._event_bus.subscribe(UIEventType.SHOW_HELP, self.handle_event)
        self._event_bus.subscribe(UIEventType.CLEAR_SCREEN, self.handle_event)
        self._event_bus.subscribe(UIEventType.INFO, self.handle_event)
        self._event_bus.subscribe(UIEventType.WARNING, self.handle_event)
        self._event_bus.subscribe(UIEventType.ERROR, self.handle_event)

    def _emit_user_input(self, text: str) -> None:
        self._event_bus.emit(UIEventType.USER_INPUT_RECEIVED, {"text": text})

    def _handle_start_app(self, data: dict) -> None:
        """处理启动应用事件"""
        # UI现在直接在主线程运行，不需要额外启动
        pass

    def _handle_stop_app(self, data: dict) -> None:
        """处理停止应用事件"""
        logger.info("收到停止应用事件，发送UI退出信号...")
        # 不直接退出UI，而是发送QUIT_UI事件让主线程处理
        self._event_bus.emit(UIEventType.QUIT_UI)

    def _handle_show_welcome(self, data: dict) -> None:
        """处理显示欢迎事件"""
        def _show_welcome():
            self.app.welcome()
        self.app.run_ui(_show_welcome)

    def _handle_show_help(self, data: dict) -> None:
        """处理显示帮助事件"""
        def _show_help():
            self.app.help()
        self.app.run_ui(_show_help)

    def _handle_clear_screen(self, data: dict) -> None:
        """处理清屏事件"""
        def _clear_screen():
            self.app.clear()
        self.app.run_ui(_clear_screen)

    def _handle_think_start(self, data: dict) -> None:
        """处理思考开始事件"""
        # TODO: 实现思考状态UI显示
        pass

    def _handle_think_update(self, data: dict) -> None:
        """处理思考更新事件"""
        # TODO: 实现思考内容更新
        pass

    def _handle_think_end(self, data: dict) -> None:
        """处理思考结束事件"""
        # TODO: 实现思考状态结束
        pass

    def _handle_message_start(self, data: dict) -> None:
        """处理消息开始事件"""
        # TODO: 实现消息显示开始
        pass

    def _handle_message_update(self, data: dict) -> None:
        """处理消息更新事件"""
        text = data.get("text", "")
        if text:
            # 通过安全接口显示消息内容
            def _show_message():
                self.app.info(text)
            self.app.run_ui(_show_message)

    def _handle_message_end(self, data: dict) -> None:
        """处理消息结束事件"""
        # TODO: 实现消息显示结束
        pass

    def _handle_tool_call_start(self, data: dict) -> None:
        """处理工具调用开始事件"""
        name = data.get("name", "")
        if name:
            self.app.start_tool_call(name)

    def _handle_tool_call_end(self, data: dict) -> None:
        """处理工具调用结束事件"""
        name = data.get("name", "")
        args = data.get("args", {})
        if name:
            self.app.execute_tool_call(name, str(args))

    def _handle_tool_call_finish(self, data: dict) -> None:
        """处理工具调用完成事件"""
        name = data.get("name", "")
        args = data.get("args", {})
        result = data.get("result", "")
        if name:
            self.app.finish_tool_call(name, str(args), result)

    def _handle_tool_call_error(self, data: dict) -> None:
        """处理工具调用错误事件"""
        name = data.get("name", "")
        args = data.get("args", {})
        error = data.get("error", "")
        if name:
            self.app.fail_tool_call(name, str(args), error)

    def _handle_code_diff(self, data: dict) -> None:
        """处理代码差异事件"""
        # TODO: 实现代码差异显示
        pass

    def _handle_terminal_exec_start(self, data: dict) -> None:
        """处理终端执行开始事件"""
        # TODO: 实现终端执行状态显示
        pass

    def _handle_terminal_exec_running(self, data: dict) -> None:
        """处理终端执行运行事件"""
        # TODO: 实现终端执行进度显示
        pass

    def _handle_terminal_exec_end(self, data: dict) -> None:
        """处理终端执行结束事件"""
        # TODO: 实现终端执行结果显示
        pass

    def _handle_progress_start(self, data: dict) -> None:
        """处理进度开始事件"""
        # TODO: 实现进度条显示
        pass

    def _handle_progress_update(self, data: dict) -> None:
        """处理进度更新事件"""
        # TODO: 实现进度更新
        pass

    def _handle_progress_end(self, data: dict) -> None:
        """处理进度结束事件"""
        # TODO: 实现进度完成
        pass

    def _handle_file_open(self, data: dict) -> None:
        """处理文件打开事件"""
        # TODO: 实现文件打开显示
        pass

    def _handle_file_update(self, data: dict) -> None:
        """处理文件更新事件"""
        # TODO: 实现文件更新显示
        pass

    def _handle_user_input(self, data: dict) -> None:
        """处理用户输入事件"""
        # TODO: 实现用户输入处理
        pass

    def _handle_info(self, data: dict) -> None:
        """处理信息事件"""
        message = data.get("message", "")
        if message:
            def _show_info():
                self.app.info(message)
            self.app.run_ui(_show_info)

    def _handle_warning(self, data: dict) -> None:
        """处理警告事件"""
        message = data.get("message", "")
        if message:
            def _show_warning():
                self.app.warning(message)
            self.app.run_ui(_show_warning)

    def _handle_error(self, data: dict) -> None:
        """处理错误事件"""
        error = data.get("error", "")
        if error:
            def _show_error():
                self.app.error(error)
            self.app.run_ui(_show_error)

    def _handle_user_confirm(self, data: dict) -> None:
        """处理用户确认事件"""
        # TODO: 实现用户确认对话框
        pass
