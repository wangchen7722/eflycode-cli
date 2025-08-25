#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
摘要压缩器模块

基于LLM生成摘要的压缩策略。
"""

from typing import List

from echo.llms.schema import Message
from echo.llms.llm_engine import LLMEngine
from echo.agents.core.token_calculator import TokenCalculator
from echo.config import CompressionConfig
from echo.utils.logger import get_logger
from .base import BaseCompressor, CompressionResult

logger = get_logger()


class SummaryCompressor(BaseCompressor):
    """基于摘要的压缩器"""
    
    def __init__(self, config: CompressionConfig, token_calculator: TokenCalculator, llm_engine: LLMEngine):
        super().__init__(config, token_calculator)
        self.llm_engine = llm_engine
    
    def compress(self, messages: List[Message]) -> CompressionResult:
        """使用LLM生成摘要进行压缩"""
        if len(messages) < self.config.min_messages_to_compress:
            return CompressionResult(
                compressed_messages=messages,
                original_count=len(messages),
                compressed_count=len(messages),
                compression_ratio=1.0,
                preserved_tokens=self._calculate_messages_tokens(messages),
                metadata={"strategy": "no_compression", "reason": "insufficient_messages"}
            )
        
        # 保留最近的消息
        recent_messages = messages[-self.config.preserve_recent_messages:]
        messages_to_compress = messages[:-self.config.preserve_recent_messages]
        
        if not messages_to_compress:
            return CompressionResult(
                compressed_messages=messages,
                original_count=len(messages),
                compressed_count=len(messages),
                compression_ratio=1.0,
                preserved_tokens=self._calculate_messages_tokens(messages),
                metadata={"strategy": "no_compression", "reason": "all_recent"}
            )
        
        # 生成摘要
        summary = self._generate_summary(messages_to_compress)
        
        # 构建压缩后的消息列表
        compressed_messages = [
            {"role": "system", "content": f"对话历史摘要：{summary}"}
        ] + recent_messages
        
        original_tokens = self._calculate_messages_tokens(messages)
        compressed_tokens = self._calculate_messages_tokens(compressed_messages)
        
        return CompressionResult(
            compressed_messages=compressed_messages,
            original_count=len(messages),
            compressed_count=len(compressed_messages),
            compression_ratio=compressed_tokens / original_tokens if original_tokens > 0 else 1.0,
            preserved_tokens=compressed_tokens,
            metadata={
                "strategy": "summary",
                "summary_length": len(summary),
                "compressed_messages_count": len(messages_to_compress)
            }
        )
    
    def _generate_summary(self, messages: List[Message]) -> str:
        """生成对话摘要"""
        # 构建摘要提示
        conversation_text = "\n".join([
            f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
            for msg in messages
            if msg.get('content')
        ])
        
        summary_prompt = f"""
请对以下对话历史进行简洁的摘要，保留关键信息和上下文：

{conversation_text}

要求：
1. 摘要长度不超过{self.config.summary_max_tokens}个token
2. 保留重要的决策、结论和关键信息
3. 保持时间顺序和逻辑关系
4. 使用简洁明了的语言

摘要：
"""
        
        try:
            response = self.llm_engine.generate(
                messages=[{"role": "user", "content": summary_prompt}],
                stream=False,
                max_tokens=self.config.summary_max_tokens
            )
            return response["choices"][0]["message"].get("content", "摘要生成失败")
        except Exception as e:
            logger.error(f"摘要生成失败: {e}")
            return "对话历史摘要（生成失败，保留原始信息）"