import sys
import threading
import os
import time
from typing import Iterable, List, Literal, Optional, Sequence

from prompt_toolkit.document import Document
from pydantic_core.core_schema import FloatSchema
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, TextColumn, BarColumn
from rich.table import Table
from rich.text import Text
from rich.align import Align

from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout import CompletionsMenu, Dimension, Float, FloatContainer, HSplit, Layout, MultiColumnCompletionsMenu
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.layout.containers import Window, ConditionalContainer
from prompt_toolkit.application import Application
from prompt_toolkit.keys import Keys
from prompt_toolkit.styles import Style
from prompt_toolkit.completion import Completer, Completion, CompleteEvent
from prompt_toolkit.buffer import Buffer

from eflycode.ui.components import GlowingTextWidget, ThinkingWidget
from eflycode.constant import EFLYCODE_VERSION
from eflycode.ui.colors import PTK_STYLE
from eflycode.ui.base_ui import BaseUI
from eflycode.ui.event import AgentUIEventHandlerMixin
from eflycode.util.event_bus import EventBus
from eflycode.env import Environment
from eflycode.ui.command import BaseCommand, get_builtin_commands

EFLYCODE_BANNER = r"""
        _____  _          ____            _       
   ___ |  ___|| | _   _  / ___| ___    __| |  ___ 
  / _ \| |_   | || | | || |    / _ \  / _` | / _ \
 |  __/|  _|  | || |_| || |___| (_) || (_| ||  __/
  \___||_|    |_| \__, | \____|\___/  \__,_| \___|
                  |___/                           
"""


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


class ConsoleUI(BaseUI):
    """终端用户界面类 处理用户输入输出和UI展示"""

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        """实现单例模式"""
        if cls._instance is None:
            cls._instance = super(ConsoleUI, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """初始化控制台 UI"""
        # 避免重复初始化
        if getattr(self, "_initialized", False):
            return
        self.console = Console(tab_size=4, highlight=False)
        self._lock = threading.Lock()
        self._initialized = True

    def welcome(self) -> None:
        """显示欢迎信息"""
        self.clear()
        environment = Environment.get_instance()

        # 版本信息
        product = Text()
        product.append(">_ ", style="bold grey50")
        product.append("eFlyCode", style="bold white")
        product.append(" ", style="")
        product.append(f"(v{EFLYCODE_VERSION})", style="bold grey50")

        # 模型和工作目录等基本信息
        info = Text()
        info.append("model:     ", style="grey50")
        info.append(environment.get_llm_config().name, style="white")
        info.append("\n", style="")
        info.append("directory: ", style="grey50")
        info.append(f"{environment.get_runtime_config().workspace_dir}", style="white")

        panel_content = Text.assemble(product, "\n\n", info)
        panel = Panel(
            Align.left(panel_content),
            border_style="grey35",
            expand=False,
            padding=(0, 2),
        )

        self.console.print(panel)

    def flush(self) -> None:
        """刷新控制台输出"""
        with self._lock:
            self.console.file.flush()

    def clear(self) -> None:
        """清空控制台屏幕"""
        with self._lock:
            self.console.clear()

    def acquire_user_input(self, placeholder: str = "ask, code or command...",
                           choices: Optional[List[str]] = None) -> str:
        """获取用户输入

        Args:
            placeholder: 输入框占位符文本
            choices: 可选的备选项列表 若提供则启用自动补全

        Returns:
            str: 用户输入的内容
        """
        application = [None]

        def get_app() -> Application:
            return application[0]

        # ===================== Key Bindings ======================
        key_bindings = KeyBindings()

        # Ctrl + C 用于取消输入
        @key_bindings.add(Keys.ControlC)
        def _handle_ctrl_c(event: KeyPressEvent):
            event.app.exit(exception=KeyboardInterrupt)

        # Alt + Enter 用于插入换行
        @key_bindings.add(Keys.Escape, Keys.Enter)
        def _handle_ctrl_enter(event: KeyPressEvent):
            event.current_buffer.insert_text("\n")

        # Enter 用于提交输入
        @key_bindings.add(Keys.Enter)
        def _handle_enter(event: KeyPressEvent):
            # 如果当前是补全状态，则不插入换行
            if event.current_buffer.complete_state:
                completion = event.current_buffer.complete_state.current_completion
                if completion:
                    event.current_buffer.apply_completion(completion)
                else:
                    if event.current_buffer.text:
                        event.current_buffer.validate_and_handle()
            else:
                if event.current_buffer.text:
                    event.current_buffer.validate_and_handle()

        # Backspace 删除前一个字符并触发补全
        @key_bindings.add(Keys.Backspace)
        def _handle_backspace(event: KeyPressEvent):
            buffer = event.current_buffer
            if buffer.text:
                buffer.delete_before_cursor(count=1)
                if len(buffer.text) > 0 and buffer.text[-1] in ["/", "#", "@"]:
                    buffer.start_completion(select_first=False)

        # ===================== Buffer =====================
        def accept_handler(buffer: Buffer):
            app = get_app()
            if app is None:
                return
            app.exit(
                result=buffer.document.text
            )
            return True

        input_buffer = Buffer(
            completer=SmartCompleter(),
            complete_while_typing=True,
            history=FileHistory(Environment.get_instance().get_runtime_config().settings_dir / ".eflycode_history"),
            auto_suggest=AutoSuggestFromHistory(),
            multiline=True,
            accept_handler=accept_handler,
        )

        # ===================== Bottom Toolbar =====================
        @Condition
        def toolbar_condition():
            return input_buffer.text.strip() == ""

        def toolbar_content():
            return FormattedText([
                ("", "[ @ ]"), ("", " Skills "),
                ("", "   "),
                ("", "[ # ]"), ("", " Files "),
                ("", "   "),
                ("", "[ / ]"), ("", " Commands "),
            ])

        toolbar_window = ConditionalContainer(
            Window(
                FormattedTextControl(lambda: toolbar_content()),
                height=1,
            ),
            filter=toolbar_condition
        )

        # ===================== Completion =====================
        completions_float = Float(
            xcursor=True,
            ycursor=True,
            transparent=True,
            content=CompletionsMenu(
                max_height=5,
                scroll_offset=1,
                extra_filter=has_focus(input_buffer)
            )
        )

        multi_completions_float = Float(
            xcursor=True,
            ycursor=True,
            transparent=True,
            content=MultiColumnCompletionsMenu(
                extra_filter=has_focus(input_buffer)
            )
        )

        # ===================== Input Window =====================
        PROMPT_TEXT = " > "

        def get_line_prefix(line_number: int, wrap_count: int) -> FormattedText:
            if line_number == 0:
                return FormattedText([("class:prompt", PROMPT_TEXT)])
            else:
                return FormattedText([("class:prompt", " " * len(PROMPT_TEXT))])

        empty_window = Window(height=1, char=" ", dont_extend_height=True)
        input_window = Window(
            BufferControl(
                buffer=input_buffer,
            ),
            height=Dimension(min=1, max=5, preferred=1),
            wrap_lines=True,
            get_line_prefix=get_line_prefix,
            dont_extend_height=True,
        )

        # ==================== Placeholder =====================
        @Condition
        def placeholder_condition():
            return input_buffer.text.strip() == ""

        placeholder_window = ConditionalContainer(
            Window(
                FormattedTextControl(
                    lambda: FormattedText([("class:placeholder", placeholder)])
                ),
                height=1,
            ),
            filter=placeholder_condition
        )
        placeholder_float = Float(
            left=len(PROMPT_TEXT),
            top=0,
            hide_when_covering_content=True,
            content=placeholder_window,
        )

        root_container = FloatContainer(
            content=HSplit([
                input_window,
                empty_window,
                toolbar_window,
            ]),
            floats=[completions_float, multi_completions_float, placeholder_float],
        )

        layout = Layout(root_container, focused_element=input_window)

        application[0] = Application(
            layout=layout,
            key_bindings=key_bindings,
            style=PTK_STYLE,
            mouse_support=True,
            full_screen=False,
        )
        result = get_app().run(
            handle_sigint=True,
        )
        return result

    def exit(self) -> None:
        """退出控制台程序"""
        with self._lock:
            self.console.print("[green]Bye!!![/green]")
        sys.exit(0)

    def progress(self, description: str, iterable, total=None):
        """显示进度条并迭代处理数据
        
        Args:
            description: 进度条描述
            iterable: 可迭代对象
            total: 总数量 如果不提供则尝试从iterable获取长度
            
        Yields:
            迭代器中的每个元素
            
        Example:
            for item in ui.progress("处理数据", data_list):
                # 处理每个item
                process_item(item)
        """
        if total is None:
            try:
                total = len(iterable)
            except TypeError:
                total = None

        with self._lock:
            progress = Progress(
                TextColumn("[bright_green]{task.description}", style="bold"),
                BarColumn(),
                TextColumn("[bright_blue][progress.percentage]{task.percentage:>3.0f}%"),
                console=self.console
            )

            with progress:
                task = progress.add_task(description, total=total)

                try:
                    for item in iterable:
                        yield item
                        progress.advance(task, 1)
                except Exception as e:
                    raise e

    def help(self, commands: List[List[str]]) -> None:
        """显示帮助信息

        Args:
            commands: 命令列表 每个元素为 {"name": "命令名", "desc": "命令描述"}
        """
        self.table(
            "",
            ["命令", "描述"],
            commands
        )

    def info(self, text: str, **kwargs) -> None:
        """显示信息内容

        Args:
            text: 要显示的信息内容
        """
        with self._lock:
            end = kwargs.pop("end", "\n")
            self.console.print(text, end=end, **kwargs)

    def error(self, message: str) -> None:
        """显示错误信息
        
        Args:
            message: 错误信息
        """
        with self._lock:
            self.console.print(f"[red]{message}[/red]")

    def success(self, message: str) -> None:
        """显示成功信息
        
        Args:
            message: 成功信息
        """
        with self._lock:
            self.console.print(f"[green]{message}[/green]")

    def warning(self, message: str) -> None:
        """显示警告信息
        
        Args:
            message: 警告信息
        """
        with self._lock:
            self.console.print(f"[yellow]{message}[/yellow]")

    def panel(self, titles: Sequence[str], content: str, color: str = "green",
              align: Literal["default", "left", "center", "right", "full"] = "default",
              style: Optional[str] = None) -> None:
        """显示面板
        
        Args:
            titles: 面板标题列表 多个标题将以 | 分隔符连接
            content: 面板内容 将显示在面板主体部分
            color: 面板边框颜色 默认为绿色
            align: 内容对齐方式 可选值包括 default left center right full
            style: 边框样式 可选值包括 bold dim italic 等，会与color组合使用
        """
        # 构建边框样式字符串
        border_style = color
        if style:
            border_style = f"{style} {color}"

        panel = Panel(
            Text(content, justify=align),
            title=" | ".join(titles),
            title_align="left",
            border_style=border_style
        )
        with self._lock:
            self.console.print(panel)

    def table(self, title: str, columns: List[str], rows: List[List[str]]) -> None:
        """显示表格内容
        
        Args:
            title: 表格标题
            columns: 列配置列表 每个字典包含name和style
            rows: 行数据列表
        """
        if len(columns) != len(rows[0]):
            raise ValueError("列数和行数不匹配")

        table = Table(title=title)
        for column in columns:
            table.add_column(column, style="default", width=20)

        for row in rows:
            table.add_row(*row)

        with self._lock:
            self.console.print(table)

    def choices(self, tip: str, choices: List[str]) -> str:
        """提供一个可滚动的选择列表供用户选择
        
        Args:
            tip: 提示文本
            choices: 选项列表 不可为空
        
        Returns:
            str: 用户选择的结果 若用户取消或未选择则返回空字符串
        
        Raises:
            ValueError: 当选项列表为空时抛出
        """
        if not choices:
            raise ValueError("Choices cannot be empty.")

        # 计算可见选项数量 预留提示与缓冲区
        try:
            terminal_height = os.get_terminal_size().lines
        except OSError:
            terminal_height = 25
        max_visible_choices = max(5, terminal_height - 4)

        bindings = KeyBindings()
        selected_index = [0]
        start_index = [0]
        cancelled = [False]

        @bindings.add(Keys.Up)
        def _up(event):  # noqa: ANN001
            selected_index[0] = (selected_index[0] - 1 + len(choices)) % len(choices)
            if selected_index[0] < start_index[0]:
                start_index[0] = selected_index[0]
            elif selected_index[0] == len(choices) - 1:
                start_index[0] = max(0, len(choices) - max_visible_choices)
            event.app.invalidate()

        @bindings.add(Keys.Down)
        def _down(event):  # noqa: ANN001
            selected_index[0] = (selected_index[0] + 1) % len(choices)
            if selected_index[0] >= start_index[0] + max_visible_choices:
                start_index[0] = selected_index[0] - max_visible_choices + 1
            elif selected_index[0] == 0:
                start_index[0] = 0
            event.app.invalidate()

        @bindings.add(Keys.Enter)
        def _handle_enter(event):
            event.app.exit(result=choices[selected_index[0]])

        @bindings.add(Keys.Escape, Keys.Enter)
        def _handle_alt_enter(event):
            event.current_buffer.insert_text('\n')

        @bindings.add(Keys.ControlC)
        def _cancel(event):
            cancelled[0] = True
            event.app.exit(result="")

        def get_prompt_tokens():
            tokens = [("class:question", f"{tip} (使用上下箭头选择, Enter确认)\n")]

            end_index = min(start_index[0] + max_visible_choices, len(choices))
            visible_choices_slice = choices[start_index[0]:end_index]

            if start_index[0] > 0:
                tokens.append(("class:indicator", "  ... (更多选项在上方) ...\n"))

            for i, choice in enumerate(visible_choices_slice, start=start_index[0]):
                if i == selected_index[0]:
                    tokens.append(("class:selected", f"> {choice}\n"))
                else:
                    tokens.append(("", f"  {choice}\n"))

            if end_index < len(choices):
                tokens.append(("class:indicator", "  ... (更多选项在下方) ...\n"))

            return FormattedText(tokens)

        style = Style.from_dict({
            "question": "bold",
            "selected": "bg:#696969 #ffffff",
            "indicator": "fg:gray",
        })

        layout = Layout(
            container=Window(
                content=FormattedTextControl(
                    text=get_prompt_tokens,
                    focusable=True,
                )
            )
        )

        app = Application(
            layout=layout,
            key_bindings=bindings,
            style=style,
            mouse_support=True,
            full_screen=True,
        )

        with patch_stdout():
            result = app.run()

        if cancelled[0]:
            return ""
        return result if result is not None else ""

    def print(self, text: str, end: str = "\n") -> None:
        """打印文本到控制台
        
        Args:
            text: 要打印的文本内容
            end: 打印结束时的字符串，默认为换行符
        """
        with self._lock:
            self.console.print(text, end=end)

    @classmethod
    def get_instance(cls) -> "ConsoleUI":
        """获取控制台UI实例
        
        如果实例尚未初始化 将抛出异常
        
        Returns:
            ConsoleUI: 控制台UI实例
        """
        if cls._instance is None or not getattr(cls._instance, "_initialized", False):
            raise RuntimeError("ConsoleUI尚未初始化 请先调用构造函数")
        return cls._instance
    

class ConsoleAgentUI(ConsoleUI):
    """控制台应用程序类 处理用户输入输出和UI展示"""
    
    def __init__(self) -> None:
        """初始化控制台应用程序"""
        super().__init__()
        self._lock = threading.Lock()
        self._main_layout = self._create_main_layout()
        self._context: Literal["tool_call", "thinking", ""] = ""
        self._app: Application = Application(
            layout=self._main_layout,
            style=PTK_STYLE,
            mouse_support=True,
            full_screen=False,
            erase_when_done=False
        )
        
        # 功能组件
        self.tool_call_widget: GlowingTextWidget | None = None
        self.thinking_widget: ThinkingWidget | None = None
        self._running = False

    def get_app(self) -> Application:
        """获取应用程序实例"""
        return self._app
    
    def run(self):
        self._running = True
        self._app.run(handle_sigint=True)
        
    def exit(self):
        with self._lock:
            self._running = False
            if self._app.is_running:
                self._app.exit()
    
    def show_main(self):
        """显示主界面"""
        with self._lock:
            self._context = ""
            self._app.layout = self._main_layout
            self._app.invalidate()
        
    def start_tool_call(self, name: str):
        """开始工具调用"""
        with self._lock:
            self._context = "tool_call"
            self._app.layout = self._create_tool_call_layout(f"Calling {name}")
            if self.tool_call_widget:
                self.tool_call_widget.start()
            self._app.invalidate()
            
    def execute_tool_call(self, name: str, args: str):
        """执行工具调用"""
        with self._lock:
            if self._context != "tool_call":
                return
            
            if self.tool_call_widget:
                # 将内容替换为执行信息
                self.tool_call_widget.update_text(f"Running {name}")
                
    def finish_tool_call(self, name: str, args: str, result: str):
        """完成工具调用"""
        with self._lock:
            if self._context != "tool_call":
                return
            
            if self.tool_call_widget:
                # 停止动画线程
                self.tool_call_widget.stop()
                # 将内容替换为执行信息
                self.tool_call_widget.update_text(f"{name} completed")
                # 手动刷新
                self._app.invalidate()
            
        # 恢复主界面
        self.show_main()

        if result:
            self.panel(
                titles=["Tool Call - " + name],
                content="\n".join([f"Args: {args}", f"Result: {result}"]),
                color="green",
            )
            
        
    def _create_main_layout(self) -> Layout:
        """创建主布局"""
        return Layout(
            Window(
                content=FormattedTextControl(text=""),
                height=1,
                dont_extend_height=True,
            )
        )

    def _create_tool_call_layout(self, display_text: str) -> Layout:
        """创建工具调用布局"""
        self.tool_call_widget = GlowingTextWidget(
            get_app=self.get_app,
            text=display_text,
            speed=0.05,
            radius=1,
        )
        return Layout(self.tool_call_widget)
        
    def _create_thinking_layout(self) -> Layout:
        """创建思考布局"""
        self.thinking_widget = ThinkingWidget(
            get_app=self.get_app,
            title="Thinking...",
        )
        return Layout(self.thinking_widget)


class ConsoleAgentEventUI(AgentUIEventHandlerMixin, ConsoleAgentUI):
    """
    控制台事件UI
    """

    def __init__(self, event_bus: EventBus) -> None:
        AgentUIEventHandlerMixin.__init__(self, event_bus)
        ConsoleAgentUI.__init__(self)

        # 是否处于输入状态

    def _handle_show_welcome(self, data: dict) -> None:
        self.welcome()

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
        print("handle_tool_call_start", data)

    def _handle_tool_call_end(self, data: dict) -> None:
        print("handle_tool_call_end", data)

    def _handle_tool_call_finish(self, data: dict) -> None:
        print("handle_tool_call_finish", data)

    def _handle_tool_call_error(self, data: dict) -> None:
        print("handle_tool_call_error", data)

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
        print("handle_error", data)

    def _handle_user_input(self, data: dict) -> None:
        print("handle_user_input", data)

    def _handle_user_confirm(self, data: dict) -> None:
        print("handle_user_confirm", data)
