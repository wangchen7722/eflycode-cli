#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上下文检索器模块

提供上下文检索的主要接口和工厂函数。
"""

from typing import Optional, Callable, List, Dict
from enum import Enum

from echo.utils.logger import get_logger
from .base import BaseRetriever
from .keyword import KeywordRetriever
from .semantic import SemanticRetriever
from .temporal import TemporalRetriever
from .hybrid import HybridRetriever

logger = get_logger()


class RetrievalStrategy(Enum):
    """检索策略枚举"""
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    TEMPORAL = "temporal"
    HYBRID = "hybrid"


def create_retriever(
    strategy: RetrievalStrategy,
    max_results: int = 10,
    embedding_function: Optional[Callable[[str], List[float]]] = None,
    **kwargs
) -> BaseRetriever:
    """创建检索器实例
    
    Args:
        strategy: 检索策略
        max_results: 最大结果数量
        embedding_function: 嵌入函数（语义检索需要）
        **kwargs: 其他参数
    
    Returns:
        BaseRetriever: 检索器实例
    
    Raises:
        ValueError: 当策略无效或缺少必要参数时
    """
    if strategy == RetrievalStrategy.KEYWORD:
        case_sensitive = kwargs.get('case_sensitive', False)
        return KeywordRetriever(max_results, case_sensitive)
    
    elif strategy == RetrievalStrategy.SEMANTIC:
        similarity_threshold = kwargs.get('similarity_threshold', 0.5)
        return SemanticRetriever(max_results, embedding_function, similarity_threshold)
    
    elif strategy == RetrievalStrategy.TEMPORAL:
        return TemporalRetriever(max_results)
    
    elif strategy == RetrievalStrategy.HYBRID:
        weights = kwargs.get('weights')
        return HybridRetriever(max_results, embedding_function, weights)
    
    else:
        raise ValueError(f"不支持的检索策略: {strategy}")


class ContextRetriever:
    """上下文检索器主类"""
    
    def __init__(self, 
                 strategy: RetrievalStrategy = RetrievalStrategy.HYBRID,
                 max_results: int = 10,
                 embedding_function: Optional[Callable[[str], List[float]]] = None,
                 **kwargs):
        self.strategy = strategy
        self.retriever = create_retriever(strategy, max_results, embedding_function, **kwargs)
    
    def retrieve(self, query: str, **kwargs):
        """检索相关上下文"""
        return self.retriever.retrieve(query, **kwargs)
    
    def add_context(self, message, importance: float = 1.0, tags: List[str] = None):
        """添加上下文"""
        self.retriever.add_context(message, importance, tags)
    
    def clear_context(self):
        """清空上下文"""
        self.retriever.clear_context()
    
    def get_context_count(self) -> int:
        """获取上下文数量"""
        return self.retriever.get_context_count()
    
    def switch_strategy(self, 
                       strategy: RetrievalStrategy,
                       embedding_function: Optional[Callable[[str], List[float]]] = None,
                       **kwargs):
        """切换检索策略"""
        # 保存当前上下文
        current_context = self.retriever.context_store.copy()
        
        # 创建新的检索器
        max_results = self.retriever.max_results
        self.strategy = strategy
        self.retriever = create_retriever(strategy, max_results, embedding_function, **kwargs)
        
        # 恢复上下文
        self.retriever.context_store = current_context
    
    def set_embedding_function(self, embedding_function: Callable[[str], List[float]]):
        """设置嵌入函数"""
        if hasattr(self.retriever, 'set_embedding_function'):
            self.retriever.set_embedding_function(embedding_function)
        else:
            logger.warning(f"当前检索策略 {self.strategy} 不支持设置嵌入函数")
    
    def get_strategy_info(self) -> Dict:
        """获取当前策略信息"""
        info = {
            "strategy": self.strategy.value,
            "max_results": self.retriever.max_results,
            "context_count": self.get_context_count()
        }
        
        # 添加策略特定信息
        if isinstance(self.retriever, SemanticRetriever):
            info["has_embedding_function"] = self.retriever.embedding_function is not None
            info["similarity_threshold"] = self.retriever.similarity_threshold
            info["embeddings_cached"] = len(self.retriever.embeddings_cache)
        
        elif isinstance(self.retriever, KeywordRetriever):
            info["case_sensitive"] = self.retriever.case_sensitive
            info["stop_words_count"] = len(self.retriever.stop_words)
        
        elif isinstance(self.retriever, HybridRetriever):
            info["weights"] = self.retriever.weights
            info["has_embedding_function"] = self.retriever.semantic_retriever.embedding_function is not None
        
        return info


# 导出主要类和函数
__all__ = [
    'BaseRetriever',
    'RetrievalResult',
    'ContextEntry',
    'RetrievalStrategy',
    'KeywordRetriever',
    'SemanticRetriever',
    'TemporalRetriever',
    'HybridRetriever',
    'ContextRetriever',
    'create_retriever'
]