#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检索器基础类模块

定义检索器的基础接口和数据结构。
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from echo.llms.schema import Message


@dataclass
class RetrievalResult:
    """检索结果"""
    messages: List[Message]
    scores: List[float]  # 相关性评分
    total_found: int
    query_time: float
    metadata: Dict[str, Any]


@dataclass
class ContextEntry:
    """上下文条目"""
    message: Message
    timestamp: datetime
    importance: float = 1.0
    tags: List[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.metadata is None:
            self.metadata = {}


class BaseRetriever(ABC):
    """检索器基类"""
    
    def __init__(self, max_results: int = 10):
        self.max_results = max_results
        self.context_store: List[ContextEntry] = []
    
    @abstractmethod
    def retrieve(self, query: str, **kwargs) -> RetrievalResult:
        """检索相关上下文"""
        pass
    
    def add_context(self, message: Message, importance: float = 1.0, tags: List[str] = None):
        """添加上下文"""
        entry = ContextEntry(
            message=message,
            timestamp=datetime.now(),
            importance=importance,
            tags=tags or []
        )
        self.context_store.append(entry)
    
    def clear_context(self):
        """清空上下文存储"""
        self.context_store.clear()
    
    def get_context_count(self) -> int:
        """获取上下文数量"""
        return len(self.context_store)
    
    def _filter_by_tags(self, entries: List[ContextEntry], tags: List[str]) -> List[ContextEntry]:
        """根据标签过滤条目"""
        if not tags:
            return entries
        
        filtered = []
        for entry in entries:
            if any(tag in entry.tags for tag in tags):
                filtered.append(entry)
        return filtered
    
    def _sort_by_importance(self, entries: List[ContextEntry]) -> List[ContextEntry]:
        """根据重要性排序"""
        return sorted(entries, key=lambda x: x.importance, reverse=True)