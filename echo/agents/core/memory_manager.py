#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
记忆管理器模块

提供智能的记忆管理功能，包括：
- 短期记忆（工作记忆）
- 长期记忆（持久化存储）
- 记忆检索和更新
- 记忆重要性评估
- 记忆遗忘机制
"""

import json
import sqlite3
import hashlib
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from pathlib import Path

from echo.llms.schema import Message
from echo.llms.llm_engine import LLMEngine
from echo.utils.logger import get_logger
from echo.config import MemoryType, MemoryImportance, MemoryConfig

logger = get_logger()





@dataclass
class MemoryItem:
    """记忆项"""
    id: str
    content: str
    memory_type: MemoryType
    importance: MemoryImportance
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    tags: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    related_memories: Set[str] = field(default_factory=set)
    
    def __post_init__(self):
        if isinstance(self.tags, list):
            self.tags = set(self.tags)
        if isinstance(self.related_memories, list):
            self.related_memories = set(self.related_memories)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['memory_type'] = self.memory_type.value
        data['importance'] = self.importance.value
        data['created_at'] = self.created_at.isoformat()
        data['last_accessed'] = self.last_accessed.isoformat()
        data['tags'] = list(self.tags)
        data['related_memories'] = list(self.related_memories)
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryItem":
        """从字典创建"""
        data = data.copy()
        data["memory_type"] = MemoryType(data["memory_type"])
        data["importance"] = MemoryImportance(data["importance"])
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["last_accessed"] = datetime.fromisoformat(data["last_accessed"])
        data["tags"] = set(data.get("tags", []))
        data["related_memories"] = set(data.get("related_memories", []))
        return cls(**data)





class BaseMemoryStore(ABC):
    """记忆存储基类"""
    
    @abstractmethod
    def store(self, memory: MemoryItem) -> bool:
        """存储记忆"""
        pass
    
    @abstractmethod
    def retrieve(self, memory_id: str) -> Optional[MemoryItem]:
        """检索记忆"""
        pass
    
    @abstractmethod
    def search(self, query: str, memory_type: Optional[MemoryType] = None, limit: int = 10) -> List[MemoryItem]:
        """搜索记忆"""
        pass
    
    @abstractmethod
    def delete(self, memory_id: str) -> bool:
        """删除记忆"""
        pass
    
    @abstractmethod
    def list_memories(self, memory_type: Optional[MemoryType] = None) -> List[MemoryItem]:
        """列出记忆"""
        pass
    
    @abstractmethod
    def cleanup_expired(self, config: MemoryConfig) -> int:
        """清理过期记忆"""
        pass


class InMemoryStore(BaseMemoryStore):
    """内存存储"""
    
    def __init__(self):
        self.memories: Dict[str, MemoryItem] = {}
    
    def store(self, memory: MemoryItem) -> bool:
        """存储记忆到内存"""
        self.memories[memory.id] = memory
        return True
    
    def retrieve(self, memory_id: str) -> Optional[MemoryItem]:
        """从内存检索记忆"""
        memory = self.memories.get(memory_id)
        if memory:
            memory.last_accessed = datetime.now()
            memory.access_count += 1
        return memory
    
    def search(self, query: str, memory_type: Optional[MemoryType] = None, limit: int = 10) -> List[MemoryItem]:
        """搜索记忆"""
        query_lower = query.lower()
        results = []
        
        for memory in self.memories.values():
            if memory_type and memory.memory_type != memory_type:
                continue
            
            # 简单的文本匹配
            if (query_lower in memory.content.lower() or 
                any(query_lower in tag.lower() for tag in memory.tags)):
                results.append(memory)
        
        # 按重要性和访问时间排序
        results.sort(key=lambda m: (m.importance.value, m.last_accessed), reverse=True)
        return results[:limit]
    
    def delete(self, memory_id: str) -> bool:
        """删除记忆"""
        if memory_id in self.memories:
            del self.memories[memory_id]
            return True
        return False
    
    def list_memories(self, memory_type: Optional[MemoryType] = None) -> List[MemoryItem]:
        """列出记忆"""
        if memory_type:
            return [m for m in self.memories.values() if m.memory_type == memory_type]
        return list(self.memories.values())
    
    def cleanup_expired(self, config: MemoryConfig) -> int:
        """清理过期记忆"""
        now = datetime.now()
        expired_ids = []
        
        for memory_id, memory in self.memories.items():
            if self._is_expired(memory, now, config):
                expired_ids.append(memory_id)
        
        for memory_id in expired_ids:
            del self.memories[memory_id]
        
        return len(expired_ids)
    
    def _is_expired(self, memory: MemoryItem, now: datetime, config: MemoryConfig) -> bool:
        """检查记忆是否过期"""
        if memory.memory_type == MemoryType.SHORT_TERM:
            ttl = timedelta(hours=config.short_term_ttl_hours)
        elif memory.memory_type == MemoryType.WORKING:
            ttl = timedelta(minutes=config.working_memory_ttl_minutes)
        else:
            return False  # 长期记忆不会过期
        
        return now - memory.last_accessed > ttl


class SQLiteMemoryStore(BaseMemoryStore):
    """SQLite持久化存储"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """初始化数据库"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    importance INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    last_accessed TEXT NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    tags TEXT,
                    metadata TEXT,
                    embedding TEXT,
                    related_memories TEXT
                )
            """)
            
            # 创建索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_type ON memories(memory_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_importance ON memories(importance)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_last_accessed ON memories(last_accessed)")
    
    def store(self, memory: MemoryItem) -> bool:
        """存储记忆到SQLite"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO memories 
                    (id, content, memory_type, importance, created_at, last_accessed, 
                     access_count, tags, metadata, embedding, related_memories)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    memory.id,
                    memory.content,
                    memory.memory_type.value,
                    memory.importance.value,
                    memory.created_at.isoformat(),
                    memory.last_accessed.isoformat(),
                    memory.access_count,
                    json.dumps(list(memory.tags)),
                    json.dumps(memory.metadata),
                    json.dumps(memory.embedding) if memory.embedding else None,
                    json.dumps(list(memory.related_memories))
                ))
            return True
        except Exception as e:
            logger.error(f"存储记忆失败: {e}")
            return False
    
    def retrieve(self, memory_id: str) -> Optional[MemoryItem]:
        """从SQLite检索记忆"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
                row = cursor.fetchone()
                
                if row:
                    memory = self._row_to_memory(row)
                    # 更新访问信息
                    memory.last_accessed = datetime.now()
                    memory.access_count += 1
                    self.store(memory)  # 更新数据库
                    return memory
        except Exception as e:
            logger.error(f"检索记忆失败: {e}")
        
        return None
    
    def search(self, query: str, memory_type: Optional[MemoryType] = None, limit: int = 10) -> List[MemoryItem]:
        """搜索记忆"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                sql = "SELECT * FROM memories WHERE content LIKE ?"
                params = [f"%{query}%"]
                
                if memory_type:
                    sql += " AND memory_type = ?"
                    params.append(memory_type.value)
                
                sql += " ORDER BY importance DESC, last_accessed DESC LIMIT ?"
                params.append(limit)
                
                cursor = conn.execute(sql, params)
                rows = cursor.fetchall()
                
                return [self._row_to_memory(row) for row in rows]
        except Exception as e:
            logger.error(f"搜索记忆失败: {e}")
            return []
    
    def delete(self, memory_id: str) -> bool:
        """删除记忆"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"删除记忆失败: {e}")
            return False
    
    def list_memories(self, memory_type: Optional[MemoryType] = None) -> List[MemoryItem]:
        """列出记忆"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                if memory_type:
                    cursor = conn.execute(
                        "SELECT * FROM memories WHERE memory_type = ? ORDER BY last_accessed DESC",
                        (memory_type.value,)
                    )
                else:
                    cursor = conn.execute("SELECT * FROM memories ORDER BY last_accessed DESC")
                
                rows = cursor.fetchall()
                return [self._row_to_memory(row) for row in rows]
        except Exception as e:
            logger.error(f"列出记忆失败: {e}")
            return []
    
    def cleanup_expired(self, config: MemoryConfig) -> int:
        """清理过期记忆"""
        try:
            now = datetime.now()
            short_term_cutoff = now - timedelta(hours=config.short_term_ttl_hours)
            working_cutoff = now - timedelta(minutes=config.working_memory_ttl_minutes)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM memories WHERE 
                    (memory_type = ? AND last_accessed < ?) OR
                    (memory_type = ? AND last_accessed < ?)
                """, (
                    MemoryType.SHORT_TERM.value, short_term_cutoff.isoformat(),
                    MemoryType.WORKING.value, working_cutoff.isoformat()
                ))
                return cursor.rowcount
        except Exception as e:
            logger.error(f"清理过期记忆失败: {e}")
            return 0
    
    def _row_to_memory(self, row: sqlite3.Row) -> MemoryItem:
        """将数据库行转换为MemoryItem"""
        return MemoryItem(
            id=row['id'],
            content=row['content'],
            memory_type=MemoryType(row['memory_type']),
            importance=MemoryImportance(row['importance']),
            created_at=datetime.fromisoformat(row['created_at']),
            last_accessed=datetime.fromisoformat(row['last_accessed']),
            access_count=row['access_count'],
            tags=set(json.loads(row['tags']) if row['tags'] else []),
            metadata=json.loads(row['metadata']) if row['metadata'] else {},
            embedding=json.loads(row['embedding']) if row['embedding'] else None,
            related_memories=set(json.loads(row['related_memories']) if row['related_memories'] else [])
        )


class MemoryManager:
    """记忆管理器主类"""
    
    def __init__(self, config: MemoryConfig, llm_engine: Optional[LLMEngine] = None):
        self.config = config
        self.llm_engine = llm_engine
        
        # 初始化存储
        self.memory_store = InMemoryStore()
        if config.enable_persistence:
            db_path = Path(config.storage_path) / "memories.db"
            self.persistent_store = SQLiteMemoryStore(str(db_path))
        else:
            self.persistent_store = None
    
    def add_memory(self, content: str, memory_type: MemoryType = MemoryType.SHORT_TERM, 
                   importance: Optional[MemoryImportance] = None, 
                   tags: Optional[Set[str]] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> str:
        """添加记忆
        
        Args:
            content: 记忆内容
            memory_type: 记忆类型
            importance: 重要性（如果未指定，将自动评估）
            tags: 标签
            metadata: 元数据
            
        Returns:
            str: 记忆ID
        """
        # 生成记忆ID
        memory_id = self._generate_memory_id(content)
        
        # 自动评估重要性
        if importance is None:
            importance = self._assess_importance(content)
        
        # 创建记忆项
        now = datetime.now()
        memory = MemoryItem(
            id=memory_id,
            content=content,
            memory_type=memory_type,
            importance=importance,
            created_at=now,
            last_accessed=now,
            tags=tags or set(),
            metadata=metadata or {}
        )
        
        # 存储记忆
        self._store_memory(memory)
        
        # 检查容量限制
        self._enforce_capacity_limits()
        
        logger.info(f"添加记忆: {memory_id[:8]}... (类型={memory_type.value}, 重要性={importance.value})")
        return memory_id
    
    def retrieve_memory(self, memory_id: str) -> Optional[MemoryItem]:
        """检索记忆"""
        # 先从内存存储检索
        memory = self.memory_store.retrieve(memory_id)
        
        # 如果内存中没有，从持久化存储检索
        if not memory and self.persistent_store:
            memory = self.persistent_store.retrieve(memory_id)
            if memory:
                # 加载到内存存储
                self.memory_store.store(memory)
        
        return memory
    
    def search_memories(self, query: str, memory_type: Optional[MemoryType] = None, 
                       limit: int = None) -> List[MemoryItem]:
        """搜索记忆"""
        if limit is None:
            limit = self.config.max_retrieval_results
        
        # 从内存存储搜索
        memory_results = self.memory_store.search(query, memory_type, limit)
        
        # 从持久化存储搜索（如果需要更多结果）
        if len(memory_results) < limit and self.persistent_store:
            persistent_results = self.persistent_store.search(query, memory_type, limit - len(memory_results))
            
            # 合并结果，去重
            seen_ids = {m.id for m in memory_results}
            for memory in persistent_results:
                if memory.id not in seen_ids:
                    memory_results.append(memory)
                    seen_ids.add(memory.id)
        
        return memory_results[:limit]
    
    def update_memory(self, memory_id: str, **updates) -> bool:
        """更新记忆"""
        memory = self.retrieve_memory(memory_id)
        if not memory:
            return False
        
        # 更新字段
        for field, value in updates.items():
            if hasattr(memory, field):
                setattr(memory, field, value)
        
        memory.last_accessed = datetime.now()
        
        # 重新存储
        return self._store_memory(memory)
    
    def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        success = self.memory_store.delete(memory_id)
        
        if self.persistent_store:
            persistent_success = self.persistent_store.delete(memory_id)
            success = success or persistent_success
        
        return success
    
    def consolidate_memories(self) -> int:
        """整合记忆（将重要的短期记忆转为长期记忆）"""
        short_term_memories = self.memory_store.list_memories(MemoryType.SHORT_TERM)
        consolidated_count = 0
        
        for memory in short_term_memories:
            if (memory.importance.value >= self.config.long_term_importance_threshold.value or
                memory.access_count >= self.config.min_access_for_retention):
                
                # 转为长期记忆
                memory.memory_type = MemoryType.LONG_TERM
                self._store_memory(memory)
                consolidated_count += 1
        
        logger.info(f"整合记忆: {consolidated_count}条短期记忆转为长期记忆")
        return consolidated_count
    
    def cleanup_expired_memories(self) -> int:
        """清理过期记忆"""
        memory_count = self.memory_store.cleanup_expired(self.config)
        persistent_count = 0
        
        if self.persistent_store:
            persistent_count = self.persistent_store.cleanup_expired(self.config)
        
        total_count = memory_count + persistent_count
        logger.info(f"清理过期记忆: {total_count}条记忆被清理")
        return total_count
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """获取记忆统计信息"""
        all_memories = self.memory_store.list_memories()
        
        stats = {
            "total_memories": len(all_memories),
            "by_type": {},
            "by_importance": {},
            "average_access_count": 0,
            "oldest_memory": None,
            "newest_memory": None
        }
        
        if all_memories:
            # 按类型统计
            for memory_type in MemoryType:
                count = sum(1 for m in all_memories if m.memory_type == memory_type)
                stats["by_type"][memory_type.value] = count
            
            # 按重要性统计
            for importance in MemoryImportance:
                count = sum(1 for m in all_memories if m.importance == importance)
                stats["by_importance"][importance.value] = count
            
            # 平均访问次数
            stats["average_access_count"] = sum(m.access_count for m in all_memories) / len(all_memories)
            
            # 最老和最新记忆
            sorted_memories = sorted(all_memories, key=lambda m: m.created_at)
            stats["oldest_memory"] = sorted_memories[0].created_at.isoformat()
            stats["newest_memory"] = sorted_memories[-1].created_at.isoformat()
        
        return stats
    
    def _generate_memory_id(self, content: str) -> str:
        """生成记忆ID"""
        timestamp = datetime.now().isoformat()
        content_hash = hashlib.md5(f"{content}{timestamp}".encode()).hexdigest()
        return f"mem_{content_hash[:16]}"
    
    def _assess_importance(self, content: str) -> MemoryImportance:
        """评估记忆重要性"""
        # 简化的重要性评估逻辑
        content_lower = content.lower()
        
        # 关键词指标
        critical_keywords = ['错误', '失败', '成功', '重要', '关键', 'error', 'critical', 'important', 'success', 'failure']
        high_keywords = ['问题', '解决', '决定', 'problem', 'solution', 'decision']
        
        if any(keyword in content_lower for keyword in critical_keywords):
            return MemoryImportance.CRITICAL
        elif any(keyword in content_lower for keyword in high_keywords):
            return MemoryImportance.HIGH
        elif len(content) > 200:  # 长内容通常更重要
            return MemoryImportance.MEDIUM
        elif len(content) > 50:
            return MemoryImportance.LOW
        else:
            return MemoryImportance.MINIMAL
    
    def _store_memory(self, memory: MemoryItem) -> bool:
        """存储记忆到所有存储后端"""
        # 存储到内存
        memory_success = self.memory_store.store(memory)
        
        # 存储到持久化存储（长期记忆）
        persistent_success = True
        if (self.persistent_store and 
            memory.memory_type in [MemoryType.LONG_TERM, MemoryType.SEMANTIC, MemoryType.EPISODIC]):
            persistent_success = self.persistent_store.store(memory)
        
        return memory_success and persistent_success
    
    def _enforce_capacity_limits(self):
        """强制执行容量限制"""
        # 检查各类型记忆的容量
        for memory_type, capacity in [
            (MemoryType.SHORT_TERM, self.config.short_term_capacity),
            (MemoryType.WORKING, self.config.working_memory_capacity),
            (MemoryType.LONG_TERM, self.config.long_term_capacity)
        ]:
            memories = self.memory_store.list_memories(memory_type)
            
            if len(memories) > capacity:
                # 按访问时间和重要性排序，删除最不重要的
                memories.sort(key=lambda m: (m.importance.value, m.last_accessed))
                
                excess_count = len(memories) - capacity
                for memory in memories[:excess_count]:
                    self.memory_store.delete(memory.id)
                
                logger.info(f"容量限制: 删除了{excess_count}条{memory_type.value}记忆")