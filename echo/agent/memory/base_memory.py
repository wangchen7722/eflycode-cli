from abc import ABC, abstractmethod
from typing import List, Dict

from echo.schema.llm import Message


class BaseMemory(ABC):
    """
    抽象基类，用于定义智能体对话记忆的统一接口。
    """

    @abstractmethod
    def append_message(self, message: Message) -> None:
        """
        添加一条对话消息
        Args:
            role: 'user' | 'assistant' | 'system'
            content: 消息文本
        """
        pass

    @abstractmethod
    def load_context(self) -> List[Message]:
        """
        获取当前上下文（若干条消息）
        Returns:
            List[Dict[str, str]]
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """清空记忆"""
        pass
