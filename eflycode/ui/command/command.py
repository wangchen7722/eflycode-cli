"""
命令系统模块

提供命令基类和命令注册中心
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from pydantic import BaseModel


class CommandResult(BaseModel):
    """命令执行结果"""
    
    # 是否继续运行循环
    continue_loop: bool = True
    # 执行消息
    message: Optional[str] = None
    # 是否成功
    success: bool = True
    # 额外数据
    data: Optional[Dict[str, Any]] = None


class BaseCommand(ABC):
    """命令基类"""
    
    def __init__(self, name: str, description: str, aliases: Optional[List[str]] = None):
        """初始化命令
        
        Args:
            name: 命令名称
            description: 命令描述
            aliases: 命令别名列表
        """
        self.name = name
        self.description = description
        self.aliases = aliases or []
    
    @abstractmethod
    def execute(self, args: str, context: "CommandContext") -> CommandResult:
        """执行命令
        
        Args:
            args: 命令参数
            context: 命令执行上下文
            
        Returns:
            CommandResult: 命令执行结果
        """
        pass
    
    def get_help(self) -> str:
        """获取命令帮助信息"""
        help_text = f"/{self.name} - {self.description}"
        if self.aliases:
            help_text += f" (别名: {', '.join(self.aliases)})"
        return help_text
    
    def validate_args(self, args: str) -> bool:
        """验证命令参数
        
        Args:
            args: 命令参数
            
        Returns:
            bool: 参数是否有效
        """
        return True


class CommandContext:
    """命令执行上下文"""
    
    def __init__(self, event_bus, run_loop=None):
        """初始化命令上下文
        
        Args:
            event_bus: 事件总线实例
            run_loop: 运行循环实例
        """
        self.event_bus = event_bus
        self.run_loop = run_loop
        self.data: Dict[str, Any] = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取上下文数据"""
        return self.data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """设置上下文数据"""
        self.data[key] = value