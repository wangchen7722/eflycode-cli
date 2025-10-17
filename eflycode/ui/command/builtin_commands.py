"""
内置命令模块

提供系统内置的基础命令
"""
from typing import List

from eflycode.ui.command.command import BaseCommand, CommandContext, CommandResult


class HelpCommand(BaseCommand):
    """帮助命令"""
    
    def __init__(self):
        super().__init__(
            name="help",
            description="显示帮助信息"
        )
    
    def execute(self, args: str, context: CommandContext) -> CommandResult:
        """执行帮助命令"""
        commands = []
        
        # 获取命令处理器中的注册中心
        if hasattr(context, 'ui') and hasattr(context.ui, 'parent_handler'):
            registry = context.ui.parent_handler.registry
            for command in registry.list_commands():
                commands.append([
                    f"/{command.name}", command.description
                ])
        
        if commands:
            context.ui.help(commands)
        else:
            context.ui.info("暂无可用命令")
        
        return CommandResult(continue_loop=True)


class QuitCommand(BaseCommand):
    """退出命令"""
    
    def __init__(self):
        super().__init__(
            name="quit",
            description="退出程序"
        )
    
    def execute(self, args: str, context: CommandContext) -> CommandResult:
        """执行退出命令"""
        return CommandResult(
            continue_loop=False,
            message="再见！",
            success=True
        )


class ClearCommand(BaseCommand):
    """清屏命令"""
    
    def __init__(self):
        super().__init__(
            name="clear",
            description="清空屏幕"
        )
    
    def execute(self, args: str, context: CommandContext) -> CommandResult:
        """执行清屏命令"""
        context.ui.clear()
        return CommandResult(continue_loop=True)


def get_builtin_commands() -> List[BaseCommand]:
    """获取所有内置命令实例
    
    Returns:
        List[BaseCommand]: 内置命令列表
    """
    return [
        HelpCommand(),
        QuitCommand(),
        ClearCommand(),
    ]