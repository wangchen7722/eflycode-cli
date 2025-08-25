"""记忆存储实现"""

import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path

from .base import BaseMemoryStore, MemoryItem
from echo.config import MemoryType, MemoryConfig
from echo.utils.logger import get_logger

logger = get_logger()


class InMemoryStore(BaseMemoryStore):
    """内存记忆存储"""
    
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
            memory.access_count += 1
            memory.last_accessed = datetime.now()
        return memory
    
    def search(self, query: str, memory_type: Optional[MemoryType] = None, limit: int = 10) -> List[MemoryItem]:
        """在内存中搜索记忆"""
        query_lower = query.lower()
        results = []
        
        for memory in self.memories.values():
            # 类型过滤
            if memory_type and memory.memory_type != memory_type:
                continue
            
            # 内容匹配
            if query_lower in memory.content.lower():
                results.append(memory)
        
        # 按重要性和访问时间排序
        results.sort(key=lambda m: (m.importance.value, m.last_accessed), reverse=True)
        return results[:limit]
    
    def delete(self, memory_id: str) -> bool:
        """从内存删除记忆"""
        if memory_id in self.memories:
            del self.memories[memory_id]
            return True
        return False
    
    def list_memories(self, memory_type: Optional[MemoryType] = None) -> List[MemoryItem]:
        """列出内存中的记忆"""
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
            return now - memory.last_accessed > timedelta(hours=config.short_term_retention_hours)
        elif memory.memory_type == MemoryType.WORKING:
            return now - memory.last_accessed > timedelta(minutes=config.working_memory_retention_minutes)
        return False  # 长期记忆不会过期


class SQLiteMemoryStore(BaseMemoryStore):
    """SQLite记忆存储"""
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self._init_database()
    
    def _init_database(self):
        """初始化数据库"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    importance TEXT NOT NULL,
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
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON memories(created_at)")
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
                    ','.join(memory.tags) if memory.tags else '',
                    str(memory.metadata) if memory.metadata else '{}',
                    str(memory.embedding) if memory.embedding else '',
                    ','.join(memory.related_memories) if memory.related_memories else ''
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
                    memory.access_count += 1
                    memory.last_accessed = datetime.now()
                    self.store(memory)  # 更新数据库
                    return memory
        except Exception as e:
            logger.error(f"检索记忆失败: {e}")
        return None
    
    def search(self, query: str, memory_type: Optional[MemoryType] = None, limit: int = 10) -> List[MemoryItem]:
        """在SQLite中搜索记忆"""
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
        """从SQLite删除记忆"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"删除记忆失败: {e}")
        return False
    
    def list_memories(self, memory_type: Optional[MemoryType] = None) -> List[MemoryItem]:
        """列出SQLite中的记忆"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                if memory_type:
                    cursor = conn.execute(
                        "SELECT * FROM memories WHERE memory_type = ? ORDER BY created_at DESC",
                        (memory_type.value,)
                    )
                else:
                    cursor = conn.execute("SELECT * FROM memories ORDER BY created_at DESC")
                
                rows = cursor.fetchall()
                return [self._row_to_memory(row) for row in rows]
        except Exception as e:
            logger.error(f"列出记忆失败: {e}")
        return []
    
    def cleanup_expired(self, config: MemoryConfig) -> int:
        """清理过期记忆"""
        try:
            now = datetime.now()
            short_term_cutoff = now - timedelta(hours=config.short_term_retention_hours)
            working_cutoff = now - timedelta(minutes=config.working_memory_retention_minutes)
            
            with sqlite3.connect(self.db_path) as conn:
                # 清理过期的短期记忆
                cursor1 = conn.execute("""
                    DELETE FROM memories 
                    WHERE memory_type = ? AND last_accessed < ?
                """, (MemoryType.SHORT_TERM.value, short_term_cutoff.isoformat()))
                
                # 清理过期的工作记忆
                cursor2 = conn.execute("""
                    DELETE FROM memories 
                    WHERE memory_type = ? AND last_accessed < ?
                """, (MemoryType.WORKING.value, working_cutoff.isoformat()))
                
                return cursor1.rowcount + cursor2.rowcount
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
            tags=set(row['tags'].split(',')) if row['tags'] else set(),
            metadata=eval(row['metadata']) if row['metadata'] and row['metadata'] != '{}' else {},
            embedding=eval(row['embedding']) if row['embedding'] else None,
            related_memories=set(row['related_memories'].split(',')) if row['related_memories'] else set()
        )