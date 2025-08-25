#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上下文压缩器模块

提供上下文压缩的主要接口和工厂函数。
"""

from typing import Optional

from echo.llms.llm_engine import LLMEngine
from echo.agents.core.token_calculator import TokenCalculator
from echo.config import CompressionConfig, CompressionStrategy
from echo.utils.logger import get_logger
from .base import BaseCompressor
from .summary import SummaryCompressor
from .sliding_window import SlidingWindowCompressor
from .key_extraction import KeyExtractionCompressor
from .hybrid import HybridCompressor

logger = get_logger()


def create_compressor(
    config: CompressionConfig,
    token_calculator: TokenCalculator,
    llm_engine: Optional[LLMEngine] = None
) -> BaseCompressor:
    """创建压缩器实例
    
    Args:
        config: 压缩配置
        token_calculator: Token计算器
        llm_engine: LLM引擎（可选，某些压缩策略需要）
    
    Returns:
        BaseCompressor: 压缩器实例
    
    Raises:
        ValueError: 当配置无效或缺少必要依赖时
    """
    if config.strategy == CompressionStrategy.SUMMARY:
        if not llm_engine:
            logger.warning("摘要压缩策略需要LLM引擎，回退到关键信息提取策略")
            return KeyExtractionCompressor(config, token_calculator)
        return SummaryCompressor(config, token_calculator, llm_engine)
    
    elif config.strategy == CompressionStrategy.SLIDING_WINDOW:
        return SlidingWindowCompressor(config, token_calculator)
    
    elif config.strategy == CompressionStrategy.KEY_EXTRACTION:
        return KeyExtractionCompressor(config, token_calculator)
    
    elif config.strategy == CompressionStrategy.HYBRID:
        return HybridCompressor(config, token_calculator, llm_engine)
    
    else:
        raise ValueError(f"不支持的压缩策略: {config.strategy}")


# 导出主要类和函数
__all__ = [
    'BaseCompressor',
    'CompressionResult',
    'SummaryCompressor',
    'SlidingWindowCompressor', 
    'KeyExtractionCompressor',
    'HybridCompressor',
    'create_compressor'
]