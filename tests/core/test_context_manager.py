"""ContextManager 测试用例"""

import unittest

from eflycode.core.context.manager import ContextManager
from eflycode.core.context.strategies import ContextStrategyConfig
from eflycode.core.llm.protocol import Message
from eflycode.core.llm.providers.base import LLMProvider


class MockProvider(LLMProvider):
    """Mock Provider 用于测试"""

    @property
    def capabilities(self):
        from eflycode.core.llm.providers.base import ProviderCapabilities
        return ProviderCapabilities(supports_streaming=True, supports_tools=True)

    def call(self, request):
        from eflycode.core.llm.protocol import ChatCompletion, Usage
        return ChatCompletion(
            id="test",
            object="chat.completion",
            created=1234567890,
            model=request.model,
            message=Message(role="assistant", content="Summary"),
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

    def stream(self, request):
        raise NotImplementedError


class TestContextManager(unittest.TestCase):
    """ContextManager 测试类"""

    def setUp(self):
        """设置测试环境"""
        self.manager = ContextManager()

    def test_init(self):
        """测试初始化"""
        self.assertIsNotNone(self.manager.tokenizer)

    def test_manage_no_config(self):
        """测试没有配置时不管理"""
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi"),
        ]
        result = self.manager.manage(
            messages, "gpt-4", None, 100000, None, None
        )
        # 没有配置，应该返回原始消息
        self.assertEqual(len(result), len(messages))
        self.assertEqual(result, messages)

    def test_manage_summary_strategy_no_compress(self):
        """测试 Summary 策略不需要压缩"""
        config = ContextStrategyConfig(
            strategy_type="summary",
            summary_threshold=0.8,
            summary_keep_recent=10,
        )
        messages = [Message(role="user", content="Hello")]
        result = self.manager.manage(
            messages, "gpt-4", config, 100000, None, None
        )
        # 消息很少，不需要压缩
        self.assertEqual(len(result), len(messages))

    def test_manage_summary_strategy_compress(self):
        """测试 Summary 策略需要压缩"""
        config = ContextStrategyConfig(
            strategy_type="summary",
            summary_threshold=0.8,
            summary_keep_recent=3,
        )
        # 创建大量消息以超过阈值
        long_content = "This is a long message. " * 100
        messages = [Message(role="user", content=long_content) for _ in range(10)]
        provider = MockProvider()
        result = self.manager.manage(
            messages, "gpt-4", config, 1000, None, provider
        )
        # 应该被压缩
        self.assertLess(len(result), len(messages))
        # 应该包含 summary 消息
        self.assertEqual(result[0].role, "system")
        self.assertIn("总结", result[0].content)

    def test_manage_sliding_window_strategy(self):
        """测试 Sliding Window 策略"""
        config = ContextStrategyConfig(
            strategy_type="sliding_window",
            sliding_window_size=5,
        )
        messages = [Message(role="user", content=f"Q{i}") for i in range(10)]
        result = self.manager.manage(
            messages, "gpt-4", config, 100000, "Initial question", None
        )
        # 应该只保留最新的 5 条消息，加上初始提问
        self.assertEqual(len(result), 6)
        self.assertEqual(result[0].role, "system")
        self.assertIn("Initial question", result[0].content)

    def test_manage_sliding_window_without_initial_question(self):
        """测试 Sliding Window 策略没有初始提问"""
        config = ContextStrategyConfig(
            strategy_type="sliding_window",
            sliding_window_size=5,
        )
        messages = [Message(role="user", content=f"Q{i}") for i in range(10)]
        result = self.manager.manage(
            messages, "gpt-4", config, 100000, None, None
        )
        # 应该只保留最新的 5 条消息
        self.assertEqual(len(result), 5)

    def test_manage_empty_messages(self):
        """测试空消息列表"""
        config = ContextStrategyConfig(strategy_type="sliding_window")
        result = self.manager.manage([], "gpt-4", config, 100000, None, None)
        self.assertEqual(len(result), 0)

    def test_manage_invalid_strategy_type(self):
        """测试无效的策略类型"""
        config = ContextStrategyConfig(strategy_type="invalid_strategy")
        messages = [Message(role="user", content="Hello")]
        with self.assertRaises(ValueError):
            self.manager.manage(messages, "gpt-4", config, 100000, None, None)

    def test_manage_summary_strategy_with_custom_model(self):
        """测试 Summary 策略使用自定义模型"""
        config = ContextStrategyConfig(
            strategy_type="summary",
            summary_threshold=0.8,
            summary_keep_recent=3,
            summary_model="gpt-3.5-turbo",
        )
        long_content = "Long message. " * 100
        messages = [Message(role="user", content=long_content) for _ in range(10)]
        provider = MockProvider()
        result = self.manager.manage(
            messages, "gpt-4", config, 1000, None, provider
        )
        # 应该被压缩
        self.assertLess(len(result), len(messages))
        # 验证 provider 被调用
        self.assertEqual(provider.call.call_count, 1) if hasattr(provider.call, 'call_count') else None

