#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语义检索器模块

基于语义相似度的检索策略。
"""

import time
import numpy as np
from typing import List, Optional, Callable

from echo.utils.logger import get_logger
from .base import BaseRetriever, RetrievalResult, ContextEntry

logger = get_logger()


class SemanticRetriever(BaseRetriever):
    """语义检索器"""
    
    def __init__(self, 
                 max_results: int = 10,
                 embedding_function: Optional[Callable[[str], List[float]]] = None,
                 similarity_threshold: float = 0.5):
        super().__init__(max_results)
        self.embedding_function = embedding_function
        self.similarity_threshold = similarity_threshold
        self.embeddings_cache = {}  # 缓存嵌入向量
    
    def retrieve(self, query: str, **kwargs) -> RetrievalResult:
        """基于语义相似度检索"""
        start_time = time.time()
        
        if not self.embedding_function:
            logger.warning("未提供嵌入函数，无法进行语义检索")
            return RetrievalResult(
                messages=[],
                scores=[],
                total_found=0,
                query_time=time.time() - start_time,
                metadata={"strategy": "semantic", "error": "no_embedding_function"}
            )
        
        try:
            # 获取查询的嵌入向量
            query_embedding = self._get_embedding(query)
            if query_embedding is None:
                return RetrievalResult(
                    messages=[],
                    scores=[],
                    total_found=0,
                    query_time=time.time() - start_time,
                    metadata={"strategy": "semantic", "error": "query_embedding_failed"}
                )
            
            # 计算每个上下文条目的相似度分数
            scored_entries = []
            for i, entry in enumerate(self.context_store):
                content = entry.message.get('content', '')
                if not content:
                    continue
                
                # 获取内容的嵌入向量
                content_embedding = self._get_embedding(content, cache_key=f"entry_{i}")
                if content_embedding is None:
                    continue
                
                # 计算余弦相似度
                similarity = self._cosine_similarity(query_embedding, content_embedding)
                
                # 应用相似度阈值
                if similarity >= self.similarity_threshold:
                    # 考虑条目重要性
                    final_score = similarity * entry.importance
                    scored_entries.append((entry, final_score))
            
            # 按分数排序并限制结果数量
            scored_entries.sort(key=lambda x: x[1], reverse=True)
            top_entries = scored_entries[:self.max_results]
            
            messages = [entry.message for entry, _ in top_entries]
            scores = [score for _, score in top_entries]
            
            return RetrievalResult(
                messages=messages,
                scores=scores,
                total_found=len(scored_entries),
                query_time=time.time() - start_time,
                metadata={
                    "strategy": "semantic",
                    "similarity_threshold": self.similarity_threshold,
                    "avg_score": sum(scores) / len(scores) if scores else 0
                }
            )
        
        except Exception as e:
            logger.error(f"语义检索失败: {e}")
            return RetrievalResult(
                messages=[],
                scores=[],
                total_found=0,
                query_time=time.time() - start_time,
                metadata={"strategy": "semantic", "error": str(e)}
            )
    
    def _get_embedding(self, text: str, cache_key: Optional[str] = None) -> Optional[List[float]]:
        """获取文本的嵌入向量"""
        # 检查缓存
        if cache_key and cache_key in self.embeddings_cache:
            return self.embeddings_cache[cache_key]
        
        try:
            embedding = self.embedding_function(text)
            
            # 缓存结果
            if cache_key:
                self.embeddings_cache[cache_key] = embedding
            
            return embedding
        
        except Exception as e:
            logger.error(f"获取嵌入向量失败: {e}")
            return None
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        try:
            # 转换为numpy数组
            a = np.array(vec1)
            b = np.array(vec2)
            
            # 计算余弦相似度
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            
            if norm_a == 0 or norm_b == 0:
                return 0.0
            
            similarity = dot_product / (norm_a * norm_b)
            return float(similarity)
        
        except Exception as e:
            logger.error(f"计算余弦相似度失败: {e}")
            return 0.0
    
    def set_embedding_function(self, embedding_function: Callable[[str], List[float]]):
        """设置嵌入函数"""
        self.embedding_function = embedding_function
        # 清空缓存，因为嵌入函数可能已改变
        self.embeddings_cache.clear()
    
    def clear_embeddings_cache(self):
        """清空嵌入向量缓存"""
        self.embeddings_cache.clear()
    
    def precompute_embeddings(self):
        """预计算所有上下文条目的嵌入向量"""
        if not self.embedding_function:
            logger.warning("未提供嵌入函数，无法预计算嵌入向量")
            return
        
        for i, entry in enumerate(self.context_store):
            content = entry.message.get('content', '')
            if content:
                self._get_embedding(content, cache_key=f"entry_{i}")
        
        logger.info(f"已预计算 {len(self.embeddings_cache)} 个嵌入向量")