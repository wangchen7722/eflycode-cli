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
    
    def compress(self, messages: List[Message]) -> CompressionResult:
        """使用滑动窗口策略压缩"""
        if len(messages) <= self.config.preserve_recent_messages:
            return CompressionResult(
                compressed_messages=messages,
                original_count=len(messages),
                compressed_count=len(messages),
                compression_ratio=1.0,
                preserved_tokens=self._calculate_messages_tokens(messages),
                metadata={"strategy": "sliding_window", "reason": "within_window"}
            )
        
        # 保留最近的消息
        compressed_messages = messages[-self.config.preserve_recent_messages:]
        
        original_tokens = self._calculate_messages_tokens(messages)
        compressed_tokens = self._calculate_messages_tokens(compressed_messages)
        
        return CompressionResult(
            compressed_messages=compressed_messages,
            original_count=len(messages),
            compressed_count=len(compressed_messages),
            compression_ratio=compressed_tokens / original_tokens if original_tokens > 0 else 1.0,
            preserved_tokens=compressed_tokens,
            metadata={
                "strategy": "sliding_window",
                "window_size": self.config.preserve_recent_messages,
                "dropped_messages": len(messages) - len(compressed_messages)
            }
        )