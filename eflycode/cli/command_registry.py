"""命令注册中心"""

from typing import Callable, Dict, Optional

from eflycode.cli.handlers import build_model_command_handler
from eflycode.cli.output import TerminalOutput
from eflycode.core.config.config_manager import ConfigManager


class CommandRegistry:
    """命令注册中心，集中管理命令与处理函数"""

    def __init__(self) -> None:
        self._commands: Dict[str, Dict[str, object]] = {}
        self._deps_initialized = False
        self._register_builtin_commands()
        self.initialize()

    def _register_builtin_commands(self) -> None:
        self.register_command(
            command="/model",
            description="选择模型配置",
            handler=None,
        )

    def register_command(
        self,
        command: str,
        description: str,
        handler: Optional[Callable[[str], object]] = None,
    ) -> None:
        if not command.startswith("/"):
            raise ValueError(f"命令必须以 '/' 开头: {command}")
        self._commands[command] = {
            "description": description,
            "handler": handler,
        }

    def set_command_handler(self, command: str, handler: Callable[[str], object]) -> None:
        if command not in self._commands:
            raise ValueError(f"命令未注册: {command}")
        self._commands[command]["handler"] = handler

    def get_command_handler(self, command: str):
        if command in self._commands:
            return self._commands[command].get("handler")
        return None

    async def handle_command_async(self, command: str) -> bool:
        command = command.strip()
        handler = self.get_command_handler(command)
        if not handler:
            return False
        result = handler(command)
        if hasattr(result, "__await__"):
            return bool(await result)
        return bool(result)

    def list_commands(self) -> Dict[str, Dict[str, object]]:
        return self._commands

    def initialize(self) -> None:
        """注入默认命令的依赖"""
        if self._deps_initialized:
            return
        output = TerminalOutput()
        config_manager = ConfigManager.get_instance()
        self.set_command_handler(
            "/model",
            build_model_command_handler(output, config_manager),
        )
        self._deps_initialized = True


_GLOBAL_COMMAND_REGISTRY: Optional[CommandRegistry] = None


def get_command_registry() -> CommandRegistry:
    global _GLOBAL_COMMAND_REGISTRY
    if _GLOBAL_COMMAND_REGISTRY is None:
        _GLOBAL_COMMAND_REGISTRY = CommandRegistry()
    return _GLOBAL_COMMAND_REGISTRY
