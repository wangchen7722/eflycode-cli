import uuid
from typing import Any, List, Optional

from eflycode.core.llm.protocol import LLMRequest, Message, MessageRole
from eflycode.core.llm.providers.base import LLMProvider
from eflycode.core.context.manager import ContextManager
from eflycode.core.context.strategies import ContextStrategyConfig
from eflycode.core.utils.logger import logger


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
        
        content_length = len(content) if content else 0
        tool_calls_count = len(tool_calls) if tool_calls else 0
        logger.debug(
            f"添加消息到会话: session_id={self._id}, role={role}, "
            f"content_length={content_length}, "
            f"tool_calls_count={tool_calls_count}, "
            f"total_messages={len(self._messages)}"
        )

        # 记录第一条 user 消息作为初始提问
        if role == "user" and content and self._initial_user_question is None:
            self._initial_user_question = content
            question_preview = content[:50]
            logger.debug(f"记录初始用户提问: session_id={self._id}, question_preview={question_preview}...")

    def get_messages(self) -> List[Message]:
        """获取所有消息

        Returns:
            List[Message]: 消息列表
        """
        return self._messages.copy()

    def clear(self) -> None:
        """清空会话历史"""
        message_count = len(self._messages)
        self._messages.clear()
        self._initial_user_question = None
        logger.info(f"清空会话历史: session_id={self._id}, cleared_messages={message_count}")

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
        original_count = len(messages)
        
        logger.debug(
            f"获取上下文: session_id={self._id}, model={model}, "
            f"max_context_length={max_context_length}, messages_count={original_count}, "
            f"context_manager={'enabled' if self.context_manager else 'disabled'}"
        )

        # 如果启用了上下文管理，进行压缩
        if self.context_manager and self.context_config:
            logger.debug(f"触发上下文压缩: session_id={self._id}, strategy={self.context_config.strategy_type}")
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
            
            compressed_count = len(messages)
            if compressed_count != original_count:
                logger.info(
                    f"上下文压缩完成: session_id={self._id}, "
                    f"original_messages={original_count}, compressed_messages={compressed_count}"
            )

        return LLMRequest(
            model=model,
            messages=messages,
        )

