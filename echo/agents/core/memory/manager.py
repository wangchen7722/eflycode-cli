"""记忆管理器"""

import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime

from .base import MemoryItem
from .stores import InMemoryStore, SQLiteMemoryStore
from echo.config import MemoryType, MemoryImportance, MemoryConfig
from echo.utils.logger import get_logger

logger = get_logger()


class MemoryManager:
    """记忆管理器
    
    负责管理不同类型的记忆存储，提供统一的记忆操作接口。
    支持内存存储和持久化存储的组合使用。
    """
    
    def __init__(self, config: MemoryConfig):
        self.config = config
        
        # 内存存储（快速访问）
        self.memory_store = InMemoryStore()
        
        # 持久化存储（可选）
        self.persistent_store = None
        if config.enable_persistence and config.persistence_path:
            self.persistent_store = SQLiteMemoryStore(config.persistence_path)
        
        logger.info(f"记忆管理器初始化完成 (持久化: {config.enable_persistence})")
    
    def add_memory(self, content: str, memory_type: MemoryType = MemoryType.SHORT_TERM,
                   importance: Optional[MemoryImportance] = None,
                   tags: Optional[List[str]] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> str:
        """添加记忆
        
        Args:
            content: 记忆内容
            memory_type: 记忆类型
            importance: 重要性（如果不指定则自动评估）
            tags: 标签列表
            metadata: 元数据
            
        Returns:
            记忆ID
        """
        # 生成记忆ID
        memory_id = self._generate_memory_id(content)
        
        # 评估重要性
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
            tags=set(tags) if tags else set(),
            metadata=metadata or {}
        )
        
        # 存储记忆
        self._store_memory(memory)
        
        # 检查容量限制
        self._enforce_capacity_limits()
        
        logger.info(f"添加记忆: {memory_id[:8]}... (类型={memory_type.value}, 重要性={importance.value})")
        return memory_id
    
    def retrieve_memory(self, memory_id: str) -> Optional[MemoryItem]:
        """检索记忆
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            记忆项，如果不存在则返回None
        """
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
        """搜索记忆
        
        Args:
            query: 搜索查询
            memory_type: 记忆类型过滤
            limit: 结果数量限制
            
        Returns:
            匹配的记忆列表
        """
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
        """更新记忆
        
        Args:
            memory_id: 记忆ID
            **updates: 要更新的字段
            
        Returns:
            是否更新成功
        """
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
        """删除记忆
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            是否删除成功
        """
        success = self.memory_store.delete(memory_id)
        
        if self.persistent_store:
            persistent_success = self.persistent_store.delete(memory_id)
            success = success or persistent_success
        
        return success
    
    def consolidate_memories(self) -> int:
        """整合记忆（将重要的短期记忆转为长期记忆）
        
        Returns:
            转换的记忆数量
        """
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
        """清理过期记忆
        
        Returns:
            清理的记忆数量
        """
        memory_count = self.memory_store.cleanup_expired(self.config)
        persistent_count = 0
        
        if self.persistent_store:
            persistent_count = self.persistent_store.cleanup_expired(self.config)
        
        total_count = memory_count + persistent_count
        logger.info(f"清理过期记忆: {total_count}条记忆被清理")
        return total_count
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """获取记忆统计信息
        
        Returns:
            统计信息字典
        """
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
        """生成记忆ID
        
        Args:
            content: 记忆内容
            
        Returns:
            唯一的记忆ID
        """
        timestamp = datetime.now().isoformat()
        content_hash = hashlib.md5(f"{content}{timestamp}".encode()).hexdigest()
        return f"mem_{content_hash[:16]}"
    
    def _assess_importance(self, content: str) -> MemoryImportance:
        """评估记忆重要性
        
        Args:
            content: 记忆内容
            
        Returns:
            重要性等级
        """
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
        """存储记忆到所有存储后端
        
        Args:
            memory: 记忆项
            
        Returns:
            是否存储成功
        """
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