"""上下文管理器

协调 Tokenizer 和 Strategy，管理上下文压缩
"""

from typing import List, Optional

from eflycode.core.llm.protocol import Message
from eflycode.core.llm.providers.base import LLMProvider

from eflycode.core.context.strategies import ContextStrategy, ContextStrategyConfig
from eflycode.core.context.tokenizer import Tokenizer


class ContextManager:
    """上下文管理器"""

    def __init__(self):
        """初始化上下文管理器"""
        self.tokenizer = Tokenizer()

    def manage(
        self,
        messages: List[Message],
        model: str,
        config: ContextStrategyConfig,
        max_context_length: int,
        initial_user_question: Optional[str] = None,
        provider: Optional[LLMProvider] = None,
    ) -> List[Message]:
        """管理上下文，返回优化后的消息列表

        Args:
            messages: 原始消息列表
            model: 模型名称
            config: 上下文策略配置
            max_context_length: 模型的最大上下文长度
            initial_user_question: 用户最初的提问（用于滑动窗口策略）
            provider: LLM Provider（用于 summary 策略）

        Returns:
            List[Message]: 优化后的消息列表
        """
        if not messages:
            return messages

        # 如果没有配置策略，直接返回原始消息
        if not config:
            return messages

        # 创建策略实例
        strategy = self._create_strategy(config)

        # 检查是否需要压缩
        if not strategy.should_compress(messages, model, self.tokenizer, max_context_length):
            return messages

        # 执行压缩
        compressed_messages = strategy.compress(
            messages,
            model,
            self.tokenizer,
            max_context_length,
            initial_user_question,
            provider,
        )

        return compressed_messages

    def _create_strategy(self, config: ContextStrategyConfig) -> ContextStrategy:
        """创建策略实例

        Args:
            config: 策略配置

        Returns:
            ContextStrategy: 策略实例
        """
        from eflycode.core.context.strategies import (
            SlidingWindowStrategy,
            SummaryCompressionStrategy,
        )

        if config.strategy_type == "summary":
            return SummaryCompressionStrategy(config)
        elif config.strategy_type == "sliding_window":
            return SlidingWindowStrategy(config)
        else:
            raise ValueError(f"未知的策略类型: {config.strategy_type}")

