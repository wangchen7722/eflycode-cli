#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
滑动窗口压缩器模块

基于滑动窗口的压缩策略，保留最近的消息。
"""

from typing import List

from echo.llms.schema import Message
from echo.agents.core.token_calculator import TokenCalculator
from echo.config import CompressionConfig
from .base import BaseCompressor, CompressionResult


class SlidingWindowCompressor(BaseCompressor):
    """滑动窗口压缩器"""
    
    def __init__(self, config: CompressionConfig, token_calculator: TokenCalculator, token_ratio: float = 0.8, max_context_length: int = None):
        super().__init__(config, token_calculator)
        self.token_ratio = token_ratio
        self.max_context_length = max_context_length or config.max_context_length
    
    def compress(self, messages: List[Message]) -> CompressionResult:
        """使用基于token的滑动窗口策略压缩"""
        original_tokens = self._calculate_messages_tokens(messages)
        
        # 计算目标token数量
        target_tokens = int(self.max_context_length * self.token_ratio)
        
        # 如果当前token数量在目标范围内，不需要压缩
        if original_tokens <= target_tokens:
            return CompressionResult(
                compressed_messages=messages,
                original_count=len(messages),
                compressed_count=len(messages),
                compression_ratio=1.0,
                preserved_tokens=original_tokens,
                metadata={"strategy": "sliding_window", "reason": "within_token_limit"}
            )
        
        # 从最新消息开始，逐步添加直到接近token限制
        compressed_messages = []
        current_tokens = 0
        
        # 从后往前遍历消息，确保保留最新的消息
        for message in reversed(messages):
            message_tokens = self._calculate_messages_tokens([message])
            
            # 如果添加这条消息会超过目标token数，停止添加
            if current_tokens + message_tokens > target_tokens:
                # 但至少要保留一条消息
                if not compressed_messages:
                    compressed_messages.append(message)
                    current_tokens += message_tokens
                break
            
            compressed_messages.append(message)
            current_tokens += message_tokens
        
        # 恢复消息的原始顺序
        compressed_messages.reverse()
        
        compressed_tokens = self._calculate_messages_tokens(compressed_messages)
        
        return CompressionResult(
            compressed_messages=compressed_messages,
            original_count=len(messages),
            compressed_count=len(compressed_messages),
            compression_ratio=compressed_tokens / original_tokens if original_tokens > 0 else 1.0,
            preserved_tokens=compressed_tokens,
            metadata={
                "strategy": "sliding_window",
                "target_tokens": target_tokens,
                "token_utilization": compressed_tokens / self.max_context_length,
                "dropped_message_count": len(messages) - len(compressed_messages)
            }
        )