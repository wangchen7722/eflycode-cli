#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
混合检索器模块

结合多种检索策略的混合检索器。
"""

import time
from typing import List, Dict, Optional, Callable

from echo.utils.logger import get_logger
from .base import BaseRetriever, RetrievalResult, ContextEntry
from .keyword import KeywordRetriever
from .semantic import SemanticRetriever
from .temporal import TemporalRetriever

logger = get_logger()


class HybridRetriever(BaseRetriever):
    """混合检索器"""
    
    def __init__(self, 
                 max_results: int = 10,
                 embedding_function: Optional[Callable[[str], List[float]]] = None,
                 weights: Optional[Dict[str, float]] = None):
        super().__init__(max_results)
        
        # 初始化子检索器
        self.keyword_retriever = KeywordRetriever(max_results * 2)  # 获取更多候选结果
        self.semantic_retriever = SemanticRetriever(max_results * 2, embedding_function)
        self.temporal_retriever = TemporalRetriever(max_results * 2)
        
        # 设置权重
        self.weights = weights or {
            'keyword': 0.4,
            'semantic': 0.4,
            'temporal': 0.2
        }
        
        # 确保权重总和为1
        total_weight = sum(self.weights.values())
        if total_weight != 1.0:
            for key in self.weights:
                self.weights[key] /= total_weight
    
    def retrieve(self, query: str, **kwargs) -> RetrievalResult:
        """使用混合策略检索"""
        start_time = time.time()
        
        # 同步上下文存储到子检索器
        self._sync_context_stores()
        
        # 获取各种检索策略的结果
        results = {}
        
        # 关键词检索
        if self.weights.get('keyword', 0) > 0:
            try:
                results['keyword'] = self.keyword_retriever.retrieve(query, **kwargs)
            except Exception as e:
                logger.error(f"关键词检索失败: {e}")
                results['keyword'] = None
        
        # 语义检索
        if self.weights.get('semantic', 0) > 0 and self.semantic_retriever.embedding_function:
            try:
                results['semantic'] = self.semantic_retriever.retrieve(query, **kwargs)
            except Exception as e:
                logger.error(f"语义检索失败: {e}")
                results['semantic'] = None
        
        # 时间检索
        if self.weights.get('temporal', 0) > 0:
            try:
                results['temporal'] = self.temporal_retriever.retrieve(query, **kwargs)
            except Exception as e:
                logger.error(f"时间检索失败: {e}")
                results['temporal'] = None
        
        # 合并和重新排序结果
        final_result = self._merge_results(results, query)
        final_result.query_time = time.time() - start_time
        
        return final_result
    
    def _sync_context_stores(self):
        """同步上下文存储到子检索器"""
        self.keyword_retriever.context_store = self.context_store.copy()
        self.semantic_retriever.context_store = self.context_store.copy()
        self.temporal_retriever.context_store = self.context_store.copy()
    
    def _merge_results(self, results: Dict[str, Optional[RetrievalResult]], query: str) -> RetrievalResult:
        """合并多个检索结果"""
        # 收集所有消息和分数
        message_scores = {}  # message_id -> {scores: {strategy: score}, entry: ContextEntry}
        
        for strategy, result in results.items():
            if result is None or not result.messages:
                continue
            
            weight = self.weights.get(strategy, 0)
            if weight == 0:
                continue
            
            for message, score in zip(result.messages, result.scores):
                # 使用消息内容作为唯一标识
                message_id = self._get_message_id(message)
                
                if message_id not in message_scores:
                    message_scores[message_id] = {
                        'scores': {},
                        'message': message,
                        'entry': self._find_entry_by_message(message)
                    }
                
                message_scores[message_id]['scores'][strategy] = score * weight
        
        # 计算综合分数
        final_scores = []
        for message_id, data in message_scores.items():
            # 综合分数 = 各策略加权分数之和
            total_score = sum(data['scores'].values())
            
            # 考虑条目重要性
            if data['entry']:
                total_score *= data['entry'].importance
            
            final_scores.append((data['message'], total_score, data['entry']))
        
        # 按分数排序
        final_scores.sort(key=lambda x: x[1], reverse=True)
        
        # 限制结果数量
        top_results = final_scores[:self.max_results]
        
        messages = [item[0] for item in top_results]
        scores = [item[1] for item in top_results]
        
        # 计算元数据
        strategy_counts = {}
        for strategy, result in results.items():
            if result:
                strategy_counts[f"{strategy}_found"] = result.total_found
        
        return RetrievalResult(
            messages=messages,
            scores=scores,
            total_found=len(message_scores),
            query_time=0,  # 将在调用方设置
            metadata={
                "strategy": "hybrid",
                "weights": self.weights,
                "strategy_results": strategy_counts,
                "avg_score": sum(scores) / len(scores) if scores else 0
            }
        )
    
    def _get_message_id(self, message) -> str:
        """获取消息的唯一标识"""
        content = message.get('content', '')
        role = message.get('role', '')
        return f"{role}:{hash(content)}"
    
    def _find_entry_by_message(self, message) -> Optional[ContextEntry]:
        """根据消息查找对应的上下文条目"""
        for entry in self.context_store:
            if (entry.message.get('content') == message.get('content') and
                entry.message.get('role') == message.get('role')):
                return entry
        return None
    
    def set_weights(self, weights: Dict[str, float]):
        """设置检索策略权重"""
        # 确保权重总和为1
        total_weight = sum(weights.values())
        if total_weight > 0:
            self.weights = {k: v / total_weight for k, v in weights.items()}
        else:
            logger.warning("权重总和为0，保持原有权重")
    
    def set_embedding_function(self, embedding_function: Callable[[str], List[float]]):
        """设置嵌入函数"""
        self.semantic_retriever.set_embedding_function(embedding_function)
    
    def add_context(self, message, importance: float = 1.0, tags: List[str] = None):
        """添加上下文（重写以同步到子检索器）"""
        super().add_context(message, importance, tags)
        # 同步到子检索器
        self._sync_context_stores()
    
    def clear_context(self):
        """清空上下文存储（重写以同步到子检索器）"""
        super().clear_context()
        self.keyword_retriever.clear_context()
        self.semantic_retriever.clear_context()
        self.temporal_retriever.clear_context()