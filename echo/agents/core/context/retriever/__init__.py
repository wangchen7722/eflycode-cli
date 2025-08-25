#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Retriever子包

提供各种上下文检索策略的实现。
"""

from .base import BaseRetriever, RetrievalResult, ContextEntry
from .keyword import KeywordRetriever
from .semantic import SemanticRetriever
from .temporal import TemporalRetriever
from .hybrid import HybridRetriever
from .context_retriever import ContextRetriever, RetrievalStrategy, create_retriever

__all__ = [
    'BaseRetriever',
    'RetrievalResult',
    'ContextEntry',
    'KeywordRetriever',
    'SemanticRetriever',
    'TemporalRetriever',
    'HybridRetriever',
    'ContextRetriever',
    'RetrievalStrategy',
    'create_retriever'
]