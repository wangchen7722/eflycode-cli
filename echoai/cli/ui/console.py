import sys
from typing import List, Literal, Optional, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text


class LoadingUI:

    def __init__(self, console: Console, description: str):
        self.console = console
        self.description = description

        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[cyan]{task.description}", style="bold green"),
            console=self.console
        )
        self._task = self._progress.add_task(description, total=100)

    def start(self):
        self._progress.start()
        return self

    def stop(self, success: bool = True):
        if success:
            self._progress.update(self._task, description=f"✅ {self.description}", completed=100)
        else:
            self._progress.update(self._task, description=f"❌ {self.description}", completed=100)
        self._progress.stop()

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


class ConsoleUI:
    """终端用户界面类，处理用户输入输出和UI展示"""

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
        self.console = Console()

        self._initialized = True

    def flush(self) -> None:
        """刷新控制台输出"""
        self.console.file.flush()

    def acquire_user_input(self, text: str = "", choices: Optional[List[str]] = None) -> str:
        """获取用户输入

        Returns:
            str: 用户输入的内容
        """
        return Prompt.ask(f"user{text}", choices=choices)

    def exit(self) -> None:
        """退出控制台程序"""
        self.console.print("[green]Bye!!![/green]")
        sys.exit(0)

    def create_loading(self, description: str) -> LoadingUI:
        """创建进度条

        Args:
            description: 进度条描述

        Yields:
            Progress: 进度条对象
        """
        return LoadingUI(self.console, description)
        # progress = Progress(
        #     SpinnerColumn(),
        #     TextColumn("[cyan]{task.description}", style="bold green"),
        #     console=self.console
        # )
        # task = progress.add_task(description, total=100)
        # try:
        #     progress.start()
        #     yield progress
        # finally:
        #     progress.update(task, description=f"✅ {description}", completed=100)
        #     progress.stop()
        # self.show_panel([], f"✅ {description}")

    def show_help(self) -> None:
        """显示帮助信息"""
        self.show_table(
            "",
            ["命令", "描述"],
            [
                ["help", "显示帮助信息"],
                ["quit", "退出程序"]
            ]
        )

    def show_text(self, text: str, **kwargs) -> None:
        """显示文本内容

        Args:
            text: 要显示的文本内容
        """
        self.console.print(text, **kwargs)

    def show_error(self, message: str) -> None:
        """显示错误信息
        
        Args:
            message: 错误信息
        """
        self.console.print(f"[red]❌: {message}[/red]")

    def show_success(self, message: str) -> None:
        """显示成功信息
        
        Args:
            message: 成功信息
        """
        self.console.print(f"[green]✅: {message}[/green]")

    def show_panel(self, titles: Sequence[str], content: str, color: str = "green",
                   align: Literal["default", "left", "center", "right", "full"] = "default") -> None:
        """显示面板
        
        Args:
            titles: 面板标题列表，多个标题将以 | 分隔符连接
            content: 面板内容，将显示在面板主体部分
            color: 面板边框颜色，默认为绿色
            align: 内容对齐方式，可选值包括:
                - default: 默认对齐
                - left: 左对齐
                - center: 居中对齐
                - right: 右对齐
                - full: 两端对齐
        """
        panel = Panel(
            Text(content, justify=align),
            title=" | ".join(titles),
            title_align="left",
            border_style=color
        )
        self.console.print(panel)

    def show_table(self, title: str, columns: List[str], rows: List[List[str]]) -> None:
        """显示表格内容
        
        Args:
            title: 表格标题
            columns: 列配置列表，每个字典包含name和style
            rows: 行数据列表
        """
        if len(columns) != len(rows[0]):
            raise ValueError("列数和行数不匹配")

        table = Table(title=title)
        for column in columns:
            table.add_column(column, style="default", width=20)

        for row in rows:
            table.add_row(*row)

        self.console.print(table)

    # def run(self):
    #     """运行控制台界面，返回用户输入内容

    #     Yields:
    #         str: 用户输入的内容
    #     """
    #     self.show_help()

    #     while True:
    #         try:
    #             user_input = self.acquire_user_input()
    #             if not user_input:
    #                 continue
    #             if user_input == "quit":
    #                 self.exit()
    #             yield user_input
    #         except KeyboardInterrupt:
    #             self.show_error("用户中断程序")
    #             self.exit()
    #         except Exception as e:
    #             self.show_error(str(e))

    @classmethod
    def get_instance(cls) -> "ConsoleUI":
        """获取控制台UI实例
        
        如果实例尚未初始化，将抛出异常
        
        Returns:
            ConsoleUI: 控制台UI实例
        """
        if cls._instance is None or not getattr(cls._instance, "_initialized", False):
            raise RuntimeError("ConsoleUI尚未初始化，请先调用构造函数")
        return cls._instance


console_ui = ConsoleUI()
