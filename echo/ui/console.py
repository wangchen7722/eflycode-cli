import sys
import threading
from typing import List, Literal, Optional, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, TextColumn, BarColumn
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text


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
        self._lock = threading.Lock()

        self._initialized = True

    def flush(self) -> None:
        """刷新控制台输出"""
        with self._lock:
            self.console.file.flush()

    def acquire_user_input(self, text: str = "", choices: Optional[List[str]] = None) -> str:
        """获取用户输入

        Returns:
            str: 用户输入的内容
        """
        with self._lock:
            return Prompt.ask(f"user{text}", choices=choices)

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
            total: 总数量，如果不提供则尝试从iterable获取长度
            
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

    def help(self) -> None:
        """显示帮助信息"""
        self.table(
            "",
            ["命令", "描述"],
            [
                ["help", "显示帮助信息"],
                ["quit", "退出程序"]
            ]
        )

    def info(self, text: str, **kwargs) -> None:
        """显示信息内容

        Args:
            text: 要显示的信息内容
        """
        with self._lock:
            self.console.print(text, **kwargs)

    def error(self, message: str) -> None:
        """显示错误信息
        
        Args:
            message: 错误信息
        """
        with self._lock:
            self.console.print(f"[red][ERROR] {message}[/red]")

    def success(self, message: str) -> None:
        """显示成功信息
        
        Args:
            message: 成功信息
        """
        with self._lock:
            self.console.print(f"[green][SUCCESS] {message}[/green]")

    def warning(self, message: str) -> None:
        """显示警告信息
        
        Args:
            message: 警告信息
        """
        with self._lock:
            self.console.print(f"[yellow][WARNING] {message}[/yellow]")

    def panel(self, titles: Sequence[str], content: str, color: str = "green",
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
        with self._lock:
            self.console.print(panel)

    def table(self, title: str, columns: List[str], rows: List[List[str]]) -> None:
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

        with self._lock:
            self.console.print(table)

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
