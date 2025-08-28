#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
压缩器测试用例

测试各种压缩器的功能，包括基于上下文长度的新压缩逻辑。
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from typing import List

from echo.llms.schema import Message
from echo.config import CompressionConfig, CompressionStrategy, TokenCalculationStrategy
from echo.agents.core.token_calculator import TokenCalculator
from echo.agents.core.context.compressor.base import BaseCompressor, CompressionResult
from echo.agents.core.context.compressor.summary import SummaryCompressor
from echo.agents.core.context.compressor.key_extraction import KeyExtractionCompressor
from echo.agents.core.context.compressor.sliding_window import SlidingWindowCompressor
from echo.agents.core.context.compressor.chain import CompressorChain, CompressorChainConfig, CompressorType
from echo.llms.llm_engine import LLMEngine


class TestCompressionConfig(unittest.TestCase):
    """测试新的压缩配置"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = CompressionConfig()
        
        self.assertEqual(config.strategy, CompressionStrategy.CHAIN)
        self.assertEqual(config.compression_ratio, 0.3)
        self.assertEqual(config.preserve_recent_messages, 5)
        self.assertEqual(config.max_context_length, 32000)
        self.assertEqual(config.context_usage_threshold, 0.8)
        self.assertEqual(config.target_context_length_ratio, 0.6)
    
    def test_compression_trigger_length(self):
        """测试压缩触发长度计算"""
        config = CompressionConfig(
            max_context_length=10000,
            context_usage_threshold=0.8
        )
        
        self.assertEqual(config.compression_trigger_length, 8000)
    
    def test_target_context_length(self):
        """测试目标上下文长度计算"""
        config = CompressionConfig(
            max_context_length=10000,
            target_context_length_ratio=0.6
        )
        
        self.assertEqual(config.target_context_length, 6000)


class TestSummaryCompressor(unittest.TestCase):
    """摘要压缩器测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.config = CompressionConfig(
            max_context_length=1000,
            context_usage_threshold=0.8,
            target_context_length_ratio=0.6,
            preserve_recent_messages=2,
            summary_max_tokens=100
        )
        
        self.mock_token_calculator = Mock(spec=TokenCalculator)
        self.mock_llm_engine = Mock(spec=LLMEngine)
        
        self.compressor = SummaryCompressor(
            config=self.config,
            token_calculator=self.mock_token_calculator,
            llm_engine=self.mock_llm_engine
        )
    
    def test_compress_empty_messages(self):
        """测试空消息列表压缩"""
        messages = []
        
        self.mock_token_calculator.calculate_messages_tokens.return_value = 0
        
        result = self.compressor.compress(messages)
        
        self.assertEqual(result.compressed_messages, [])
        self.assertEqual(result.original_count, 0)
        self.assertEqual(result.compressed_count, 0)
        self.assertEqual(result.compression_ratio, 1.0)
    
    def test_compress_within_context_limit(self):
        """测试在上下文限制内的压缩"""
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there!")
        ]
        
        # 模拟token数量在限制内
        self.mock_token_calculator.calculate_messages_tokens.return_value = 500
        
        result = self.compressor.compress(messages)
        
        # 应该不进行压缩
        self.assertEqual(result.compressed_messages, messages)
        self.assertEqual(result.compression_ratio, 1.0)
        self.assertEqual(result.metadata["reason"], "within_context_limit")
    
    @patch('echo.agents.core.context.compressor.summary.logger')
    def test_compress_with_summary_generation(self, mock_logger):
        """测试生成摘要的压缩"""
        messages = [
            Message(role="user", content="What is Python?"),
            Message(role="assistant", content="Python is a programming language."),
            Message(role="user", content="How to use it?"),
            Message(role="assistant", content="You can write scripts and applications."),
            Message(role="user", content="Thanks!")
        ]
        
        # 模拟token数量超过限制
        self.mock_token_calculator.calculate_messages_tokens.side_effect = [
            1000,  # 原始消息总token数
            800,   # 需要压缩的消息token数
            200,   # 最近消息token数
            300    # 压缩后消息token数
        ]
        
        # 模拟LLM生成摘要
        self.mock_llm_engine.generate.return_value = "Discussion about Python programming language."
        
        result = self.compressor.compress(messages)
        
        # 验证压缩结果
        self.assertEqual(result.original_count, 5)
        self.assertLess(result.compressed_count, 5)
        self.assertLess(result.compression_ratio, 1.0)
        self.assertEqual(result.metadata["strategy"], "summary")
        
        # 验证LLM被调用
        self.mock_llm_engine.generate.assert_called_once()


class TestKeyExtractionCompressor(unittest.TestCase):
    """关键信息提取压缩器测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.config = CompressionConfig(
            max_context_length=1000,
            context_usage_threshold=0.8,
            preserve_recent_messages=2
        )
        
        self.mock_token_calculator = Mock(spec=TokenCalculator)
        
        self.compressor = KeyExtractionCompressor(
            config=self.config,
            token_calculator=self.mock_token_calculator
        )
    
    def test_extract_key_messages(self):
        """测试关键消息提取"""
        messages = [
            Message(role="user", content="Hello there"),
            Message(role="assistant", content="This is an important error message"),
            Message(role="user", content="Just chatting"),
            Message(role="assistant", content="Critical API failure detected"),
            Message(role="user", content="Recent message 1"),
            Message(role="assistant", content="Recent message 2")
        ]
        
        # 模拟token计算
        self.mock_token_calculator.calculate_messages_tokens.side_effect = [
            1000,  # 原始消息总token数
            600    # 压缩后消息token数
        ]
        
        result = self.compressor.compress(messages)
        
        # 验证关键消息被保留
        self.assertLess(result.compressed_count, result.original_count)
        self.assertEqual(result.metadata["strategy"], "key_extraction")
        
        # 验证包含关键词的消息被保留
        compressed_content = [msg.content for msg in result.compressed_messages]
        self.assertTrue(any("important" in content or "error" in content for content in compressed_content))
        self.assertTrue(any("Critical" in content or "API" in content for content in compressed_content))
    
    def test_key_pattern_detection(self):
        """测试关键模式检测"""
        # 测试中文关键词
        self.assertTrue(self.compressor._contains_key_info("这是一个重要的问题"))
        self.assertTrue(self.compressor._contains_key_info("发生了错误"))
        
        # 测试英文关键词
        self.assertTrue(self.compressor._contains_key_info("This is critical"))
        self.assertTrue(self.compressor._contains_key_info("API error occurred"))
        
        # 测试普通文本
        self.assertFalse(self.compressor._contains_key_info("Just normal conversation"))


class TestSlidingWindowCompressor(unittest.TestCase):
    """滑动窗口压缩器测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.config = CompressionConfig(
            max_context_length=1000,
            context_usage_threshold=0.8
        )
        
        self.mock_token_calculator = Mock(spec=TokenCalculator)
        
        self.compressor = SlidingWindowCompressor(
            config=self.config,
            token_calculator=self.mock_token_calculator,
            token_ratio=0.6
        )
    
    def test_compress_within_token_limit(self):
        """测试在token限制内的压缩"""
        messages = [
            Message(role="user", content="Message 1"),
            Message(role="assistant", content="Response 1")
        ]
        
        # 模拟token数量在限制内
        self.mock_token_calculator.calculate_messages_tokens.return_value = 400
        
        result = self.compressor.compress(messages)
        
        # 应该不进行压缩
        self.assertEqual(result.compressed_messages, messages)
        self.assertEqual(result.compression_ratio, 1.0)
        self.assertEqual(result.metadata["reason"], "within_token_limit")
    
    def test_compress_exceeds_token_limit(self):
        """测试超过token限制的压缩"""
        messages = [
            Message(role="user", content="Old message 1"),
            Message(role="assistant", content="Old response 1"),
            Message(role="user", content="Old message 2"),
            Message(role="assistant", content="Old response 2"),
            Message(role="user", content="Recent message"),
            Message(role="assistant", content="Recent response")
        ]
        
        # 模拟token计算：总数超限，但最近的消息在限制内
        def mock_token_calc(msgs):
            if len(msgs) == 6:  # 所有消息
                return 1000
            elif len(msgs) == 1:  # 单条消息
                return 100
            elif len(msgs) == 2:  # 最近两条消息
                return 200
            else:
                return len(msgs) * 100
        
        self.mock_token_calculator.calculate_messages_tokens.side_effect = mock_token_calc
        
        result = self.compressor.compress(messages)
        
        # 验证压缩结果
        self.assertLess(result.compressed_count, result.original_count)
        self.assertLess(result.compression_ratio, 1.0)
        self.assertEqual(result.metadata["strategy"], "sliding_window")
        
        # 验证保留的是最新的消息
        self.assertIn("Recent", result.compressed_messages[-1].content)


class TestCompressorChain(unittest.TestCase):
    """压缩器链测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.config = CompressionConfig(
            max_context_length=1000,
            context_usage_threshold=0.8,
            chain_compressor_types=["key_extraction", "sliding_window"],
            chain_selection_strategy="best_ratio"
        )
        
        self.mock_token_calculator = Mock(spec=TokenCalculator)
        self.mock_llm_engine = Mock(spec=LLMEngine)
        
        self.chain_config = CompressorChainConfig(
            compressor_types=[CompressorType.KEY_EXTRACTION, CompressorType.SLIDING_WINDOW],
            selection_strategy="best_ratio"
        )
        
        self.compressor_chain = CompressorChain(
            config=self.config,
            token_calculator=self.mock_token_calculator,
            chain_config=self.chain_config,
            llm_engine=self.mock_llm_engine
        )
    
    def test_chain_initialization(self):
        """测试压缩器链初始化"""
        self.assertEqual(len(self.compressor_chain.compressors), 2)
        self.assertIsInstance(self.compressor_chain.compressors[0], KeyExtractionCompressor)
        self.assertIsInstance(self.compressor_chain.compressors[1], SlidingWindowCompressor)
    
    @patch('echo.agents.core.context.compressor.chain.logger')
    def test_compress_with_best_ratio_selection(self, mock_logger):
        """测试使用最佳压缩比选择策略的压缩"""
        messages = [
            Message(role="user", content="Important error occurred"),
            Message(role="assistant", content="Let me help you"),
            Message(role="user", content="Critical API failure"),
            Message(role="assistant", content="I'll investigate")
        ]
        
        # 模拟token计算
        self.mock_token_calculator.calculate_messages_tokens.side_effect = [
            1000,  # 原始消息
            600,   # 关键提取结果
            400,   # 滑动窗口结果
            1000,  # 原始消息（第二次调用）
            400    # 滑动窗口结果（第二次调用）
        ]
        
        result = self.compressor_chain.compress(messages)
        
        # 验证选择了压缩比更好的结果
        self.assertEqual(result.metadata["chain_strategy"], "best_ratio")
        self.assertIn("selected_compressor", result.metadata)
    
    def test_compress_with_summary_in_chain(self):
        """测试包含摘要压缩器的压缩器链"""
        chain_config = CompressorChainConfig(
            compressor_types=[CompressorType.SUMMARY, CompressorType.SLIDING_WINDOW],
            selection_strategy="best_ratio"
        )
        
        compressor_chain = CompressorChain(
            config=self.config,
            token_calculator=self.mock_token_calculator,
            chain_config=chain_config,
            llm_engine=self.mock_llm_engine
        )
        
        # 验证摘要压缩器被正确创建
        self.assertEqual(len(compressor_chain.compressors), 2)
        self.assertIsInstance(compressor_chain.compressors[0], SummaryCompressor)
        self.assertIsInstance(compressor_chain.compressors[1], SlidingWindowCompressor)


class TestCompressionIntegration(unittest.TestCase):
    """压缩器集成测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.config = CompressionConfig(
            max_context_length=2000,
            context_usage_threshold=0.8,
            target_context_length_ratio=0.6,
            preserve_recent_messages=3
        )
        
        self.mock_token_calculator = Mock(spec=TokenCalculator)
        self.mock_llm_engine = Mock(spec=LLMEngine)
    
    def test_context_length_based_compression_trigger(self):
        """测试基于上下文长度的压缩触发"""
        messages = self._create_test_messages(10)
        
        # 模拟token数量超过触发阈值
        trigger_length = self.config.compression_trigger_length  # 1600
        self.mock_token_calculator.calculate_messages_tokens.return_value = trigger_length + 100
        
        compressor = SlidingWindowCompressor(
            config=self.config,
            token_calculator=self.mock_token_calculator
        )
        
        # 设置压缩后的token数量
        self.mock_token_calculator.calculate_messages_tokens.side_effect = [
            trigger_length + 100,  # 原始消息
            self.config.target_context_length  # 压缩后消息
        ]
        
        result = compressor.compress(messages)
        
        # 验证压缩被触发
        self.assertLess(result.compression_ratio, 1.0)
    
    def test_preserve_recent_messages(self):
        """测试保留最近消息功能"""
        messages = self._create_test_messages(8)
        
        # 模拟需要压缩的情况
        self.mock_token_calculator.calculate_messages_tokens.side_effect = [
            2000,  # 原始消息总数
            1000   # 压缩后消息数
        ]
        
        compressor = KeyExtractionCompressor(
            config=self.config,
            token_calculator=self.mock_token_calculator
        )
        
        result = compressor.compress(messages)
        
        # 验证最近的消息被保留
        recent_messages = messages[-self.config.preserve_recent_messages:]
        compressed_recent = result.compressed_messages[-self.config.preserve_recent_messages:]
        
        for original, compressed in zip(recent_messages, compressed_recent):
            self.assertEqual(original.content, compressed.content)
    
    def _create_test_messages(self, count: int) -> List[Message]:
        """创建测试消息列表"""
        messages = []
        for i in range(count):
            if i % 2 == 0:
                messages.append(Message(role="user", content=f"User message {i}"))
            else:
                messages.append(Message(role="assistant", content=f"Assistant response {i}"))
        return messages


if __name__ == '__main__':
    unittest.main()