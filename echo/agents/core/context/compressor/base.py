#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
压缩器基础类模块

定义压缩器的基础接口和数据结构。
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any

from pydantic import BaseModel, Field

from echo.llms.schema import Message
from echo.agents.core.token_calculator import TokenCalculator
from echo.config import CompressionConfig


class CompressionResult(BaseModel):
    """压缩结果

    压缩器对消息列表进行压缩后的结果数据结构，包含:
    - 压缩后的消息列表
    - 原始消息数量
    - 压缩后消息数量
    - 压缩比率
    - 保留的token数量
    - 元数据信息
    """
    compressed_messages: List[Message] = Field(description="压缩后的消息列表")
    """压缩后得到的消息列表，包含所有经过压缩处理的消息"""

    original_count: int = Field(description="原始消息数量")
    """压缩前原始消息列表中的消息数量"""

    compressed_count: int = Field(description="压缩后的消息数量")
    """压缩后消息列表中的消息数量"""

    compression_ratio: float = Field(description="压缩比率，compressed_tokens / original_tokens")
    """压缩比率，用压缩后的token数除以原始token数得到的比值"""

    preserved_tokens: int = Field(description="保留的token数量")
    """压缩后保留下来的token总数"""

    metadata: Dict[str, Any] = Field(description="压缩相关的元数据信息，如压缩策略、原因等")
    """压缩过程的元数据信息，包括使用的压缩策略、压缩原因等附加信息"""


class BaseCompressor(ABC):
    """压缩器基类"""
    
    def __init__(self, config: CompressionConfig, token_calculator: TokenCalculator):
        self.config = config
        self.token_calculator = token_calculator
    
    @abstractmethod
    def compress(self, messages: List[Message]) -> CompressionResult:
        """压缩消息列表"""
        pass
    
    def _estimate_tokens(self, text: str) -> int:
        """估算文本token数量（保持向后兼容）"""
        return self.token_calculator.calculate_tokens(text)
    
    def _calculate_messages_tokens(self, messages: List[Message]) -> int:
        """计算消息列表的总token数"""
        return self.token_calculator.calculate_messages_tokens(messages)