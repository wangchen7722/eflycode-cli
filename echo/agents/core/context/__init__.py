#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上下文管理包

提供上下文压缩和检索功能，包括：
- 上下文压缩器（摘要、滑动窗口、关键信息提取、混合）
- 上下文检索器（关键词、语义、时间、混合）
"""

# 压缩器
from .compressor import (
    BaseCompressor,
    CompressionResult,
    SummaryCompressor,
    SlidingWindowCompressor,
    KeyExtractionCompressor,
    HybridCompressor,
    create_compressor
)

# 检索器
from .retriever import (
    BaseRetriever,
    RetrievalResult,
    ContextEntry,
    KeywordRetriever,
    SemanticRetriever,
    TemporalRetriever,
    HybridRetriever,
    RetrievalStrategy,
    create_retriever,
    ContextRetriever
)

__all__ = [
    # 压缩器
    "BaseCompressor",
    "CompressionResult",
    "SummaryCompressor",
    "SlidingWindowCompressor",
    "KeyExtractionCompressor",
    "HybridCompressor",
    "create_compressor",
    
    # 检索器
    "BaseRetriever",
    "RetrievalResult",
    "ContextEntry",
    "KeywordRetriever",
    "SemanticRetriever",
    "TemporalRetriever",
    "HybridRetriever",
    "RetrievalStrategy",
    "create_retriever",
    "ContextRetriever",
]