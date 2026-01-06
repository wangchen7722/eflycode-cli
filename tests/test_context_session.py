"""Session 上下文管理集成测试用例"""

import unittest
from unittest.mock import Mock

from eflycode.core.agent.session import Session
from eflycode.core.context.strategies import ContextStrategyConfig
from eflycode.core.llm.protocol import DEFAULT_MAX_CONTEXT_LENGTH, Message
from eflycode.core.llm.providers.base import LLMProvider


class MockProvider(LLMProvider):
    """Mock Provider 用于测试"""

    def __init__(self):
        self.call_count = 0

    @property
    def capabilities(self):
        from eflycode.core.llm.providers.base import ProviderCapabilities
        return ProviderCapabilities(supports_streaming=True, supports_tools=True)

    def call(self, request):
        self.call_count += 1
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


class TestSessionContextIntegration(unittest.TestCase):
    """Session 上下文管理集成测试类"""

    def setUp(self):
        """设置测试环境"""
        self.provider = MockProvider()

    def test_session_without_context_config(self):
        """测试没有上下文配置的 Session"""
        session = Session()
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi")
        
        context = session.get_context(
            "gpt-4",
            max_context_length=DEFAULT_MAX_CONTEXT_LENGTH,
            provider=self.provider,
        )
        # 没有配置，应该返回所有消息
        self.assertEqual(len(context.messages), 2)

    def test_session_initial_question_recording(self):
        """测试记录初始提问"""
        session = Session()
        session.add_message("user", "This is my first question")
        session.add_message("assistant", "Answer")
        session.add_message("user", "Second question")
        
        self.assertEqual(session._initial_user_question, "This is my first question")

    def test_session_initial_question_only_first(self):
        """测试只记录第一条 user 消息"""
        session = Session()
        session.add_message("user", "First question")
        session.add_message("assistant", "Answer")
        session.add_message("user", "Second question")
        
        # 应该只记录第一条
        self.assertEqual(session._initial_user_question, "First question")

    def test_session_initial_question_empty_content(self):
        """测试空内容不记录为初始提问"""
        session = Session()
        session.add_message("user", "")
        session.add_message("user", "Real question")
        
        self.assertEqual(session._initial_user_question, "Real question")

    def test_session_clear_resets_initial_question(self):
        """测试清空会话时重置初始提问"""
        session = Session()
        session.add_message("user", "Question")
        self.assertIsNotNone(session._initial_user_question)
        
        session.clear()
        self.assertIsNone(session._initial_user_question)

    def test_session_with_sliding_window_strategy(self):
        """测试 Session 使用滑动窗口策略"""
        config = ContextStrategyConfig(
            strategy_type="sliding_window",
            sliding_window_size=3,
        )
        session = Session(context_config=config)
        
        # 添加多条消息
        for i in range(5):
            session.add_message("user", f"Q{i}")
            session.add_message("assistant", f"A{i}")
        
        context = session.get_context(
            "gpt-4",
            max_context_length=DEFAULT_MAX_CONTEXT_LENGTH,
            provider=self.provider,
        )
        # 应该被压缩到窗口大小
        self.assertLessEqual(len(context.messages), 4)  # 3 条消息 + 可能的初始提问

    def test_session_with_summary_strategy(self):
        """测试 Session 使用 Summary 策略"""
        config = ContextStrategyConfig(
            strategy_type="summary",
            summary_threshold=0.8,
            summary_keep_recent=2,
        )
        session = Session(context_config=config)
        
        # 添加大量消息以触发压缩
        long_content = "This is a long message. " * 100
        for i in range(5):
            session.add_message("user", long_content + f" Q{i}")
            session.add_message("assistant", f"A{i}")
        
        context = session.get_context(
            "gpt-4",
            max_context_length=1000,  # 很小的上下文长度
            provider=self.provider,
        )
        # 应该被压缩
        self.assertLess(len(context.messages), 10)

    def test_session_context_manager_initialization(self):
        """测试上下文管理器的初始化"""
        config = ContextStrategyConfig(strategy_type="sliding_window")
        session = Session(context_config=config)
        self.assertIsNotNone(session.context_manager)
        
        session2 = Session()
        self.assertIsNone(session2.context_manager)

    def test_session_get_context_passes_provider(self):
        """测试 get_context 传递 provider"""
        config = ContextStrategyConfig(
            strategy_type="summary",
            summary_threshold=0.8,
            summary_keep_recent=2,
        )
        session = Session(context_config=config)
        
        long_content = "Long message. " * 100
        for i in range(5):
            session.add_message("user", long_content)
        
        # 使用真实的 MockProvider
        provider = MockProvider()
        initial_call_count = provider.call_count
        
        context = session.get_context(
            "gpt-4",
            max_context_length=1000,
            provider=provider,
        )
        # 如果触发了压缩，provider 应该被调用
        if len(context.messages) < 5:
            # 只有在实际压缩时才调用
            self.assertGreater(provider.call_count, initial_call_count)

