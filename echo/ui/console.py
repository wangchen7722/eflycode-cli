import sys
from typing import List, Literal
from contextlib import contextmanager
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.text import Text


class ConsoleUI:
    """终端用户界面类，处理用户输入输出和UI展示"""

    def __init__(self):
        """初始化控制台UI"""
        self.console = Console()

    def acquire_user_input(self) -> str:
        """获取用户输入

        Returns:
            str: 用户输入的内容
        """
        return Prompt.ask("user")

    def exit(self) -> None:
        """退出控制台程序"""
        self.console.print("[green]Bye!!![/green]")
        sys.exit(0)

    @contextmanager
    def create_loading(self, description: str):
        """创建进度条

        Args:
            description: 进度条描述

        Yields:
            Progress: 进度条对象
        """
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        )
        task = progress.add_task(description, total=100)
        try:
            progress.start()
            yield progress
        finally:
            progress.update(task, description=description, completed=100, visible=False)
            progress.stop()
        self.show_panel([], f"✅ {description}")

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

    def show_text(self, text: str) -> None:
        """显示文本内容

        Args:
            text: 要显示的文本内容
        """
        self.console.print(text)

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

    def show_panel(self, titles: List[str], content: str, color: str = "green",
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
            table.add_column(column, style='default', width=20)

        for row in rows:
            table.add_row(*row)

        self.console.print(table)

    def run(self):
        """运行控制台界面，返回用户输入内容
        
        Yields:
            str: 用户输入的内容
        """
        self.show_help()

        while True:
            try:
                user_input = self.acquire_user_input()
                if not user_input:
                    continue
                if user_input == "quit":
                    self.exit()
                yield user_input
            except KeyboardInterrupt:
                self.show_error("用户中断程序")
                self.exit()
            except Exception as e:
                self.show_error(str(e))
