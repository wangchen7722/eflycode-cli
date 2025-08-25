#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""压缩器测试用例"""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime

from echo.agents.core.context.compressor import (
    BaseCompressor,
    CompressionResult,
    SummaryCompressor,
    SlidingWindowCompressor,
    KeyExtractionCompressor,
    HybridCompressor,
    create_compressor
)
from echo.llms.schema import Message
from echo.config import CompressionConfig, CompressionStrategy


class TestCompressionResult(unittest.TestCase):
    """压缩结果测试"""
    
    def test_compression_result_creation(self):
        """测试压缩结果创建"""
        messages = [Message(role="user", content="test")]
        result = CompressionResult(
            compressed_messages=messages,
            original_token_count=100,
            compressed_token_count=50,
            compression_ratio=0.5,
            metadata={"strategy": "test"}
        )
        
        self.assertEqual(result.compressed_messages, messages)
        self.assertEqual(result.original_token_count, 100)
        self.assertEqual(result.compressed_token_count, 50)
        self.assertEqual(result.compression_ratio, 0.5)
        self.assertEqual(result.metadata["strategy"], "test")


class TestSummaryCompressor(unittest.TestCase):
    """摘要压缩器测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.mock_llm = Mock()
        self.mock_token_calculator = Mock()
        self.config = CompressionConfig(
            strategy=CompressionStrategy.SUMMARY,
            target_token_count=100,
            preserve_recent_count=2
        )
        self.compressor = SummaryCompressor(self.mock_llm, self.mock_token_calculator, self.config)
    
    def test_compress_empty_messages(self):
        """测试压缩空消息列表"""
        result = self.compressor.compress([])
        
        self.assertEqual(result.compressed_messages, [])
        self.assertEqual(result.original_token_count, 0)
        self.assertEqual(result.compressed_token_count, 0)
        self.assertEqual(result.compression_ratio, 1.0)
    
    def test_compress_few_messages(self):
        """测试压缩少量消息"""
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there!")
        ]
        self.mock_token_calculator.calculate_tokens.return_value = 10
        
        result = self.compressor.compress(messages)
        
        self.assertEqual(result.compressed_messages, messages)
        self.assertEqual(result.original_token_count, 20)  # 2 messages * 10 tokens
        self.assertEqual(result.compressed_token_count, 20)
        self.assertEqual(result.compression_ratio, 1.0)
    
    @patch('echo.agents.core.context.compressor.summary.logger')
    def test_compress_with_summary(self, mock_logger):
        """测试带摘要的压缩"""
        messages = [
            Message(role="user", content="First message"),
            Message(role="assistant", content="First response"),
            Message(role="user", content="Second message"),
            Message(role="assistant", content="Second response"),
            Message(role="user", content="Recent message"),
            Message(role="assistant", content="Recent response")
        ]
        
        # 模拟token计算
        self.mock_token_calculator.calculate_tokens.side_effect = [15, 15, 16, 16, 14, 15]  # 各消息token数
        
        # 模拟LLM生成摘要
        mock_response = Mock()
        mock_response.content = "Summary of conversation"
        self.mock_llm.generate.return_value = mock_response
        
        result = self.compressor.compress(messages)
        
        # 验证结果
        self.assertEqual(len(result.compressed_messages), 3)  # 摘要 + 2条最近消息
        self.assertEqual(result.compressed_messages[0].role, "system")
        self.assertIn("Summary of conversation", result.compressed_messages[0].content)
        self.assertEqual(result.compressed_messages[1], messages[-2])  # 倒数第二条
        self.assertEqual(result.compressed_messages[2], messages[-1])  # 最后一条
        
        # 验证LLM被调用
        self.mock_llm.generate.assert_called_once()
    
    def test_generate_summary_prompt(self):
        """测试摘要提示生成"""
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi!")
        ]
        
        prompt = self.compressor._generate_summary_prompt(messages)
        
        self.assertIn("请总结以下对话内容", prompt)
        self.assertIn("Hello", prompt)
        self.assertIn("Hi!", prompt)


class TestSlidingWindowCompressor(unittest.TestCase):
    """滑动窗口压缩器测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.mock_token_calculator = Mock()
        self.config = CompressionConfig(
            strategy=CompressionStrategy.SLIDING_WINDOW,
            target_token_count=50,
            preserve_recent_count=3
        )
        self.compressor = SlidingWindowCompressor(self.mock_token_calculator, self.config)
    
    def test_compress_within_limit(self):
        """测试在限制范围内的压缩"""
        messages = [
            Message(role="user", content="Message 1"),
            Message(role="assistant", content="Response 1")
        ]
        self.mock_token_calculator.calculate_tokens.return_value = 20
        
        result = self.compressor.compress(messages)
        
        self.assertEqual(result.compressed_messages, messages)
        self.assertEqual(result.compression_ratio, 1.0)
    
    def test_compress_exceeds_limit(self):
        """测试超出限制的压缩"""
        messages = [
            Message(role="user", content="Old message 1"),
            Message(role="assistant", content="Old response 1"),
            Message(role="user", content="Old message 2"),
            Message(role="assistant", content="Old response 2"),
            Message(role="user", content="Recent message"),
            Message(role="assistant", content="Recent response")
        ]
        
        # 模拟token计算：每条消息20个token
        self.mock_token_calculator.calculate_tokens.return_value = 20
        
        result = self.compressor.compress(messages)
        
        # 应该保留最近的3条消息
        self.assertEqual(len(result.compressed_messages), 3)
        self.assertEqual(result.compressed_messages, messages[-3:])
        self.assertEqual(result.original_token_count, 120)  # 6 * 20
        self.assertEqual(result.compressed_token_count, 60)  # 3 * 20
        self.assertEqual(result.compression_ratio, 0.5)


class TestKeyExtractionCompressor(unittest.TestCase):
    """关键信息提取压缩器测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.mock_token_calculator = Mock()
        self.config = CompressionConfig(
            strategy=CompressionStrategy.KEY_EXTRACTION,
            target_token_count=100
        )
        self.compressor = KeyExtractionCompressor(self.mock_token_calculator, self.config)
    
    def test_extract_key_messages(self):
        """测试关键消息提取"""
        messages = [
            Message(role="user", content="Hello"),  # 普通消息
            Message(role="assistant", content="Error: Something went wrong"),  # 包含关键词
            Message(role="user", content="How to fix this problem?"),  # 包含关键词
            Message(role="assistant", content="Try this solution"),  # 包含关键词
            Message(role="user", content="Thanks"),  # 普通消息
        ]
        
        self.mock_token_calculator.calculate_tokens.return_value = 15
        
        result = self.compressor.compress(messages)
        
        # 应该提取包含关键词的消息
        self.assertGreater(len(result.compressed_messages), 0)
        self.assertLess(len(result.compressed_messages), len(messages))
    
    def test_has_key_patterns(self):
        """测试关键模式检测"""
        # 测试错误关键词
        self.assertTrue(self.compressor._has_key_patterns("Error occurred"))
        self.assertTrue(self.compressor._has_key_patterns("Failed to process"))
        
        # 测试问题关键词
        self.assertTrue(self.compressor._has_key_patterns("How to solve this?"))
        self.assertTrue(self.compressor._has_key_patterns("What is the problem?"))
        
        # 测试代码块
        self.assertTrue(self.compressor._has_key_patterns("```python\nprint('hello')\n```"))
        
        # 测试URL
        self.assertTrue(self.compressor._has_key_patterns("Check https://example.com"))
        
        # 测试文件路径
        self.assertTrue(self.compressor._has_key_patterns("Edit /path/to/file.py"))
        
        # 测试普通文本
        self.assertFalse(self.compressor._has_key_patterns("Just a normal message"))
    
    def test_calculate_importance_score(self):
        """测试重要性分数计算"""
        # 长消息应该有更高分数
        long_message = Message(role="user", content="This is a very long message " * 20)
        short_message = Message(role="user", content="Short")
        
        long_score = self.compressor._calculate_importance_score(long_message)
        short_score = self.compressor._calculate_importance_score(short_message)
        
        self.assertGreater(long_score, short_score)
        
        # 包含关键词的消息应该有更高分数
        key_message = Message(role="user", content="Error: Something failed")
        normal_message = Message(role="user", content="Hello there")
        
        key_score = self.compressor._calculate_importance_score(key_message)
        normal_score = self.compressor._calculate_importance_score(normal_message)
        
        self.assertGreater(key_score, normal_score)


class TestHybridCompressor(unittest.TestCase):
    """混合压缩器测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.mock_llm = Mock()
        self.mock_token_calculator = Mock()
        self.config = CompressionConfig(
            strategy=CompressionStrategy.HYBRID,
            target_token_count=100
        )
        self.compressor = HybridCompressor(self.mock_llm, self.mock_token_calculator, self.config)
    
    def test_select_strategy_few_messages(self):
        """测试少量消息的策略选择"""
        messages = [Message(role="user", content="Hello")]
        strategy = self.compressor._select_strategy(messages, 50)
        self.assertEqual(strategy, "sliding_window")
    
    def test_select_strategy_many_messages_low_tokens(self):
        """测试多消息低token的策略选择"""
        messages = [Message(role="user", content="Hi")] * 15
        strategy = self.compressor._select_strategy(messages, 200)
        self.assertEqual(strategy, "key_extraction")
    
    def test_select_strategy_many_messages_high_tokens(self):
        """测试多消息高token的策略选择"""
        messages = [Message(role="user", content="Hi")] * 15
        strategy = self.compressor._select_strategy(messages, 2000)
        self.assertEqual(strategy, "summary")
    
    @patch('echo.agents.core.context.compressor.hybrid.SlidingWindowCompressor')
    def test_compress_with_sliding_window(self, mock_sliding_compressor_class):
        """测试使用滑动窗口压缩"""
        messages = [Message(role="user", content="Hello")]
        self.mock_token_calculator.calculate_tokens.return_value = 10
        
        # 模拟滑动窗口压缩器
        mock_compressor = Mock()
        mock_result = CompressionResult(
            compressed_messages=messages,
            original_token_count=10,
            compressed_token_count=10,
            compression_ratio=1.0
        )
        mock_compressor.compress.return_value = mock_result
        mock_sliding_compressor_class.return_value = mock_compressor
        
        result = self.compressor.compress(messages)
        
        self.assertEqual(result, mock_result)
        mock_sliding_compressor_class.assert_called_once()
        mock_compressor.compress.assert_called_once_with(messages)


class TestCreateCompressor(unittest.TestCase):
    """压缩器工厂函数测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.mock_llm = Mock()
        self.mock_token_calculator = Mock()
    
    def test_create_summary_compressor(self):
        """测试创建摘要压缩器"""
        config = CompressionConfig(strategy=CompressionStrategy.SUMMARY)
        compressor = create_compressor(config, self.mock_llm, self.mock_token_calculator)
        self.assertIsInstance(compressor, SummaryCompressor)
    
    def test_create_sliding_window_compressor(self):
        """测试创建滑动窗口压缩器"""
        config = CompressionConfig(strategy=CompressionStrategy.SLIDING_WINDOW)
        compressor = create_compressor(config, None, self.mock_token_calculator)
        self.assertIsInstance(compressor, SlidingWindowCompressor)
    
    def test_create_key_extraction_compressor(self):
        """测试创建关键信息提取压缩器"""
        config = CompressionConfig(strategy=CompressionStrategy.KEY_EXTRACTION)
        compressor = create_compressor(config, None, self.mock_token_calculator)
        self.assertIsInstance(compressor, KeyExtractionCompressor)
    
    def test_create_hybrid_compressor(self):
        """测试创建混合压缩器"""
        config = CompressionConfig(strategy=CompressionStrategy.HYBRID)
        compressor = create_compressor(config, self.mock_llm, self.mock_token_calculator)
        self.assertIsInstance(compressor, HybridCompressor)
    
    def test_create_summary_without_llm(self):
        """测试创建摘要压缩器但没有LLM引擎"""
        config = CompressionConfig(strategy=CompressionStrategy.SUMMARY)
        with self.assertRaises(ValueError) as context:
            create_compressor(config, None, self.mock_token_calculator)
        self.assertIn("LLM引擎", str(context.exception))
    
    def test_create_hybrid_without_llm(self):
        """测试创建混合压缩器但没有LLM引擎"""
        config = CompressionConfig(strategy=CompressionStrategy.HYBRID)
        with self.assertRaises(ValueError) as context:
            create_compressor(config, None, self.mock_token_calculator)
        self.assertIn("LLM引擎", str(context.exception))
    
    def test_create_unsupported_strategy(self):
        """测试创建不支持的策略"""
        config = Mock()
        config.strategy = "unsupported_strategy"
        
        with self.assertRaises(ValueError) as context:
            create_compressor(config, self.mock_llm, self.mock_token_calculator)
        self.assertIn("不支持的压缩策略", str(context.exception))


if __name__ == '__main__':
    unittest.main()