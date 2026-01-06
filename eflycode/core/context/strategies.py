"""上下文管理策略

实现不同的上下文压缩策略
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Literal, Optional

from eflycode.core.llm.protocol import LLMRequest, Message, MessageRole
from eflycode.core.llm.providers.base import LLMProvider

from eflycode.core.context.tokenizer import Tokenizer


@dataclass
class ContextStrategyConfig:
    """上下文策略配置"""

    strategy_type: Literal["summary", "sliding_window"]
    # Summary 策略配置
    summary_threshold: float = 0.8  # token 阈值比例
    summary_keep_recent: int = 10  # 保留最新消息数
    summary_model: Optional[str] = None  # 用于 summary 的模型，None 表示使用相同模型
    # Sliding Window 策略配置
    sliding_window_size: int = 10  # 窗口大小


class ContextStrategy(ABC):
    """上下文压缩策略基类"""

    @abstractmethod
    def should_compress(
        self,
        messages: List[Message],
        model: str,
        tokenizer: Tokenizer,
        max_context_length: int,
    ) -> bool:
        """判断是否需要压缩

        Args:
            messages: 消息列表
            model: 模型名称
            tokenizer: Token 计算器
            max_context_length: 模型的最大上下文长度

        Returns:
            bool: 是否需要压缩
        """
        pass

    @abstractmethod
    def compress(
        self,
        messages: List[Message],
        model: str,
        tokenizer: Tokenizer,
        max_context_length: int,
        initial_user_question: Optional[str] = None,
        provider: Optional[LLMProvider] = None,
    ) -> List[Message]:
        """压缩消息列表

        Args:
            messages: 消息列表
            model: 模型名称
            tokenizer: Token 计算器
            max_context_length: 模型的最大上下文长度
            initial_user_question: 用户最初的提问（用于滑动窗口策略）
            provider: LLM Provider（用于 summary 策略）

        Returns:
            List[Message]: 压缩后的消息列表
        """
        pass


class SummaryCompressionStrategy(ContextStrategy):
    """Summary 压缩策略

    当 token 数达到模型窗口的 80% 时，使用 LLM 对旧消息进行总结压缩
    """

    def __init__(self, config: ContextStrategyConfig):
        """初始化策略

        Args:
            config: 策略配置
        """
        self.config = config

    def should_compress(
        self,
        messages: List[Message],
        model: str,
        tokenizer: Tokenizer,
        max_context_length: int,
    ) -> bool:
        """判断是否需要压缩"""
        if not messages:
            return False

        total_tokens = tokenizer.count_tokens(messages, model)
        threshold = int(max_context_length * self.config.summary_threshold)
        return total_tokens >= threshold

    def compress(
        self,
        messages: List[Message],
        model: str,
        tokenizer: Tokenizer,
        max_context_length: int,
        initial_user_question: Optional[str] = None,
        provider: Optional[LLMProvider] = None,
    ) -> List[Message]:
        """压缩消息列表"""
        if not messages:
            return messages

        # 保留最新的 N 条消息
        keep_recent = self.config.summary_keep_recent
        if len(messages) <= keep_recent:
            return messages

        recent_messages = messages[-keep_recent:]
        old_messages = messages[:-keep_recent]

        # 如果没有 provider，无法进行 summary，返回原始消息
        if not provider:
            return messages

        # 构建 summary 提示词
        old_messages_text = self._format_messages_for_summary(old_messages)
        summary_prompt = f"""请总结以下对话历史，保留关键信息和上下文，以便后续对话能够理解：

{old_messages_text}

请用简洁的语言总结这段对话的关键内容，包括：
1. 用户的主要问题和需求
2. 重要的讨论点和决策
3. 需要保留的上下文信息

总结："""

        # 使用指定的模型或相同模型进行 summary
        summary_model = self.config.summary_model or model

        # 创建 summary 请求
        summary_request = LLMRequest(
            model=summary_model,
            messages=[
                Message(role="user", content=summary_prompt),
            ],
        )

        try:
            # 调用 LLM 进行 summary
            response = provider.call(summary_request)
            summary_content = response.message.content or ""

            # 构建压缩后的消息列表
            compressed_messages = [
                Message(
                    role="system",
                    content=f"[对话历史总结] {summary_content}",
                ),
            ]
            compressed_messages.extend(recent_messages)

            return compressed_messages
        except Exception:
            # 如果 summary 失败，回退到原始消息
            return messages

    def _format_messages_for_summary(self, messages: List[Message]) -> str:
        """格式化消息用于 summary

        Args:
            messages: 消息列表

        Returns:
            str: 格式化后的文本
        """
        lines = []
        for msg in messages:
            role_name = {"user": "用户", "assistant": "助手", "system": "系统", "tool": "工具"}.get(
                msg.role, msg.role
            )
            content = msg.content or ""
            if msg.tool_calls:
                content += f" [调用了工具: {', '.join(tc.function.name for tc in msg.tool_calls if tc.function)}]"
            lines.append(f"{role_name}: {content}")
        return "\n".join(lines)


class SlidingWindowStrategy(ContextStrategy):
    """滑动窗口策略

    只保留最新的 N 条消息，但保留用户最初的提问
    """

    def __init__(self, config: ContextStrategyConfig):
        """初始化策略

        Args:
            config: 策略配置
        """
        self.config = config

    def should_compress(
        self,
        messages: List[Message],
        model: str,
        tokenizer: Tokenizer,
        max_context_length: int,
    ) -> bool:
        """判断是否需要压缩"""
        window_size = self.config.sliding_window_size
        return len(messages) > window_size

    def compress(
        self,
        messages: List[Message],
        model: str,
        tokenizer: Tokenizer,
        max_context_length: int,
        initial_user_question: Optional[str] = None,
        provider: Optional[LLMProvider] = None,
    ) -> List[Message]:
        """压缩消息列表"""
        if not messages:
            return messages

        window_size = self.config.sliding_window_size
        if len(messages) <= window_size:
            return messages

        # 保留最新的 N 条消息
        recent_messages = messages[-window_size:]

        # 检查初始提问是否在最新消息中
        has_initial_question = False
        if initial_user_question:
            for msg in recent_messages:
                if msg.role == "user" and msg.content == initial_user_question:
                    has_initial_question = True
                    break

        # 如果初始提问不在最新消息中，将其作为第一条消息插入
        if initial_user_question and not has_initial_question:
            compressed_messages = [
                Message(
                    role="system",
                    content=f"[用户最初的问题] {initial_user_question}",
                ),
            ]
            compressed_messages.extend(recent_messages)
            return compressed_messages

        return recent_messages

