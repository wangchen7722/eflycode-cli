from typing import List, Optional

from eflycode.core.llm.protocol import LLMRequest, Message, MessageRole


class Session:
    """会话管理，管理 Agent 的对话历史"""

    def __init__(self):
        """初始化会话"""
        self._messages: List[Message] = []

    def add_message(
        self,
        role: MessageRole,
        content: str = None,
        tool_calls: List = None,
        tool_call_id: str = None,
    ) -> None:
        """添加消息到会话历史

        Args:
            role: 消息角色（user、assistant、system、tool）
            content: 消息内容
            tool_calls: 工具调用列表（仅用于 assistant 角色）
            tool_call_id: 工具调用 ID（仅用于 tool 角色）
        """
        from eflycode.core.llm.protocol import Message
        message = Message(role=role, content=content, tool_calls=tool_calls, tool_call_id=tool_call_id)
        self._messages.append(message)

    def get_messages(self) -> List[Message]:
        """获取所有消息

        Returns:
            List[Message]: 消息列表
        """
        return self._messages.copy()

    def clear(self) -> None:
        """清空会话历史"""
        self._messages.clear()

    def get_context(self, model: str) -> LLMRequest:
        """获取当前上下文，转换为 LLMRequest 格式

        Args:
            model: 模型名称

        Returns:
            LLMRequest: LLM 请求对象
        """
        return LLMRequest(
            model=model,
            messages=self.get_messages(),
        )

