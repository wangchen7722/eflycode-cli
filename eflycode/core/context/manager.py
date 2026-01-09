"""上下文管理器

协调 Tokenizer 和 Strategy，管理上下文压缩
"""

from typing import Any, List, Optional

from eflycode.core.llm.protocol import Message
from eflycode.core.llm.providers.base import LLMProvider

from eflycode.core.context.strategies import ContextStrategy, ContextStrategyConfig
from eflycode.core.context.tokenizer import Tokenizer
from eflycode.core.utils.logger import logger


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
        hook_system: Optional[Any] = None,
        session_id: Optional[str] = None,
    ) -> List[Message]:
        """管理上下文，返回优化后的消息列表

        Args:
            messages: 原始消息列表
            model: 模型名称
            config: 上下文策略配置
            max_context_length: 模型的最大上下文长度
            initial_user_question: 用户最初的提问（用于滑动窗口策略）
            provider: LLM Provider（用于 summary 策略）
            hook_system: Hook 系统实例（可选）
            session_id: 会话 ID（可选，用于 hooks）

        Returns:
            List[Message]: 优化后的消息列表
        """
        logger.info(
            f"开始上下文管理: model={model}, messages_count={len(messages)}, "
            f"max_context_length={max_context_length}, strategy={config.strategy_type if config else 'none'}"
        )
        
        if not messages:
            return messages

        # 如果没有配置策略，直接返回原始消息
        if not config:
            logger.debug("未配置上下文策略，返回原始消息")
            return messages

        # 创建策略实例
        strategy = self._create_strategy(config)

        # 检查是否需要压缩
        should_compress = strategy.should_compress(messages, model, self.tokenizer, max_context_length)
        logger.debug(f"压缩检查结果: should_compress={should_compress}")
        
        if not should_compress:
            return messages

        # 触发 PreCompress hook
        if hook_system and session_id:
            logger.debug(f"触发 PreCompress hook: session_id={session_id}")
            from pathlib import Path
            from eflycode.core.config.config_manager import ConfigManager

            config_manager = ConfigManager.get_instance()
            workspace_dir = config_manager.get_workspace_dir() or Path.cwd()

            hook_result = hook_system.fire_pre_compress_event(session_id, workspace_dir)

            # 如果 hook 要求停止，返回原始消息
            if not hook_result.continue_:
                logger.warning(f"PreCompress hook 要求停止压缩: session_id={session_id}")
                return messages

        # 执行压缩
        original_count = len(messages)
        logger.info(f"执行上下文压缩: strategy={config.strategy_type}, original_messages={original_count}")
        compressed_messages = strategy.compress(
            messages,
            model,
            self.tokenizer,
            max_context_length,
            initial_user_question,
            provider,
        )
        
        original_count = len(messages)
        compressed_count = len(compressed_messages)
        reduction = original_count - compressed_count
        logger.info(
            f"上下文压缩完成: original_messages={original_count}, "
            f"compressed_messages={compressed_count}, "
            f"reduction={reduction}"
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
            logger.debug("创建 SummaryCompressionStrategy")
            return SummaryCompressionStrategy(config)
        elif config.strategy_type == "sliding_window":
            logger.debug("创建 SlidingWindowStrategy")
            return SlidingWindowStrategy(config)
        else:
            logger.error(f"未知的策略类型: {config.strategy_type}")
            raise ValueError(f"未知的策略类型: {config.strategy_type}")

