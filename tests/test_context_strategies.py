"""上下文管理策略测试用例"""

import unittest
from unittest.mock import MagicMock, Mock

from eflycode.core.context.strategies import (
    ContextStrategyConfig,
    SlidingWindowStrategy,
    SummaryCompressionStrategy,
)
from eflycode.core.context.tokenizer import Tokenizer
from eflycode.core.llm.protocol import ChatCompletion, Message, Usage
from eflycode.core.llm.providers.base import LLMProvider


class MockProvider(LLMProvider):
    """Mock Provider 用于测试"""

    def __init__(self, summary_content: str = "这是对话历史的总结"):
        self.summary_content = summary_content
        self.call_count = 0

    @property
    def capabilities(self):
        from eflycode.core.llm.providers.base import ProviderCapabilities
        return ProviderCapabilities(supports_streaming=True, supports_tools=True)

    def call(self, request):
        self.call_count += 1
        return ChatCompletion(
            id="chatcmpl-test",
            object="chat.completion",
            created=1234567890,
            model=request.model,
            message=Message(role="assistant", content=self.summary_content),
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

    def stream(self, request):
        raise NotImplementedError


class TestContextStrategyConfig(unittest.TestCase):
    """ContextStrategyConfig 测试类"""

    def test_config_summary_defaults(self):
        """测试 Summary 策略的默认配置"""
        config = ContextStrategyConfig(strategy_type="summary")
        self.assertEqual(config.strategy_type, "summary")
        self.assertEqual(config.summary_threshold, 0.8)
        self.assertEqual(config.summary_keep_recent, 10)
        self.assertIsNone(config.summary_model)

    def test_config_sliding_window_defaults(self):
        """测试 Sliding Window 策略的默认配置"""
        config = ContextStrategyConfig(strategy_type="sliding_window")
        self.assertEqual(config.strategy_type, "sliding_window")
        self.assertEqual(config.sliding_window_size, 10)

    def test_config_custom_values(self):
        """测试自定义配置值"""
        config = ContextStrategyConfig(
            strategy_type="summary",
            summary_threshold=0.9,
            summary_keep_recent=5,
            summary_model="gpt-3.5-turbo",
        )
        self.assertEqual(config.summary_threshold, 0.9)
        self.assertEqual(config.summary_keep_recent, 5)
        self.assertEqual(config.summary_model, "gpt-3.5-turbo")


class TestSummaryCompressionStrategy(unittest.TestCase):
    """SummaryCompressionStrategy 测试类"""

    def setUp(self):
        """设置测试环境"""
        self.tokenizer = Tokenizer()
        self.config = ContextStrategyConfig(
            strategy_type="summary",
            summary_threshold=0.8,
            summary_keep_recent=3,
        )
        self.strategy = SummaryCompressionStrategy(self.config)

    def test_should_compress_below_threshold(self):
        """测试低于阈值时不压缩"""
        messages = [Message(role="user", content="Hello")]
        max_context_length = 100000
        should_compress = self.strategy.should_compress(
            messages, "gpt-4", self.tokenizer, max_context_length
        )
        self.assertFalse(should_compress)

    def test_should_compress_above_threshold(self):
        """测试高于阈值时压缩"""
        # 创建大量消息以超过阈值
        long_content = "This is a long message. " * 1000
        messages = [Message(role="user", content=long_content) for _ in range(10)]
        max_context_length = 1000  # 很小的上下文长度，容易超过阈值
        should_compress = self.strategy.should_compress(
            messages, "gpt-4", self.tokenizer, max_context_length
        )
        self.assertTrue(should_compress)

    def test_compress_without_provider(self):
        """测试没有 provider 时不压缩"""
        messages = [
            Message(role="user", content="Q1"),
            Message(role="assistant", content="A1"),
            Message(role="user", content="Q2"),
            Message(role="assistant", content="A2"),
            Message(role="user", content="Q3"),
        ]
        compressed = self.strategy.compress(
            messages, "gpt-4", self.tokenizer, 100000, None, None
        )
        # 没有 provider，应该返回原始消息
        self.assertEqual(len(compressed), len(messages))

    def test_compress_keeps_recent_messages(self):
        """测试压缩时保留最新消息"""
        messages = [
            Message(role="user", content="Q1"),
            Message(role="assistant", content="A1"),
            Message(role="user", content="Q2"),
            Message(role="assistant", content="A2"),
            Message(role="user", content="Q3"),
            Message(role="assistant", content="A3"),
        ]
        provider = MockProvider("Summary of Q1, A1, Q2, A2")
        compressed = self.strategy.compress(
            messages, "gpt-4", self.tokenizer, 100000, None, provider
        )
        # 应该保留最新的 3 条消息 + 1 条 summary 消息
        self.assertEqual(len(compressed), 4)
        self.assertEqual(compressed[0].role, "system")
        self.assertIn("总结", compressed[0].content)
        # 最后 3 条消息应该保留（Q3, A3, 但实际只有 Q3 和 A3，因为只有 6 条消息）
        # 检查最后几条消息
        self.assertEqual(compressed[-1].content, "A3")
        self.assertIn(compressed[-2].content, ["Q3", "A2"])  # 可能是 Q3 或 A2

    def test_compress_fewer_messages_than_keep_recent(self):
        """测试消息数少于保留数时不压缩"""
        messages = [
            Message(role="user", content="Q1"),
            Message(role="assistant", content="A1"),
        ]
        provider = MockProvider()
        compressed = self.strategy.compress(
            messages, "gpt-4", self.tokenizer, 100000, None, provider
        )
        # 消息数少于 keep_recent，应该返回原始消息
        self.assertEqual(len(compressed), len(messages))

    def test_compress_provider_error(self):
        """测试 provider 调用失败时的回退"""
        messages = [
            Message(role="user", content="Q1"),
            Message(role="assistant", content="A1"),
            Message(role="user", content="Q2"),
            Message(role="assistant", content="A2"),
            Message(role="user", content="Q3"),
        ]
        # 创建一个会抛出异常的 provider
        provider = MockProvider()
        provider.call = Mock(side_effect=Exception("API Error"))
        compressed = self.strategy.compress(
            messages, "gpt-4", self.tokenizer, 100000, None, provider
        )
        # 应该回退到原始消息
        self.assertEqual(len(compressed), len(messages))

    def test_format_messages_for_summary(self):
        """测试消息格式化"""
        messages = [
            Message(role="user", content="Question 1"),
            Message(role="assistant", content="Answer 1"),
        ]
        formatted = self.strategy._format_messages_for_summary(messages)
        self.assertIn("用户", formatted)
        self.assertIn("助手", formatted)
        self.assertIn("Question 1", formatted)
        self.assertIn("Answer 1", formatted)


class TestSlidingWindowStrategy(unittest.TestCase):
    """SlidingWindowStrategy 测试类"""

    def setUp(self):
        """设置测试环境"""
        self.tokenizer = Tokenizer()
        self.config = ContextStrategyConfig(
            strategy_type="sliding_window",
            sliding_window_size=5,
        )
        self.strategy = SlidingWindowStrategy(self.config)

    def test_should_compress_below_window_size(self):
        """测试消息数少于窗口大小时不压缩"""
        messages = [
            Message(role="user", content="Q1"),
            Message(role="assistant", content="A1"),
        ]
        should_compress = self.strategy.should_compress(
            messages, "gpt-4", self.tokenizer, 100000
        )
        self.assertFalse(should_compress)

    def test_should_compress_above_window_size(self):
        """测试消息数超过窗口大小时压缩"""
        messages = [Message(role="user", content=f"Q{i}") for i in range(10)]
        should_compress = self.strategy.should_compress(
            messages, "gpt-4", self.tokenizer, 100000
        )
        self.assertTrue(should_compress)

    def test_compress_keeps_window_size(self):
        """测试压缩后保留窗口大小的消息"""
        messages = [Message(role="user", content=f"Q{i}") for i in range(10)]
        compressed = self.strategy.compress(
            messages, "gpt-4", self.tokenizer, 100000, None, None
        )
        # 应该只保留最新的 5 条消息
        self.assertEqual(len(compressed), 5)
        self.assertEqual(compressed[0].content, "Q5")
        self.assertEqual(compressed[-1].content, "Q9")

    def test_compress_with_initial_question_in_window(self):
        """测试初始提问在窗口内时不插入"""
        # 创建消息，使初始提问在最后 5 条消息中
        messages = [
            Message(role="user", content="Q1"),
            Message(role="assistant", content="A1"),
            Message(role="user", content="Q2"),
            Message(role="assistant", content="A2"),
            Message(role="user", content="Initial question"),  # 在窗口内
            Message(role="assistant", content="A3"),
            Message(role="user", content="Q4"),
        ]
        compressed = self.strategy.compress(
            messages, "gpt-4", self.tokenizer, 100000, "Initial question", None
        )
        # 初始提问在窗口内，不应该插入 system message
        self.assertEqual(len(compressed), 5)  # 只保留最后 5 条消息
        # 第一条消息不应该是 system message
        self.assertNotEqual(compressed[0].role, "system")
        # 初始提问应该在消息中
        contents = [msg.content for msg in compressed]
        self.assertIn("Initial question", contents)

    def test_compress_with_initial_question_outside_window(self):
        """测试初始提问不在窗口内时插入"""
        messages = [Message(role="user", content=f"Q{i}") for i in range(10)]
        compressed = self.strategy.compress(
            messages, "gpt-4", self.tokenizer, 100000, "Initial question", None
        )
        # 应该插入初始提问作为 system message
        self.assertEqual(len(compressed), 6)  # 5 条消息 + 1 条 system message
        self.assertEqual(compressed[0].role, "system")
        self.assertIn("Initial question", compressed[0].content)
        # 最后 5 条消息应该保留
        self.assertEqual(compressed[1].content, "Q5")
        self.assertEqual(compressed[-1].content, "Q9")

    def test_compress_without_initial_question(self):
        """测试没有初始提问时只保留窗口消息"""
        messages = [Message(role="user", content=f"Q{i}") for i in range(10)]
        compressed = self.strategy.compress(
            messages, "gpt-4", self.tokenizer, 100000, None, None
        )
        # 应该只保留最新的 5 条消息
        self.assertEqual(len(compressed), 5)
        self.assertEqual(compressed[0].content, "Q5")

    def test_compress_empty_messages(self):
        """测试空消息列表"""
        compressed = self.strategy.compress(
            [], "gpt-4", self.tokenizer, 100000, None, None
        )
        self.assertEqual(len(compressed), 0)

