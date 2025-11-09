"""
内置命令模块

提供系统内置的基础命令
"""
from typing import List

from eflycode.ui.command.command import BaseCommand, CommandContext, CommandResult
from eflycode.ui.event import UIEventType


class HelpCommand(BaseCommand):
    """帮助命令"""
    
    def __init__(self):
        super().__init__(
            name="help",
            description="显示可用命令列表"
        )
    
    def execute(self, args: str, context: CommandContext) -> CommandResult:
        """执行帮助命令"""
        # 通过事件总线请求显示帮助信息
        context.event_bus.emit(UIEventType.SHOW_HELP, {})
        
        return CommandResult(
            continue_loop=True,
            message="显示帮助信息",
            success=True
        )


class ClearCommand(BaseCommand):
    """清屏命令"""
    
    def __init__(self):
        super().__init__(
            name="clear",
            description="清空屏幕内容"
        )
    
    def execute(self, args: str, context: CommandContext) -> CommandResult:
        """执行清屏命令"""
        context.event_bus.emit(UIEventType.CLEAR_SCREEN, {})
        
        return CommandResult(
            continue_loop=True,
            message="屏幕已清空",
            success=True
        )


def get_builtin_commands() -> List[BaseCommand]:
    """获取所有内置命令实例
    
    Returns:
        List[BaseCommand]: 内置命令列表
    """
    return [
        HelpCommand(),
        ClearCommand(),
    ]