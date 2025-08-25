"""记忆系统基础类和数据结构"""

import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime

from echo.config import MemoryType, MemoryImportance, MemoryConfig


@dataclass
class MemoryItem:
    """记忆项数据结构"""
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
        """后处理：确保tags和related_memories是集合类型"""
        if isinstance(self.tags, list):
            self.tags = set(self.tags)
        if isinstance(self.related_memories, list):
            self.related_memories = set(self.related_memories)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
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
        """从字典创建记忆项"""
        # 转换枚举类型
        data['memory_type'] = MemoryType(data['memory_type'])
        data['importance'] = MemoryImportance(data['importance'])
        
        # 转换时间类型
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['last_accessed'] = datetime.fromisoformat(data['last_accessed'])
        
        # 转换集合类型
        data['tags'] = set(data.get('tags', []))
        data['related_memories'] = set(data.get('related_memories', []))
        
        return cls(**data)


class BaseMemoryStore(ABC):
    """记忆存储抽象基类"""
    
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