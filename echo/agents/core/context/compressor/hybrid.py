#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
混合压缩器模块

结合多种压缩策略的混合压缩器。
"""

from typing import List, Optional

from echo.llms.schema import Message
from echo.llms.llm_engine import LLMEngine
from echo.agents.core.token_calculator import TokenCalculator
from echo.config import CompressionConfig
from echo.utils.logger import get_logger
from .base import BaseCompressor, CompressionResult
from .summary import SummaryCompressor
from .sliding_window import SlidingWindowCompressor
from .key_extraction import KeyExtractionCompressor

logger = get_logger()


class HybridCompressor(BaseCompressor):
    """混合压缩器"""
    
    def __init__(self, config: CompressionConfig, token_calculator: TokenCalculator, llm_engine: Optional[LLMEngine] = None):
        super().__init__(config, token_calculator)
        self.llm_engine = llm_engine
        
        # 初始化子压缩器
        self.summary_compressor = SummaryCompressor(config, token_calculator, llm_engine) if llm_engine else None
        self.sliding_window_compressor = SlidingWindowCompressor(config, token_calculator)
        self.key_extraction_compressor = KeyExtractionCompressor(config, token_calculator)
    
    def compress(self, messages: List[Message]) -> CompressionResult:
        """使用混合策略进行压缩"""
        if len(messages) < self.config.min_messages_to_compress:
            return CompressionResult(
                compressed_messages=messages,
                original_count=len(messages),
                compressed_count=len(messages),
                compression_ratio=1.0,
                preserved_tokens=self._calculate_messages_tokens(messages),
                metadata={"strategy": "hybrid", "reason": "insufficient_messages"}
            )
        
        original_tokens = self._calculate_messages_tokens(messages)
        
        # 根据消息数量和token数选择策略
        if original_tokens > self.config.max_context_tokens * 0.8:
            # 高压缩需求，优先使用摘要压缩
            if self.summary_compressor:
                result = self.summary_compressor.compress(messages)
                result.metadata["hybrid_strategy"] = "summary_primary"
                return result
            else:
                # 没有LLM引擎，使用关键信息提取
                result = self.key_extraction_compressor.compress(messages)
                result.metadata["hybrid_strategy"] = "key_extraction_fallback"
                return result
        
        elif len(messages) > self.config.preserve_recent_messages * 2:
            # 中等压缩需求，使用关键信息提取
            key_result = self.key_extraction_compressor.compress(messages)
            
            # 如果关键信息提取效果不好，回退到滑动窗口
            if key_result.compression_ratio > 0.8:
                window_result = self.sliding_window_compressor.compress(messages)
                window_result.metadata["hybrid_strategy"] = "sliding_window_fallback"
                return window_result
            else:
                key_result.metadata["hybrid_strategy"] = "key_extraction_primary"
                return key_result
        
        else:
            # 低压缩需求，使用滑动窗口
            result = self.sliding_window_compressor.compress(messages)
            result.metadata["hybrid_strategy"] = "sliding_window_primary"
            return result
    
    def _select_best_result(self, results: List[CompressionResult]) -> CompressionResult:
        """选择最佳压缩结果"""
        if not results:
            raise ValueError("No compression results to select from")
        
        # 根据压缩比和保留信息质量选择最佳结果
        best_result = results[0]
        best_score = self._calculate_result_score(best_result)
        
        for result in results[1:]:
            score = self._calculate_result_score(result)
            if score > best_score:
                best_result = result
                best_score = score
        
        return best_result
    
    def _calculate_result_score(self, result: CompressionResult) -> float:
        """计算压缩结果的评分"""
        # 压缩比权重（越小越好）
        compression_score = 1.0 - result.compression_ratio
        
        # 保留消息数量权重
        message_score = min(result.compressed_count / self.config.preserve_recent_messages, 1.0)
        
        # 综合评分
        return compression_score * 0.7 + message_score * 0.3