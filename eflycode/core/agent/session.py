import uuid
from typing import Any, List, Optional

from eflycode.core.llm.protocol import LLMRequest, Message, MessageRole
from eflycode.core.llm.providers.base import LLMProvider
from eflycode.core.context.manager import ContextManager
from eflycode.core.context.strategies import ContextStrategyConfig


class Session:
    """会话管理，管理 Agent 的对话历史"""

    def __init__(self, context_config: Optional[ContextStrategyConfig] = None):
        """初始化会话

        Args:
            context_config: 上下文管理配置，如果为 None 则不启用上下文管理
        """
        self._id = str(uuid.uuid4())
        self._messages: List[Message] = []
        self._initial_user_question: Optional[str] = None
        self.context_config = context_config
        self.context_manager: Optional[ContextManager] = ContextManager() if context_config else None

    @property
    def id(self) -> str:
        """获取会话 ID

        Returns:
            str: 会话唯一标识符
        """
        return self._id

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

        # 记录第一条 user 消息作为初始提问
        if role == "user" and content and self._initial_user_question is None:
            self._initial_user_question = content

    def get_messages(self) -> List[Message]:
        """获取所有消息

        Returns:
            List[Message]: 消息列表
        """
        return self._messages.copy()

    def clear(self) -> None:
        """清空会话历史"""
        self._messages.clear()
        self._initial_user_question = None

    def get_context(
        self,
        model: str,
        max_context_length: int,
        provider: Optional[LLMProvider] = None,
        hook_system: Optional[Any] = None,
    ) -> LLMRequest:
        """获取当前上下文，转换为 LLMRequest 格式

        Args:
            model: 模型名称
            max_context_length: 模型的最大上下文长度
            provider: LLM Provider（用于 summary 策略）
            hook_system: Hook 系统实例（可选，用于 PreCompress hook）

        Returns:
            LLMRequest: LLM 请求对象
        """
        messages = self.get_messages()

        # 如果启用了上下文管理，进行压缩
        if self.context_manager and self.context_config:
            messages = self.context_manager.manage(
                messages=messages,
                model=model,
                config=self.context_config,
                max_context_length=max_context_length,
                initial_user_question=self._initial_user_question,
                provider=provider,
                hook_system=hook_system,
                session_id=self._id,
            )

        return LLMRequest(
            model=model,
            messages=messages,
        )

