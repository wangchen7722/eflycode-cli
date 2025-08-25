#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
关键词检索器模块

基于关键词匹配的检索策略。
"""

import re
import time
from typing import List, Set
from collections import Counter

from .base import BaseRetriever, RetrievalResult, ContextEntry


class KeywordRetriever(BaseRetriever):
    """关键词检索器"""
    
    def __init__(self, max_results: int = 10, case_sensitive: bool = False):
        super().__init__(max_results)
        self.case_sensitive = case_sensitive
        # 停用词列表
        self.stop_words = {
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
            '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of',
            'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have',
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'
        }
    
    def retrieve(self, query: str, **kwargs) -> RetrievalResult:
        """基于关键词检索"""
        start_time = time.time()
        
        # 提取查询关键词
        query_keywords = self._extract_keywords(query)
        if not query_keywords:
            return RetrievalResult(
                messages=[],
                scores=[],
                total_found=0,
                query_time=time.time() - start_time,
                metadata={"strategy": "keyword", "query_keywords": []}
            )
        
        # 计算每个上下文条目的相关性分数
        scored_entries = []
        for entry in self.context_store:
            score = self._calculate_keyword_score(entry, query_keywords)
            if score > 0:
                scored_entries.append((entry, score))
        
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
                "strategy": "keyword",
                "query_keywords": list(query_keywords),
                "avg_score": sum(scores) / len(scores) if scores else 0
            }
        )
    
    def _extract_keywords(self, text: str) -> Set[str]:
        """提取关键词"""
        if not self.case_sensitive:
            text = text.lower()
        
        # 使用正则表达式提取单词
        words = re.findall(r'\b\w+\b', text)
        
        # 过滤停用词和短词
        keywords = set()
        for word in words:
            if len(word) > 1 and word not in self.stop_words:
                keywords.add(word)
        
        return keywords
    
    def _calculate_keyword_score(self, entry: ContextEntry, query_keywords: Set[str]) -> float:
        """计算关键词匹配分数"""
        content = entry.message.get('content', '')
        if not content:
            return 0.0
        
        # 提取内容关键词
        content_keywords = self._extract_keywords(content)
        
        # 计算交集
        matches = query_keywords.intersection(content_keywords)
        if not matches:
            return 0.0
        
        # 基础分数：匹配关键词数量 / 查询关键词总数
        base_score = len(matches) / len(query_keywords)
        
        # 考虑关键词频率
        content_words = re.findall(r'\b\w+\b', content.lower() if not self.case_sensitive else content)
        word_freq = Counter(content_words)
        
        freq_bonus = 0
        for keyword in matches:
            freq_bonus += min(word_freq.get(keyword, 0) / len(content_words), 0.1)
        
        # 考虑条目重要性
        importance_factor = entry.importance
        
        # 考虑内容长度（较长的内容可能包含更多相关信息）
        length_factor = min(len(content) / 1000, 1.0)
        
        # 综合分数
        final_score = base_score * importance_factor * (1 + freq_bonus + length_factor * 0.2)
        
        return min(final_score, 1.0)
    
    def add_keywords_to_entry(self, entry_index: int, keywords: List[str]):
        """为指定条目添加关键词标签"""
        if 0 <= entry_index < len(self.context_store):
            self.context_store[entry_index].tags.extend(keywords)