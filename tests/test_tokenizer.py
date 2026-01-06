"""Tokenizer 测试用例"""

import unittest

from eflycode.core.context.tokenizer import Tokenizer
from eflycode.core.llm.protocol import Message, ToolCall, ToolCallFunction


class TestTokenizer(unittest.TestCase):
    """Tokenizer 测试类"""

    def setUp(self):
        """设置测试环境"""
        self.tokenizer = Tokenizer()

    def test_get_encoding_for_model(self):
        """测试获取模型的编码器"""
        encoding = self.tokenizer.get_encoding_for_model("gpt-4")
        self.assertIsNotNone(encoding)

        encoding2 = self.tokenizer.get_encoding_for_model("deepseek-chat")
        self.assertIsNotNone(encoding2)

        # 应该使用相同的编码器（都是 cl100k_base）
        self.assertEqual(encoding.name, encoding2.name)

    def test_get_encoding_for_unknown_model(self):
        """测试未知模型的编码器"""
        encoding = self.tokenizer.get_encoding_for_model("unknown-model")
        self.assertIsNotNone(encoding)
        # 应该使用默认编码器
        self.assertEqual(encoding.name, "cl100k_base")

    def test_count_message_tokens_simple(self):
        """测试计算简单消息的 token 数"""
        message = Message(role="user", content="Hello, world!")
        tokens = self.tokenizer.count_message_tokens(message, "gpt-4")
        self.assertGreater(tokens, 0)
        # "Hello, world!" 大约 3-4 个 token，加上格式 token 大约 7-8 个
        self.assertGreaterEqual(tokens, 5)

    def test_count_message_tokens_empty(self):
        """测试计算空消息的 token 数"""
        message = Message(role="user", content="")
        tokens = self.tokenizer.count_message_tokens(message, "gpt-4")
        # 即使内容为空，也有格式 token
        self.assertGreater(tokens, 0)

    def test_count_message_tokens_with_tool_calls(self):
        """测试计算带工具调用的消息的 token 数"""
        tool_call = ToolCall(
            id="call_123",
            type="function",
            function=ToolCallFunction(name="test_tool", arguments='{"arg": "value"}'),
        )
        message = Message(role="assistant", content="I'll use a tool", tool_calls=[tool_call])
        tokens = self.tokenizer.count_message_tokens(message, "gpt-4")
        self.assertGreater(tokens, 0)
        # 应该比简单消息更多
        self.assertGreater(tokens, 10)

    def test_count_message_tokens_with_tool_call_id(self):
        """测试计算带 tool_call_id 的消息的 token 数"""
        message = Message(role="tool", content="Tool result", tool_call_id="call_123")
        tokens = self.tokenizer.count_message_tokens(message, "gpt-4")
        self.assertGreater(tokens, 0)

    def test_count_tokens_multiple_messages(self):
        """测试计算多条消息的 token 数"""
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there"),
            Message(role="user", content="How are you?"),
        ]
        total_tokens = self.tokenizer.count_tokens(messages, "gpt-4")
        self.assertGreater(total_tokens, 0)

        # 应该比单条消息多
        single_tokens = self.tokenizer.count_message_tokens(messages[0], "gpt-4")
        self.assertGreater(total_tokens, single_tokens)

    def test_count_tokens_empty_list(self):
        """测试计算空消息列表的 token 数"""
        tokens = self.tokenizer.count_tokens([], "gpt-4")
        self.assertEqual(tokens, 0)

    def test_count_tokens_different_models(self):
        """测试不同模型的 token 计算"""
        message = Message(role="user", content="Hello, world!")
        
        tokens_gpt4 = self.tokenizer.count_message_tokens(message, "gpt-4")
        tokens_deepseek = self.tokenizer.count_message_tokens(message, "deepseek-chat")
        tokens_unknown = self.tokenizer.count_message_tokens(message, "unknown-model")
        
        # 所有模型应该返回相同的 token 数（都使用 cl100k_base）
        self.assertEqual(tokens_gpt4, tokens_deepseek)
        self.assertEqual(tokens_gpt4, tokens_unknown)

    def test_count_tokens_long_content(self):
        """测试计算长内容的 token 数"""
        long_content = "Hello, world! " * 100
        message = Message(role="user", content=long_content)
        tokens = self.tokenizer.count_message_tokens(message, "gpt-4")
        self.assertGreater(tokens, 100)  # 应该有很多 token

    def test_encoding_caching(self):
        """测试编码器缓存"""
        encoding1 = self.tokenizer.get_encoding_for_model("gpt-4")
        encoding2 = self.tokenizer.get_encoding_for_model("gpt-4")
        # 应该是同一个对象（缓存）
        self.assertIs(encoding1, encoding2)

