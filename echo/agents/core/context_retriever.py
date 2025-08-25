#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上下文检索器模块

提供智能的上下文检索功能，包括：
- 对话历史检索
- 语义相似度搜索
- 关键词匹配
- 时间窗口过滤
- 多模态内容检索
"""

import json
import re
import math
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict, Counter

from echo.llms.schema import Message
from echo.llms.llm_engine import LLMEngine
from echo.utils.logger import get_logger
from echo.config import RetrievalStrategy, RetrievalConfig

logger = get_logger()





@dataclass
class RetrievalResult:
    """检索结果"""
    message: Message
    score: float
    relevance_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[datetime] = None


@dataclass
class RetrievalResponse:
    """检索响应"""
    results: List[RetrievalResult]
    total_searched: int
    query_analysis: Dict[str, Any]
    execution_time: float
    strategy_used: str


class BaseRetriever(ABC):
    """检索器基类"""
    
    def __init__(self, config: RetrievalConfig):
        self.config = config
    
    @abstractmethod
    def retrieve(self, query: str, messages: List[Message], **kwargs) -> List[RetrievalResult]:
        """检索相关消息"""
        pass
    
    def _extract_keywords(self, text: str) -> Set[str]:
        """提取关键词"""
        # 移除标点符号和特殊字符
        cleaned_text = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text.lower())
        words = cleaned_text.split()
        
        # 过滤停用词（简化版本）
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            '是', '的', '了', '在', '有', '和', '与', '或', '但', '这', '那', '一个', '一些', '什么', '怎么'
        }
        
        keywords = {word for word in words if len(word) > 2 and word not in stop_words}
        return keywords
    
    def _calculate_keyword_similarity(self, query_keywords: Set[str], content_keywords: Set[str]) -> float:
        """计算关键词相似度"""
        if not query_keywords or not content_keywords:
            return 0.0
        
        intersection = query_keywords.intersection(content_keywords)
        union = query_keywords.union(content_keywords)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _calculate_temporal_score(self, message_time: Optional[datetime], current_time: datetime) -> float:
        """计算时间相关性评分"""
        if not message_time:
            return 0.5  # 默认中等时间相关性
        
        time_diff = abs((current_time - message_time).total_seconds())
        max_time_diff = self.config.time_window_hours * 3600
        
        if time_diff > max_time_diff:
            return 0.0
        
        # 时间越近，评分越高
        return 1.0 - (time_diff / max_time_diff)


class KeywordRetriever(BaseRetriever):
    """关键词检索器"""
    
    def retrieve(self, query: str, messages: List[Message], **kwargs) -> List[RetrievalResult]:
        """基于关键词匹配检索"""
        query_keywords = self._extract_keywords(query)
        results = []
        
        for i, message in enumerate(messages):
            content = message.get('content', '')
            if not isinstance(content, str) or len(content) < self.config.min_content_length:
                continue
            
            content_keywords = self._extract_keywords(content)
            similarity = self._calculate_keyword_similarity(query_keywords, content_keywords)
            
            if similarity >= self.config.similarity_threshold:
                result = RetrievalResult(
                    message=message,
                    score=similarity,
                    relevance_type="keyword",
                    metadata={
                        "matched_keywords": list(query_keywords.intersection(content_keywords)),
                        "total_keywords": len(content_keywords),
                        "message_index": i
                    }
                )
                results.append(result)
        
        # 按相似度排序
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:self.config.max_results]


class SemanticRetriever(BaseRetriever):
    """语义检索器（简化版本，实际应用中需要使用embedding模型）"""
    
    def __init__(self, config: RetrievalConfig, llm_engine: Optional[LLMEngine] = None):
        super().__init__(config)
        self.llm_engine = llm_engine
    
    def retrieve(self, query: str, messages: List[Message], **kwargs) -> List[RetrievalResult]:
        """基于语义相似度检索"""
        if not self.llm_engine:
            logger.warning("语义检索需要LLM引擎，回退到关键词检索")
            keyword_retriever = KeywordRetriever(self.config)
            return keyword_retriever.retrieve(query, messages, **kwargs)
        
        results = []
        
        for i, message in enumerate(messages):
            content = message.get('content', '')
            if not isinstance(content, str) or len(content) < self.config.min_content_length:
                continue
            
            # 使用LLM计算语义相似度（简化实现）
            similarity = self._calculate_semantic_similarity(query, content)
            
            if similarity >= self.config.similarity_threshold:
                result = RetrievalResult(
                    message=message,
                    score=similarity,
                    relevance_type="semantic",
                    metadata={
                        "content_length": len(content),
                        "message_index": i,
                        "similarity_method": "llm_based"
                    }
                )
                results.append(result)
        
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:self.config.max_results]
    
    def _calculate_semantic_similarity(self, query: str, content: str) -> float:
        """计算语义相似度（简化实现）"""
        try:
            # 构建相似度判断提示
            similarity_prompt = f"""
请评估以下查询和内容的语义相似度，返回0-1之间的数值：

查询：{query}
内容：{content}

评分标准：
- 1.0: 完全相关，内容直接回答查询
- 0.8: 高度相关，内容与查询主题一致
- 0.6: 中等相关，内容部分涉及查询主题
- 0.4: 低度相关，内容略微涉及查询主题
- 0.2: 微弱相关，内容与查询有间接联系
- 0.0: 无关，内容与查询无关

请只返回数值，不要其他解释：
"""
            
            response = self.llm_engine.generate(
                messages=[{"role": "user", "content": similarity_prompt}],
                stream=False,
                max_tokens=10
            )
            
            result_text = response["choices"][0]["message"].get("content", "0.0")
            # 提取数值
            import re
            match = re.search(r'\d+\.?\d*', result_text)
            if match:
                score = float(match.group())
                return min(1.0, max(0.0, score))
            
        except Exception as e:
            logger.error(f"语义相似度计算失败: {e}")
        
        # 回退到简单的文本相似度
        return self._simple_text_similarity(query, content)
    
    def _simple_text_similarity(self, query: str, content: str) -> float:
        """简单文本相似度计算"""
        query_words = set(self._extract_keywords(query))
        content_words = set(self._extract_keywords(content))
        
        if not query_words or not content_words:
            return 0.0
        
        intersection = query_words.intersection(content_words)
        union = query_words.union(content_words)
        
        jaccard_similarity = len(intersection) / len(union) if union else 0.0
        
        # 考虑内容长度的影响
        length_factor = min(1.0, len(content) / (len(query) * 2))
        
        return jaccard_similarity * length_factor


class TemporalRetriever(BaseRetriever):
    """时间相关检索器"""
    
    def retrieve(self, query: str, messages: List[Message], **kwargs) -> List[RetrievalResult]:
        """基于时间相关性检索"""
        current_time = kwargs.get('current_time', datetime.now())
        results = []
        
        for i, message in enumerate(messages):
            content = message.get('content', '')
            if not isinstance(content, str) or len(content) < self.config.min_content_length:
                continue
            
            # 尝试从消息中提取时间戳
            message_time = self._extract_message_timestamp(message)
            temporal_score = self._calculate_temporal_score(message_time, current_time)
            
            if temporal_score > 0:
                # 结合关键词匹配
                query_keywords = self._extract_keywords(query)
                content_keywords = self._extract_keywords(content)
                keyword_score = self._calculate_keyword_similarity(query_keywords, content_keywords)
                
                # 综合评分
                combined_score = temporal_score * 0.6 + keyword_score * 0.4
                
                if combined_score >= self.config.similarity_threshold:
                    result = RetrievalResult(
                        message=message,
                        score=combined_score,
                        relevance_type="temporal",
                        metadata={
                            "temporal_score": temporal_score,
                            "keyword_score": keyword_score,
                            "message_time": message_time.isoformat() if message_time else None,
                            "message_index": i
                        },
                        timestamp=message_time
                    )
                    results.append(result)
        
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:self.config.max_results]
    
    def _extract_message_timestamp(self, message: Message) -> Optional[datetime]:
        """提取消息时间戳"""
        # 尝试从消息元数据中获取时间戳
        if 'timestamp' in message:
            try:
                if isinstance(message['timestamp'], datetime):
                    return message['timestamp']
                elif isinstance(message['timestamp'], str):
                    return datetime.fromisoformat(message['timestamp'])
                elif isinstance(message['timestamp'], (int, float)):
                    return datetime.fromtimestamp(message['timestamp'])
            except Exception:
                pass
        
        # 尝试从内容中提取时间信息
        content = message.get('content', '')
        time_patterns = [
            r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})',
            r'(\d{2}:\d{2}:\d{2})',
            r'(\d{4}-\d{2}-\d{2})'
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, content)
            if match:
                try:
                    time_str = match.group(1)
                    if len(time_str) == 8:  # HH:MM:SS
                        today = datetime.now().date()
                        time_obj = datetime.strptime(time_str, '%H:%M:%S').time()
                        return datetime.combine(today, time_obj)
                    elif len(time_str) == 10:  # YYYY-MM-DD
                        return datetime.strptime(time_str, '%Y-%m-%d')
                    else:  # YYYY-MM-DD HH:MM:SS
                        return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                except Exception:
                    continue
        
        return None


class HybridRetriever(BaseRetriever):
    """混合检索器"""
    
    def __init__(self, config: RetrievalConfig, llm_engine: Optional[LLMEngine] = None):
        super().__init__(config)
        self.keyword_retriever = KeywordRetriever(config)
        self.semantic_retriever = SemanticRetriever(config, llm_engine)
        self.temporal_retriever = TemporalRetriever(config)
    
    def retrieve(self, query: str, messages: List[Message], **kwargs) -> List[RetrievalResult]:
        """使用混合策略检索"""
        # 获取各种检索结果
        keyword_results = self.keyword_retriever.retrieve(query, messages, **kwargs)
        semantic_results = self.semantic_retriever.retrieve(query, messages, **kwargs)
        temporal_results = self.temporal_retriever.retrieve(query, messages, **kwargs)
        
        # 合并结果并重新评分
        combined_results = self._combine_results(
            keyword_results, semantic_results, temporal_results
        )
        
        # 去重并排序
        unique_results = self._deduplicate_results(combined_results)
        unique_results.sort(key=lambda x: x.score, reverse=True)
        
        return unique_results[:self.config.max_results]
    
    def _combine_results(self, *result_lists) -> List[RetrievalResult]:
        """合并多个检索结果列表"""
        # 使用消息索引作为键来合并结果
        message_scores = defaultdict(list)
        message_results = {}
        
        for results in result_lists:
            for result in results:
                msg_index = result.metadata.get('message_index', -1)
                if msg_index >= 0:
                    message_scores[msg_index].append(result.score)
                    if msg_index not in message_results:
                        message_results[msg_index] = result
        
        # 计算综合评分
        combined_results = []
        for msg_index, scores in message_scores.items():
            if msg_index in message_results:
                result = message_results[msg_index]
                
                # 加权平均评分
                weights = [self.config.keyword_weight, self.config.semantic_weight, self.config.temporal_weight]
                weighted_score = sum(score * weight for score, weight in zip(scores + [0] * (3 - len(scores)), weights[:len(scores)]))
                weighted_score /= sum(weights[:len(scores)])
                
                result.score = weighted_score
                result.relevance_type = "hybrid"
                result.metadata["component_scores"] = scores
                combined_results.append(result)
        
        return combined_results
    
    def _deduplicate_results(self, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """去除重复结果"""
        seen_indices = set()
        unique_results = []
        
        for result in results:
            msg_index = result.metadata.get('message_index', -1)
            if msg_index not in seen_indices:
                seen_indices.add(msg_index)
                unique_results.append(result)
        
        return unique_results


class ContextRetriever:
    """上下文检索器主类"""
    
    def __init__(self, config: RetrievalConfig, llm_engine: Optional[LLMEngine] = None):
        self.config = config
        self.llm_engine = llm_engine
        self._retriever = self._create_retriever()
    
    def _create_retriever(self) -> BaseRetriever:
        """创建检索器实例"""
        if self.config.strategy == RetrievalStrategy.KEYWORD:
            return KeywordRetriever(self.config)
        elif self.config.strategy == RetrievalStrategy.SEMANTIC:
            return SemanticRetriever(self.config, self.llm_engine)
        elif self.config.strategy == RetrievalStrategy.TEMPORAL:
            return TemporalRetriever(self.config)
        else:  # HYBRID or RELEVANCE
            return HybridRetriever(self.config, self.llm_engine)
    
    def retrieve_context(self, query: str, messages: List[Message], **kwargs) -> RetrievalResponse:
        """检索相关上下文
        
        Args:
            query: 查询字符串
            messages: 消息历史列表
            **kwargs: 额外参数（如current_time等）
            
        Returns:
            RetrievalResponse: 检索响应
        """
        start_time = datetime.now()
        
        try:
            # 分析查询
            query_analysis = self._analyze_query(query)
            
            # 执行检索
            results = self._retriever.retrieve(query, messages, **kwargs)
            
            # 计算执行时间
            execution_time = (datetime.now() - start_time).total_seconds()
            
            response = RetrievalResponse(
                results=results,
                total_searched=len(messages),
                query_analysis=query_analysis,
                execution_time=execution_time,
                strategy_used=self.config.strategy.value
            )
            
            logger.info(
                f"上下文检索完成: 查询='{query[:50]}...', "
                f"搜索={len(messages)}条, 返回={len(results)}条, "
                f"耗时={execution_time:.3f}s, 策略={self.config.strategy.value}"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"上下文检索失败: {e}")
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return RetrievalResponse(
                results=[],
                total_searched=len(messages),
                query_analysis={"error": str(e)},
                execution_time=execution_time,
                strategy_used="error"
            )
    
    def _analyze_query(self, query: str) -> Dict[str, Any]:
        """分析查询内容"""
        keywords = self._retriever._extract_keywords(query)
        
        # 检测查询类型
        query_type = "general"
        if any(word in query.lower() for word in ['when', 'time', '什么时候', '时间']):
            query_type = "temporal"
        elif any(word in query.lower() for word in ['how', 'why', 'what', '如何', '为什么', '什么']):
            query_type = "semantic"
        elif len(keywords) > 3:
            query_type = "keyword_rich"
        
        return {
            "query_length": len(query),
            "keywords": list(keywords),
            "keyword_count": len(keywords),
            "query_type": query_type,
            "language": "chinese" if any('\u4e00' <= char <= '\u9fff' for char in query) else "english"
        }
    
    def update_config(self, config: RetrievalConfig):
        """更新检索配置"""
        self.config = config
        self._retriever = self._create_retriever()
    
    def get_retrieval_stats(self, messages: List[Message]) -> Dict[str, Any]:
        """获取检索统计信息"""
        total_messages = len(messages)
        content_messages = sum(1 for msg in messages if msg.get('content') and len(msg['content']) >= self.config.min_content_length)
        
        return {
            "total_messages": total_messages,
            "searchable_messages": content_messages,
            "search_coverage": content_messages / total_messages if total_messages > 0 else 0,
            "strategy": self.config.strategy.value,
            "max_results": self.config.max_results,
            "similarity_threshold": self.config.similarity_threshold
        }