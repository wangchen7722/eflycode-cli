#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
时间检索器模块

基于时间的检索策略。
"""

import time
from datetime import datetime, timedelta
from typing import List, Optional

from .base import BaseRetriever, RetrievalResult, ContextEntry


class TemporalRetriever(BaseRetriever):
    """时间检索器"""
    
    def __init__(self, max_results: int = 10):
        super().__init__(max_results)
    
    def retrieve(self, query: str, **kwargs) -> RetrievalResult:
        """基于时间检索"""
        start_time = time.time()
        
        # 从kwargs中获取时间相关参数
        time_range = kwargs.get('time_range')  # (start_time, end_time)
        recent_hours = kwargs.get('recent_hours')  # 最近N小时
        recent_days = kwargs.get('recent_days')  # 最近N天
        
        # 过滤条目
        filtered_entries = self._filter_by_time(
            self.context_store, 
            time_range=time_range,
            recent_hours=recent_hours,
            recent_days=recent_days
        )
        
        # 按时间排序（最新的在前）
        filtered_entries.sort(key=lambda x: x.timestamp, reverse=True)
        
        # 限制结果数量
        top_entries = filtered_entries[:self.max_results]
        
        # 计算时间相关的分数
        messages = []
        scores = []
        current_time = datetime.now()
        
        for entry in top_entries:
            messages.append(entry.message)
            # 时间分数：越新的消息分数越高
            time_diff = (current_time - entry.timestamp).total_seconds()
            time_score = max(0.1, 1.0 - (time_diff / (7 * 24 * 3600)))  # 7天内的消息
            final_score = time_score * entry.importance
            scores.append(final_score)
        
        return RetrievalResult(
            messages=messages,
            scores=scores,
            total_found=len(filtered_entries),
            query_time=time.time() - start_time,
            metadata={
                "strategy": "temporal",
                "time_range": time_range,
                "recent_hours": recent_hours,
                "recent_days": recent_days,
                "oldest_entry": min(entry.timestamp for entry in top_entries).isoformat() if top_entries else None,
                "newest_entry": max(entry.timestamp for entry in top_entries).isoformat() if top_entries else None
            }
        )
    
    def retrieve_recent(self, hours: int = 24) -> RetrievalResult:
        """检索最近N小时的消息"""
        return self.retrieve("", recent_hours=hours)
    
    def retrieve_by_date_range(self, start_date: datetime, end_date: datetime) -> RetrievalResult:
        """检索指定日期范围内的消息"""
        return self.retrieve("", time_range=(start_date, end_date))
    
    def retrieve_today(self) -> RetrievalResult:
        """检索今天的消息"""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        return self.retrieve_by_date_range(today, tomorrow)
    
    def retrieve_this_week(self) -> RetrievalResult:
        """检索本周的消息"""
        now = datetime.now()
        # 计算本周开始时间（周一）
        days_since_monday = now.weekday()
        week_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday)
        week_end = week_start + timedelta(days=7)
        return self.retrieve_by_date_range(week_start, week_end)
    
    def _filter_by_time(self, 
                       entries: List[ContextEntry],
                       time_range: Optional[tuple] = None,
                       recent_hours: Optional[int] = None,
                       recent_days: Optional[int] = None) -> List[ContextEntry]:
        """根据时间条件过滤条目"""
        filtered = entries.copy()
        current_time = datetime.now()
        
        # 按时间范围过滤
        if time_range:
            start_time, end_time = time_range
            filtered = [
                entry for entry in filtered
                if start_time <= entry.timestamp <= end_time
            ]
        
        # 按最近小时数过滤
        if recent_hours is not None:
            cutoff_time = current_time - timedelta(hours=recent_hours)
            filtered = [
                entry for entry in filtered
                if entry.timestamp >= cutoff_time
            ]
        
        # 按最近天数过滤
        if recent_days is not None:
            cutoff_time = current_time - timedelta(days=recent_days)
            filtered = [
                entry for entry in filtered
                if entry.timestamp >= cutoff_time
            ]
        
        return filtered
    
    def get_time_distribution(self) -> dict:
        """获取时间分布统计"""
        if not self.context_store:
            return {}
        
        current_time = datetime.now()
        distribution = {
            "total_entries": len(self.context_store),
            "last_hour": 0,
            "last_24_hours": 0,
            "last_week": 0,
            "last_month": 0,
            "older": 0
        }
        
        for entry in self.context_store:
            time_diff = current_time - entry.timestamp
            
            if time_diff <= timedelta(hours=1):
                distribution["last_hour"] += 1
            elif time_diff <= timedelta(hours=24):
                distribution["last_24_hours"] += 1
            elif time_diff <= timedelta(days=7):
                distribution["last_week"] += 1
            elif time_diff <= timedelta(days=30):
                distribution["last_month"] += 1
            else:
                distribution["older"] += 1
        
        return distribution