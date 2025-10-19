import threading
import time
from typing import Optional, List, Callable, Any
from enum import Enum

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Layout, HSplit, VSplit, Float, FloatContainer, Dimension
from prompt_toolkit.layout.containers import Window, ConditionalContainer, ScrollOffsets
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout import CompletionsMenu, MultiColumnCompletionsMenu
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.text import Text

from eflycode.ui.colors import PTK_STYLE
from eflycode.ui.event import AgentUIEventHandlerMixin
from eflycode.ui.components import GlowingTextWidget, ThinkingWidget
from eflycode.ui.command import get_builtin_commands, BaseCommand
from eflycode.util.event_bus import EventBus
from eflycode.env import Environment


class UIState(Enum):
    """UI 状态枚举"""
    IDLE = "idle"                    # 空闲状态，显示输入框
    THINKING = "thinking"            # 思考状态，显示思考动画
    TOOL_CALLING = "tool_calling"    # 工具调用状态，显示工具调用动画
    PROCESSING = "processing"        # 处理状态，显示处理信息


class SmartCompleter(Completer):
    """智能补全器"""

    def __init__(self):
        self.commands: List[BaseCommand] = get_builtin_commands()
        self.skills: List[str] = []
        self.files: List[str] = []
        self.max_command_length = max(len(cmd.name) for cmd in self.commands) if self.commands else 0

    def get_completions(self, document: Document, complete_event):
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


class MainApplicationUI(AgentUIEventHandlerMixin):
    """
    统一的主应用程序 UI
    
    解决现有问题：
    1. 使用单一 Application 实例
    2. 输入区域和输出区域同时存在
    3. 事件驱动的状态管理
    4. 流畅的动画和状态切换
    """

    def __init__(self, event_bus: EventBus):
        super().__init__(event_bus)
        
        self._lock = threading.Lock()
        self._console = Console(tab_size=4, highlight=False)
        self._state = UIState.IDLE
        self._running = False
        
        # 输出内容缓存
        self._output_lines: List[FormattedText] = []
        self._max_output_lines = 1000
        
        # 组件
        self._thinking_widget: Optional[ThinkingWidget] = None
        self._tool_call_widget: Optional[GlowingTextWidget] = None
        
        # 创建应用程序组件
        self._setup_application()

    def _setup_application(self):
        """设置应用程序组件"""
        
        # ===================== 输入缓冲区 =====================
        def accept_handler(buffer: Buffer):
            """处理输入提交"""
            if self._app and self._app.is_running:
                # 获取输入内容
                input_text = buffer.document.text.strip()
                if input_text:
                    # 添加到输出区域
                    self._add_output_line(FormattedText([("class:user_input", f"> {input_text}")]))
                    # 清空输入缓冲区
                    buffer.reset()
                    # 触发输入事件
                    self._handle_user_input_submit(input_text)
                    # 刷新界面
                    self._app.invalidate()
            return True

        self._input_buffer = Buffer(
            completer=SmartCompleter(),
            complete_while_typing=True,
            history=FileHistory(Environment.get_instance().get_runtime_config().settings_dir / ".eflycode_history"),
            auto_suggest=AutoSuggestFromHistory(),
            multiline=True,
            accept_handler=accept_handler,
        )

        # ===================== 键绑定 =====================
        self._key_bindings = KeyBindings()

        @self._key_bindings.add(Keys.ControlC)
        def _handle_ctrl_c(event: KeyPressEvent):
            """Ctrl+C 退出应用程序"""
            if self._app and self._app.is_running:
                self._app.exit()

        @self._key_bindings.add(Keys.Escape, Keys.Enter)
        def _handle_alt_enter(event: KeyPressEvent):
            """Alt+Enter 插入换行"""
            event.current_buffer.insert_text("\n")

        @self._key_bindings.add(Keys.Enter)
        def _handle_enter(event: KeyPressEvent):
            """Enter 提交输入或应用补全"""
            buffer = event.current_buffer
            if buffer.complete_state:
                completion = buffer.complete_state.current_completion
                if completion:
                    buffer.apply_completion(completion)
                else:
                    if buffer.text.strip():
                        buffer.validate_and_handle()
            else:
                if buffer.text.strip():
                    buffer.validate_and_handle()

        @self._key_bindings.add(Keys.Backspace)
        def _handle_backspace(event: KeyPressEvent):
            """Backspace 删除字符并触发补全"""
            buffer = event.current_buffer
            if buffer.text:
                buffer.delete_before_cursor(count=1)
                if len(buffer.text) > 0 and buffer.text[-1] in ["/", "#", "@"]:
                    buffer.start_completion(select_first=False)

        # ===================== 创建布局 =====================
        self._create_layout()
        
        # ===================== 创建应用程序 =====================
        self._app = Application(
            layout=self._layout,
            key_bindings=self._key_bindings,
            style=PTK_STYLE,
            mouse_support=True,
            full_screen=False,
            erase_when_done=False
        )

    def _create_layout(self):
        """创建应用程序布局"""
        
        # ===================== 输出区域 =====================
        def get_output_content():
            """获取输出内容"""
            if not self._output_lines:
                return FormattedText([("", "")])
            return FormattedText([
                line for lines in self._output_lines for line in (lines if isinstance(lines, list) else [lines])
            ])

        self._output_control = FormattedTextControl(
            text=get_output_content,
            focusable=False,
            show_cursor=False
        )
        
        self._output_window = Window(
            content=self._output_control,
            height=Dimension(min=5, max=30, preferred=10),
            scroll_offsets=ScrollOffsets(bottom=1),
            wrap_lines=True,
        )

        # ===================== 状态区域 =====================
        def get_status_content():
            """获取状态内容"""
            if self._state == UIState.THINKING and self._thinking_widget:
                return self._thinking_widget.get_formatted_text()
            elif self._state == UIState.TOOL_CALLING and self._tool_call_widget:
                return self._tool_call_widget.get_formatted_text()
            else:
                return FormattedText([("", "")])

        self._status_control = FormattedTextControl(
            text=get_status_content,
            focusable=False,
            show_cursor=False
        )
        
        @Condition
        def show_status():
            return self._state in [UIState.THINKING, UIState.TOOL_CALLING]

        self._status_window = ConditionalContainer(
            Window(
                content=self._status_control,
                height=Dimension(min=1, max=3, preferred=2),
            ),
            filter=show_status
        )

        # ===================== 输入区域 =====================
        PROMPT_TEXT = " > "

        def get_line_prefix(line_number: int, wrap_count: int) -> FormattedText:
            if line_number == 0:
                return FormattedText([("class:prompt", PROMPT_TEXT)])
            else:
                return FormattedText([("class:prompt", " " * len(PROMPT_TEXT))])

        self._input_window = Window(
            BufferControl(buffer=self._input_buffer),
            height=Dimension(min=1, max=5, preferred=1),
            wrap_lines=True,
            get_line_prefix=get_line_prefix,
            dont_extend_height=True,
        )

        # ===================== 占位符 =====================
        @Condition
        def show_placeholder():
            return self._input_buffer.text.strip() == "" and self._state == UIState.IDLE

        placeholder_window = ConditionalContainer(
            Window(
                FormattedTextControl(
                    lambda: FormattedText([("class:placeholder", "ask, code or command...")])
                ),
                height=1,
            ),
            filter=show_placeholder
        )

        placeholder_float = Float(
            left=len(PROMPT_TEXT),
            top=0,
            hide_when_covering_content=True,
            content=placeholder_window,
        )

        # ===================== 工具栏 =====================
        @Condition
        def show_toolbar():
            return self._input_buffer.text.strip() == "" and self._state == UIState.IDLE

        def get_toolbar_content():
            return FormattedText([
                ("", "[ @ ]"), ("", " Skills "),
                ("", "   "),
                ("", "[ # ]"), ("", " Files "),
                ("", "   "),
                ("", "[ / ]"), ("", " Commands "),
            ])

        toolbar_window = ConditionalContainer(
            Window(
                FormattedTextControl(lambda: get_toolbar_content()),
                height=1,
            ),
            filter=show_toolbar
        )

        # ===================== 补全菜单 =====================
        completions_float = Float(
            xcursor=True,
            ycursor=True,
            transparent=True,
            content=CompletionsMenu(
                max_height=5,
                scroll_offset=1,
                extra_filter=has_focus(self._input_buffer)
            )
        )

        multi_completions_float = Float(
            xcursor=True,
            ycursor=True,
            transparent=True,
            content=MultiColumnCompletionsMenu(
                extra_filter=has_focus(self._input_buffer)
            )
        )

        # ===================== 主布局 =====================
        main_container = HSplit([
            self._output_window,
            self._status_window,
            Window(height=1, char=" ", dont_extend_height=True),  # 分隔线
            self._input_window,
            toolbar_window,
        ])

        self._layout = Layout(
            FloatContainer(
                content=main_container,
                floats=[completions_float, multi_completions_float, placeholder_float],
            ),
            focused_element=self._input_window
        )

    def _add_output_line(self, line: FormattedText):
        """添加输出行"""
        with self._lock:
            self._output_lines.append(line)
            # 限制输出行数
            if len(self._output_lines) > self._max_output_lines:
                self._output_lines = self._output_lines[-self._max_output_lines:]

    def _handle_user_input_submit(self, input_text: str):
        """处理用户输入提交"""
        # 这里可以触发相应的事件或回调
        # 例如：self._event_bus.publish("user_input_submit", {"text": input_text})
        pass

    def _set_state(self, state: UIState):
        """设置 UI 状态"""
        with self._lock:
            if self._state != state:
                self._state = state
                if self._app:
                    self._app.invalidate()

    def run(self):
        """运行应用程序"""
        self._running = True
        with patch_stdout():
            try:
                self._app.run(handle_sigint=True)
            except KeyboardInterrupt:
                pass
            finally:
                self._running = False

    def exit(self):
        """退出应用程序"""
        with self._lock:
            self._running = False
            if self._app and self._app.is_running:
                self._app.exit()

    def is_running(self) -> bool:
        """检查应用程序是否正在运行"""
        return self._running

    def add_output(self, text: str, style: str = ""):
        """添加输出文本"""
        if style:
            formatted_text = FormattedText([(style, text + "\n")])
        else:
            formatted_text = FormattedText([("", text + "\n")])
        
        self._add_output_line(formatted_text)
        
        if self._app:
            self._app.invalidate()

    def clear_output(self):
        """清空输出区域"""
        with self._lock:
            self._output_lines.clear()
            if self._app:
                self._app.invalidate()

    # ===================== 事件处理方法 =====================
    
    def _handle_show_welcome(self, data: dict) -> None:
        """处理欢迎事件"""
        self.add_output("Welcome to EflyCode!", "class:welcome")

    def _handle_think_start(self, data: dict) -> None:
        """处理思考开始事件"""
        self._thinking_widget = ThinkingWidget(
            get_app=lambda: self._app,
            title="Thinking..."
        )
        self._thinking_widget.start()
        self._set_state(UIState.THINKING)

    def _handle_think_update(self, data: dict) -> None:
        """处理思考更新事件"""
        if self._thinking_widget and data.get("content"):
            self._thinking_widget.update_content(data["content"])

    def _handle_think_end(self, data: dict) -> None:
        """处理思考结束事件"""
        if self._thinking_widget:
            self._thinking_widget.stop()
            self._thinking_widget = None
        self._set_state(UIState.IDLE)

    def _handle_message_start(self, data: dict) -> None:
        """处理消息开始事件"""
        self.add_output(f"Assistant: ", "class:assistant")

    def _handle_message_update(self, data: dict) -> None:
        """处理消息更新事件"""
        if data.get("content"):
            self.add_output(data["content"], "class:message")

    def _handle_message_end(self, data: dict) -> None:
        """处理消息结束事件"""
        self.add_output("", "")  # 添加空行

    def _handle_tool_call_start(self, data: dict) -> None:
        """处理工具调用开始事件"""
        tool_name = data.get("name", "Unknown Tool")
        self._tool_call_widget = GlowingTextWidget(
            get_app=lambda: self._app,
            text=f"Calling {tool_name}...",
            speed=0.05,
            radius=1,
        )
        self._tool_call_widget.start()
        self._set_state(UIState.TOOL_CALLING)

    def _handle_tool_call_end(self, data: dict) -> None:
        """处理工具调用执行事件"""
        tool_name = data.get("name", "Unknown Tool")
        if self._tool_call_widget:
            self._tool_call_widget.update_text(f"Running {tool_name}...")

    def _handle_tool_call_finish(self, data: dict) -> None:
        """处理工具调用完成事件"""
        tool_name = data.get("name", "Unknown Tool")
        result = data.get("result", "")
        
        if self._tool_call_widget:
            self._tool_call_widget.stop()
            self._tool_call_widget = None
        
        self._set_state(UIState.IDLE)
        
        # 显示工具调用结果
        self.add_output(f"✓ {tool_name} completed", "class:success")
        if result:
            self.add_output(f"Result: {result}", "class:result")

    def _handle_tool_call_error(self, data: dict) -> None:
        """处理工具调用错误事件"""
        tool_name = data.get("name", "Unknown Tool")
        error = data.get("error", "Unknown error")
        
        if self._tool_call_widget:
            self._tool_call_widget.stop()
            self._tool_call_widget = None
        
        self._set_state(UIState.IDLE)
        
        # 显示错误信息
        self.add_output(f"✗ {tool_name} failed", "class:error")
        self.add_output(f"Error: {error}", "class:error")

    def _handle_code_diff(self, data: dict) -> None:
        """处理代码差异事件"""
        self.add_output("Code changes detected", "class:info")

    def _handle_terminal_exec_start(self, data: dict) -> None:
        """处理终端执行开始事件"""
        command = data.get("command", "")
        self.add_output(f"$ {command}", "class:command")

    def _handle_terminal_exec_running(self, data: dict) -> None:
        """处理终端执行运行事件"""
        output = data.get("output", "")
        if output:
            self.add_output(output, "class:terminal_output")

    def _handle_terminal_exec_end(self, data: dict) -> None:
        """处理终端执行结束事件"""
        exit_code = data.get("exit_code", 0)
        if exit_code == 0:
            self.add_output("Command completed successfully", "class:success")
        else:
            self.add_output(f"Command failed with exit code {exit_code}", "class:error")

    def _handle_progress_start(self, data: dict) -> None:
        """处理进度开始事件"""
        description = data.get("description", "Processing...")
        self.add_output(f"Starting: {description}", "class:info")

    def _handle_progress_update(self, data: dict) -> None:
        """处理进度更新事件"""
        # 可以在这里更新进度条
        pass

    def _handle_progress_end(self, data: dict) -> None:
        """处理进度结束事件"""
        description = data.get("description", "Processing")
        self.add_output(f"Completed: {description}", "class:success")

    def _handle_file_open(self, data: dict) -> None:
        """处理文件打开事件"""
        filename = data.get("filename", "")
        self.add_output(f"Opened file: {filename}", "class:info")

    def _handle_file_update(self, data: dict) -> None:
        """处理文件更新事件"""
        filename = data.get("filename", "")
        self.add_output(f"Updated file: {filename}", "class:info")

    def _handle_info(self, data: dict) -> None:
        """处理信息事件"""
        message = data.get("message", "")
        self.add_output(message, "class:info")

    def _handle_warning(self, data: dict) -> None:
        """处理警告事件"""
        message = data.get("message", "")
        self.add_output(f"Warning: {message}", "class:warning")

    def _handle_error(self, data: dict) -> None:
        """处理错误事件"""
        message = data.get("message", "")
        self.add_output(f"Error: {message}", "class:error")

    def _handle_user_input(self, data: dict) -> None:
        """处理用户输入事件"""
        # 这个方法用于处理来自事件总线的用户输入事件
        pass

    def _handle_user_confirm(self, data: dict) -> None:
        """处理用户确认事件"""
        message = data.get("message", "Please confirm")
        self.add_output(f"Confirmation: {message}", "class:confirm")