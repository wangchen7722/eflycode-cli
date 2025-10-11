"""
内置命令模块

提供系统内置的基础命令
"""

from echo.ui.command.command import BaseCommand, CommandContext, CommandResult


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
                commands.append({
                    "command": f"/{command.name}",
                    "description": command.description
                })
        
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


class StatusCommand(BaseCommand):
    """状态命令"""
    
    def __init__(self):
        super().__init__(
            name="status",
            description="显示运行状态"
        )
    
    def execute(self, args: str, context: CommandContext) -> CommandResult:
        """执行状态命令"""
        if context.run_loop:
            state = context.run_loop.state
            is_running = context.run_loop.is_running
            agent_name = getattr(context.run_loop.agent, 'name', '未知')
            
            status_info = [
                f"Agent: {agent_name}",
                f"状态: {state.value}",
                f"运行中: {'是' if is_running else '否'}"
            ]
            
            context.ui.panel(["系统状态"], "\n".join(status_info), color="blue")
        else:
            context.ui.warning("无法获取运行状态")
        
        return CommandResult(continue_loop=True)


class PauseCommand(BaseCommand):
    """暂停命令"""
    
    def __init__(self):
        super().__init__(
            name="pause",
            description="暂停运行循环"
        )
    
    def execute(self, args: str, context: CommandContext) -> CommandResult:
        """执行暂停命令"""
        # 设置暂停标志
        context.set("paused", True)
        return CommandResult(
            continue_loop=True,
            message="已暂停，输入 /resume 恢复运行",
            success=True
        )


class ResumeCommand(BaseCommand):
    """恢复命令"""
    
    def __init__(self):
        super().__init__(
            name="resume",
            description="恢复运行循环"
        )
    
    def execute(self, args: str, context: CommandContext) -> CommandResult:
        """执行恢复命令"""
        # 清除暂停标志
        context.set("paused", False)
        return CommandResult(
            continue_loop=True,
            message="已恢复运行",
            success=True
        )


def get_builtin_commands():
    """获取所有内置命令实例
    
    Returns:
        List[BaseCommand]: 内置命令列表
    """
    return [
        HelpCommand(),
        QuitCommand(),
        ClearCommand(),
        StatusCommand(),
        PauseCommand(),
        ResumeCommand(),
    ]