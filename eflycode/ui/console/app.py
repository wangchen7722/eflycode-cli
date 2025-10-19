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

from eflycode.ui.event import UIEventType
from eflycode.ui.console.ui import ConsoleUI
from eflycode.ui.components import GlowingTextWidget, ThinkingWidget, InputWidget
from eflycode.ui.colors import PTK_STYLE
from eflycode.ui.event import AgentUIEventHandlerMixin
from eflycode.util.event_bus import EventBus
from eflycode.env import Environment
from eflycode.ui.command import BaseCommand, get_builtin_commands


class SmartCompleter(Completer):

    def __init__(self):
        self.commands: List[BaseCommand] = get_builtin_commands()
        self.skills: List[str] = []
        self.files: List[str] = []
        self.max_command_length = max(len(cmd.name) for cmd in self.commands) if self.commands else 0

    def get_completions(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        text = document.text_before_cursor
        if len(text) > 0:
            # 从当前光标位置向前取出与最大命令长度相同的文本进行匹配
            start_pos = max(0, len(text) - self.max_command_length)
            text = text[start_pos:]
            # 判断这段文本中是否含有 "/"，若含有找到 "/" 后的内容
            slash_index = text.rfind("/")
            if slash_index != -1:
                text = text[slash_index + 1:]
                for cmd in self.commands:
                    if cmd.name.startswith(text):
                        yield Completion(cmd.name, display=cmd.description, start_position=-len(text))

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

    def stop(self):
        """安全停止"""
        with self._lock:
            if self._running and self._app.is_running:
                self._app.exit()
            self._running = False
            if self._app_thread:
                self._app_thread.join(timeout=1.0)
                self._app_thread = None

    def start_tool_call(self, name: str):
        """开始工具调用"""
        with self._lock:
            self._state = UIState.TOOL_CALL
            self._app.layout = self._create_tool_call_layout(f"Calling {name}")
            if self._tool_call_widget:
                self._tool_call_widget.start()
            self._app.invalidate()

    def execute_tool_call(self, name: str, args: str):
        """执行工具调用"""
        with self._lock:
            if self._state != UIState.TOOL_CALL:
                return

            if self._tool_call_widget:
                # 将内容替换为执行信息
                self._tool_call_widget.update_text(f"Running {name}")

    def finish_tool_call(self, name: str, args: str, result: str):
        """完成工具调用"""
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

    def fail_tool_call(self, name: str, args: str, error: str):
        """失败工具调用"""
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

    def show_input(self):
        """显示输入窗口"""
        with self._lock:
            self._state = UIState.INPUT
            self._app.layout = self._create_input_layout()
            self._app.invalidate()

    def _mount_key_bindings(self) -> None:
        """挂载按键绑定"""
        key_bindings = KeyBindings()
         # Ctrl + C 用于取消输入
        @key_bindings.add(Keys.ControlC)
        def _handle_ctrl_c(event: KeyPressEvent):
            print("Ctrl+C pressed, exiting...")
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

    def _create_tool_call_window(self, text: str) -> None:
        self._tool_call_widget = GlowingTextWidget(
            get_app=lambda: self._app,
            text=text,
            speed=0.05,
            radius=1
        )
        return self._tool_call_widget

    def _create_thinking_window(self) -> None:
        self._thinking_widget = ThinkingWidget(
            get_app=lambda: self._app,
            title="Thinking...",
        )
        return self._thinking_widget

    def _create_input_window(self, placeholder: str = "ask, code, or command...") -> None:
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

    def _emit_user_input(self, text: str) -> None:
        self._event_bus.emit(UIEventType.USER_INPUT_RECEIVED, {"text": text})

    def _handle_start_app(self, data: dict) -> None:
        self.app.run_in_background()

    def _handle_stop_app(self, data: dict) -> None:
        self.app.stop()

    def _handle_show_welcome(self, data: dict) -> None:
        self.app.welcome()

    def _handle_think_start(self, data: dict) -> None:
        print("handle_think_start", data)

    def _handle_think_update(self, data: dict) -> None:
        print("handle_think_update", data)

    def _handle_think_end(self, data: dict) -> None:
        print("handle_think_end", data)

    def _handle_message_start(self, data: dict) -> None:
        print("handle_message_start", data)

    def _handle_message_update(self, data: dict) -> None:
        print("handle_message_update", data)

    def _handle_message_end(self, data: dict) -> None:
        print("handle_message_end", data)

    def _handle_tool_call_start(self, data: dict) -> None:
        self.app.start_tool_call(data["name"])

    def _handle_tool_call_end(self, data: dict) -> None:
        self.app.execute_tool_call(data["name"], data["args"])

    def _handle_tool_call_finish(self, data: dict) -> None:
        self.app.finish_tool_call(data["name"], data["args"], data["result"])

    def _handle_tool_call_error(self, data: dict) -> None:
        self.app.fail_tool_call(data["name"], data["args"], data["error"])

    def _handle_code_diff(self, data: dict) -> None:
        print("handle_code_diff", data)

    def _handle_terminal_exec_start(self, data: dict) -> None:
        print("handle_terminal_exec_start", data)

    def _handle_terminal_exec_running(self, data: dict) -> None:
        print("handle_terminal_exec_running", data)

    def _handle_terminal_exec_end(self, data: dict) -> None:
        print("handle_terminal_exec_end", data)

    def _handle_progress_start(self, data: dict) -> None:
        print("handle_progress_start", data)

    def _handle_progress_update(self, data: dict) -> None:
        print("handle_progress_update", data)

    def _handle_progress_end(self, data: dict) -> None:
        print("handle_progress_end", data)

    def _handle_file_open(self, data: dict) -> None:
        print("handle_file_open", data)

    def _handle_file_update(self, data: dict) -> None:
        print("handle_file_update", data)

    def _handle_info(self, data: dict) -> None:
        print("handle_info", data)

    def _handle_warning(self, data: dict) -> None:
        print("handle_warning", data)

    def _handle_error(self, data: dict) -> None:
        self.app.error(data["error"])

    def _handle_user_input(self, data: dict) -> None:
        print("handle_user_input", data)

    def _handle_user_confirm(self, data: dict) -> None:
        print("handle_user_confirm", data)
