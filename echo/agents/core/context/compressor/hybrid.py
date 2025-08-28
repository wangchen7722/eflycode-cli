#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
混合压缩器模块

结合多种压缩策略的混合压缩器，现在基于CompressorChain实现。
"""

from typing import List, Optional

from echo.llms.schema import Message
from echo.llms.llm_engine import LLMEngine
from echo.agents.core.token_calculator import TokenCalculator
from echo.config import CompressionConfig
from echo.utils.logger import get_logger
from .base import BaseCompressor, CompressionResult
from .chain import CompressorChain, CompressorChainConfig, CompressorType

logger = get_logger()


class HybridCompressor(BaseCompressor):
    """混合压缩器
    
    基于CompressorChain实现的混合压缩器，保持向后兼容性。
    """
    
    def __init__(self, config: CompressionConfig, token_calculator: TokenCalculator, llm_engine: Optional[LLMEngine] = None):
        super().__init__(config, token_calculator)
        self.llm_engine = llm_engine
        
        # 创建默认的压缩器链配置
        compressor_types = []
        if llm_engine:
            compressor_types.append(CompressorType.SUMMARY)
        compressor_types.extend([CompressorType.KEY_EXTRACTION, CompressorType.SLIDING_WINDOW])
        
        chain_config = CompressorChainConfig(
            compressor_types=compressor_types,
            selection_strategy="best_score"
        )
        
        # 使用压缩器链实现
        self.compressor_chain = CompressorChain(config, token_calculator, chain_config, llm_engine)
    
    def compress(self, messages: List[Message]) -> CompressionResult:
        """使用混合策略进行压缩"""
        result = self.compressor_chain.compress(messages)
        # 保持向后兼容，添加hybrid标识
        result.metadata["strategy"] = "hybrid"
        result.metadata["implementation"] = "chain_based"
        return result
    
    def get_compressor_info(self):
        """获取压缩器信息，用于调试和监控"""
        return self.compressor_chain.get_compressor_info()