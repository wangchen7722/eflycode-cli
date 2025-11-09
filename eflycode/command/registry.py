import importlib
from typing import Type

from eflycode.command.base import Command


class CommandRegistry:
    """命令注册中心"""

    _commands: dict[str, Type[Command]] = {}

    @classmethod
    def auto_discover(cls, package="eflycode.command.builtin"):
        """自动发现并注册指定包中的命令类"""
        package = importlib.import_module(package)
        for _, module_name, _ in package.walk_packages(package.__path__,
                                                       package.__name__ + "."):
            module = importlib.import_module(module_name)
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and issubclass(attr, Command)
                        and attr is not Command):
                    cls.register(attr)

    @classmethod
    def register(cls, command_cls: Type[Command]):
        """注册命令"""
        if not command_cls.name:
            raise ValueError(f"{command_cls.__name__} 缺少 name 属性")
        cls._commands[command_cls.name] = command_cls

    @classmethod
    def create(cls, name: str) -> Command:
        """根据名称创建命令实例"""
        command_cls = cls._commands.get(name)
        if not command_cls:
            raise ValueError(f"未注册命令 {name}")
        return command_cls()

    @classmethod
    def list(cls) -> list[tuple[str, str]]:
        """列出所有注册的命令名称"""
        return [(name, cmd.description) for name, cmd in cls._commands.items()]


def register_command(cls: Type[Command]) -> Type[Command]:
    """注册命令类"""
    CommandRegistry.register(cls)
    return cls
