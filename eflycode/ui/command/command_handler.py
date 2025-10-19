"""命令处理器模块

处理用户输入的命令
"""

from typing import Dict, Optional, List, Callable
from eflycode.ui.command.command import BaseCommand, CommandContext, CommandResult
from eflycode.ui.command.builtin_commands import get_builtin_commands
from eflycode.util.logger import logger
from eflycode.ui.base_ui import BaseUI


class CommandRegistry:
    """命令注册中心"""

    def __init__(self):
        """初始化命令注册中心"""
        self._commands: Dict[str, BaseCommand] = {}
        self._aliases: Dict[str, str] = {}

    def register(self, command: BaseCommand) -> None:
        """注册命令
        
        Args:
            command: 命令实例
        """
        self._commands[command.name] = command

        # 注册别名
        for alias in command.aliases:
            self._aliases[alias] = command.name

        logger.debug(f"Registered command: {command.name}")

    def unregister(self, name: str) -> bool:
        """注销命令
        
        Args:
            name: 命令名称
            
        Returns:
            bool: 是否成功注销
        """
        if name in self._commands:
            command = self._commands[name]

            # 移除别名
            for alias in command.aliases:
                self._aliases.pop(alias, None)

            # 移除命令
            del self._commands[name]
            return True
        return False

    def get_command(self, name: str) -> Optional[BaseCommand]:
        """获取命令
        
        Args:
            name: 命令名称或别名
            
        Returns:
            Optional[BaseCommand]: 命令实例，如果不存在则返回 None
        """
        # 检查是否为别名
        if name in self._aliases:
            name = self._aliases[name]

        return self._commands.get(name)

    def list_commands(self) -> List[BaseCommand]:
        """列出所有命令
        
        Returns:
            List[BaseCommand]: 命令列表
        """
        return list(self._commands.values())


class CommandHandler:
    """控制台命令处理器"""

    def __init__(self, ui: BaseUI, run_loop: Callable[[], None]):
        self.ui = ui
        self.run_loop = run_loop
        self.command_prefix = "/"
        self.registry = CommandRegistry()

        # 为了让内置命令能够访问命令处理器
        self.ui.parent_handler = self

        # 注册内置命令
        self._register_builtin_commands()

    def _register_builtin_commands(self):
        """注册内置命令"""
        for command in get_builtin_commands():
            self.registry.register(command)

    def register_command(self, command: BaseCommand) -> None:
        """注册命令
        
        Args:
            command: 命令实例
        """
        self.registry.register(command)

    def is_command(self, user_input: str) -> bool:
        """检查输入是否为命令
        
        Args:
            user_input: 用户输入
            
        Returns:
            bool: 是否为命令
        """
        return user_input.strip().startswith(self.command_prefix)

    def handle_command(self, user_input: str) -> CommandResult:
        """处理命令
        
        Args:
            user_input: 用户输入
            
        Returns:
            CommandResult: 命令执行结果
        """
        # 移除命令前缀
        command_line = user_input.strip()[len(self.command_prefix):]

        # 解析命令名和参数
        parts = command_line.split(maxsplit=1)
        command_name = parts[0] if parts else ""
        args = parts[1] if len(parts) > 1 else ""

        # 获取命令
        command = self.registry.get_command(command_name)
        if not command:
            return CommandResult(
                continue_loop=True,
                message=f"未知命令: {command_name}",
                success=False
            )

        # 创建命令上下文
        context = CommandContext(
            ui=self.ui,
            run_loop=self.run_loop
        )

        # 执行命令
        try:
            return command.execute(args, context)
        except Exception as e:
            return CommandResult(
                continue_loop=True,
                message=f"命令执行错误: {str(e)}",
                success=False
            )
