from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class CommandContext(BaseModel):
    """命令执行上下文"""
    args: list[str] = Field(default_factory=list)


class Command(ABC):
    """命令类基类"""

    name: str = ""
    description: str = ""

    @abstractmethod
    def execute(self, context: CommandContext):
        """执行命令"""
        ...
