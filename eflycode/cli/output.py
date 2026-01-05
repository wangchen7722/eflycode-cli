import sys
from typing import Dict, Optional

from rich.console import Console

from eflycode.core.ui.output import UIOutput


class TerminalOutput(UIOutput):
    """终端输出实现

    使用 rich 库进行终端输出
    支持样式和格式化
    直接写入 stdout（scrollback-first 方式）
    """

    def __init__(self, console: Optional[Console] = None):
        """初始化终端输出

        Args:
            console: Rich Console 实例，None 则使用默认控制台
        """
        self._console = console or Console(file=sys.stdout)
        self._current_task: Optional[str] = None

    def write(self, text: str) -> None:
        """写入文本

        支持增量写入，用于打字机效果

        Args:
            text: 要写入的文本
        """
        self._console.print(text, end="")
        if hasattr(self._console.file, "flush"):
            self._console.file.flush()

    def clear(self) -> None:
        """清空输出"""
        self._console.clear()

    def flush(self) -> None:
        """刷新输出缓冲区"""
        if hasattr(self._console.file, "flush"):
            self._console.file.flush()

    def start_task(self, task_name: str) -> None:
        """开始任务

        Args:
            task_name: 任务名称
        """
        self._current_task = task_name
        self._console.print(f"[bold cyan]任务开始:[/bold cyan] {task_name}")

    def end_task(self) -> None:
        """结束任务"""
        if self._current_task:
            self._console.print("\n[bold green]任务完成[/bold green]")
            self._current_task = None

    def show_tool_call(self, tool_name: str, arguments: Dict) -> None:
        """显示工具调用

        Args:
            tool_name: 工具名称
            arguments: 工具参数
        """
        self._console.print(f"[yellow]调用工具:[/yellow] [bold]{tool_name}[/bold]")
        if arguments:
            self._console.print(f"  参数: {arguments}")

    def show_tool_call_detected(self, tool_name: str) -> None:
        """显示工具调用检测到

        Args:
            tool_name: 工具名称
        """
        self._console.print(f"\n[dim]检测到工具调用:[/dim] [bold]{tool_name}[/bold]")

    def show_tool_call_executing(self, tool_name: str, arguments: Dict) -> None:
        """显示工具正在执行

        Args:
            tool_name: 工具名称
            arguments: 工具参数
        """
        self._console.print(f"\n[yellow]工具 {tool_name} 正在执行...[/yellow]")
        if arguments:
            self._console.print(f"  参数: {arguments}")

    def show_tool_result(self, tool_name: str, result: str) -> None:
        """显示工具执行结果

        Args:
            tool_name: 工具名称
            result: 执行结果
        """
        self._console.print(f"\n[green]工具 {tool_name} 执行成功[/green]")
        if result:
            result_preview = result[:200] + "..." if len(result) > 200 else result
            self._console.print(f"  结果: {result_preview}")

    def show_error(self, error: Exception) -> None:
        """显示错误信息

        Args:
            error: 错误异常
        """
        self._console.print(f"[bold red]错误:[/bold red] {error}")

    def close(self) -> None:
        """关闭输出

        清理资源
        """
        self.flush()

