import sys
import threading
import os
from typing import List, Literal, Optional, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, TextColumn, BarColumn
from rich.table import Table
from rich.text import Text
from rich.align import Align

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.containers import Window, HSplit, ConditionalContainer, FloatContainer, Float
from prompt_toolkit.application import Application
from prompt_toolkit.widgets import TextArea, Frame
from prompt_toolkit.keys import Keys
from prompt_toolkit.filters import Condition
from prompt_toolkit.styles import Style

from eflycode.ui.colors import PTK_STYLE
from eflycode.ui.base_ui import BaseUI
from eflycode.ui.event import AgentUIEventHandlerMixin
from eflycode.util.event_bus import EventBus

EFLYCODE_BANNER = r"""
        _____  _          ____            _       
   ___ |  ___|| | _   _  / ___| ___    __| |  ___ 
  / _ \| |_   | || | | || |    / _ \  / _` | / _ \
 |  __/|  _|  | || |_| || |___| (_) || (_| ||  __/
  \___||_|    |_| \__, | \____|\___/  \__,_| \___|
                  |___/                           
"""

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
        """初始化控制台UI"""
        # 避免重复初始化
        if getattr(self, "_initialized", False):
            return
        self.console = Console(tab_size=4, highlight=False)
        self._lock = threading.Lock()

        self._ptk_session = PromptSession(history=InMemoryHistory())

        self._initialized = True


    def welcome(self) -> None:
        """显示欢迎信息"""
        self.clear()
        # self.console.print(f"[bold #081776]{EFLYCODE_BANNER}[/bold #081776]")
        product = Text()
        product.append(">_ ", style="grey50")
        product.append("eFlyCode", style="bold white")
        product.append(" ", style="")
        product.append("(v0.46.0)", style="grey50")
        panel = Panel(
            Align.left(product),
            border_style="grey35",
            expand=False,
            padding=(0, 2),
        )

        self.console.print(panel)
        # self.panel(titles=[], content=">_ eFlyCode 智能编程助手")

    def flush(self) -> None:
        """刷新控制台输出"""
        with self._lock:
            self.console.file.flush()

    def clear(self) -> None:
        """清空控制台屏幕"""
        with self._lock:
            self.console.clear()

    def acquire_user_input(self, text: str = "请输入内容…", choices: Optional[List[str]] = None, prompt: str = " > ") -> str:
        """获取用户输入

        Args:
            text: 输入框占位符文本
            choices: 可选的备选项列表 若提供则启用自动补全
            prompt: 输入框提示前缀

        Returns:
            str: 用户输入的内容
        """
        completer = None
        if choices:
            completer = WordCompleter(choices, ignore_case=True)

        # 结果与取消标志
        result: List[str] = [""]
        cancelled: List[bool] = [False]

        # 绑定 Ctrl+C 取消
        bindings = KeyBindings()

        @bindings.add(Keys.ControlC)
        def _handle_ctrl_c(event: KeyPressEvent):
            cancelled[0] = True
            event.app.exit()

        @bindings.add(Keys.Enter)
        def _handle_enter(event: KeyPressEvent):
            if event.current_buffer.text:
                result[0] = event.current_buffer.text
                event.app.exit()

        @bindings.add(Keys.Escape, Keys.Enter)
        def _handle_alt_enter(event: KeyPressEvent):
            event.current_buffer.insert_text('\n')

        # 输入区域和布局
        textarea = TextArea(
            multiline=True,
            prompt=FormattedText([("class:prompt", f"{prompt}")]),
            completer=completer,
            history=self._ptk_session.history,
            auto_suggest=AutoSuggestFromHistory(),
            style="class:input",
            wrap_lines=True,
            focusable=True,
            focus_on_click=True
        )

        @Condition
        def show_placeholder():
            return textarea.text == ""

        placeholder_text = text
        placeholder = ConditionalContainer(
            Window(
                content=FormattedTextControl(
                    text=[("class:placeholder", placeholder_text)],
                    show_cursor=True,
                ),
                height=1,
                dont_extend_height=True,
                dont_extend_width=True,
            ),
            filter=show_placeholder,
        )

        textarea_with_placeholder = FloatContainer(
            content=textarea,
            floats=[
                Float(
                    content=placeholder,
                    left=4,
                    top=0,
                    transparent=True
                )
            ],
        )

        body = HSplit([
            textarea_with_placeholder
        ])

        frame = Frame(body=body)

        app = Application(
            layout=Layout(container=body),
            key_bindings=bindings,
            mouse_support=False,
            full_screen=False,
            style=PTK_STYLE,
        )

        with patch_stdout():
            app.run()

        if cancelled[0]:
            raise KeyboardInterrupt
        return result[0]

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


class ConsoleEventUI(AgentUIEventHandlerMixin, ConsoleUI):
    """
    控制台事件UI
    """

    def __init__(self, event_bus: EventBus) -> None:
        super().__init__(event_bus)

    def _handle_think_start(self, data: dict) -> None:
        pass

    def _handle_think_update(self, data: dict) -> None:
        pass

    def _handle_think_end(self, data: dict) -> None:
        pass

    def _handle_message_start(self, data: dict) -> None:
        pass

    def _handle_message_update(self, data: dict) -> None:
        pass

    def _handle_message_end(self, data: dict) -> None:
        pass

    def _handle_tool_call_start(self, data: dict) -> None:
        pass

    def _handle_tool_call_end(self, data: dict) -> None:
        pass

    def _handle_tool_call_finish(self, data: dict) -> None:
        pass

    def _handle_tool_call_error(self, data: dict) -> None:
        pass

    def _handle_code_diff(self, data: dict) -> None:
        pass

    def _handle_terminal_exec_start(self, data: dict) -> None:
        pass

    def _handle_terminal_exec_running(self, data: dict) -> None:
        pass

    def _handle_terminal_exec_end(self, data: dict) -> None:
        pass

    def _handle_progress_start(self, data: dict) -> None:
        pass

    def _handle_progress_update(self, data: dict) -> None:
        pass

    def _handle_progress_end(self, data: dict) -> None:
        pass

    def _handle_file_open(self, data: dict) -> None:
        pass

    def _handle_file_update(self, data: dict) -> None:
        pass

    def _handle_info(self, data: dict) -> None:
        pass

    def _handle_warning(self, data: dict) -> None:
        pass

    def _handle_error(self, data: dict) -> None:
        pass

    def _handle_user_input(self, data: dict) -> None:
        pass

    def _handle_user_confirm(self, data: dict) -> None:
        pass
