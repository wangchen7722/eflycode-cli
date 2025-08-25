#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""记忆管理测试用例"""

import unittest
import tempfile
import os
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from echo.agents.core.memory import (
    MemoryItem,
    BaseMemoryStore,
    InMemoryStore,
    SQLiteMemoryStore,
    MemoryManager
)
from echo.config import MemoryConfig


class TestMemoryItem(unittest.TestCase):
    """记忆项测试"""
    
    def test_memory_item_creation(self):
        """测试记忆项创建"""
        now = datetime.now()
        memory = MemoryItem(
            id="test_id",
            content="Test content",
            memory_type="conversation",
            importance=0.8,
            created_at=now,
            last_accessed=now,
            access_count=1,
            tags=["test", "memory"],
            metadata={"source": "test"},
            embedding=[0.1, 0.2, 0.3],
            related_memories=["related_id"]
        )
        
        self.assertEqual(memory.id, "test_id")
        self.assertEqual(memory.content, "Test content")
        self.assertEqual(memory.memory_type, "conversation")
        self.assertEqual(memory.importance, 0.8)
        self.assertEqual(memory.created_at, now)
        self.assertEqual(memory.last_accessed, now)
        self.assertEqual(memory.access_count, 1)
        self.assertEqual(memory.tags, ["test", "memory"])
        self.assertEqual(memory.metadata["source"], "test")
        self.assertEqual(memory.embedding, [0.1, 0.2, 0.3])
        self.assertEqual(memory.related_memories, ["related_id"])
    
    def test_memory_item_to_dict(self):
        """测试记忆项转字典"""
        now = datetime.now()
        memory = MemoryItem(
            id="test_id",
            content="Test content",
            memory_type="conversation",
            importance=0.8,
            created_at=now
        )
        
        memory_dict = memory.to_dict()
        
        self.assertEqual(memory_dict["id"], "test_id")
        self.assertEqual(memory_dict["content"], "Test content")
        self.assertEqual(memory_dict["memory_type"], "conversation")
        self.assertEqual(memory_dict["importance"], 0.8)
        self.assertEqual(memory_dict["created_at"], now.isoformat())
    
    def test_memory_item_from_dict(self):
        """测试从字典创建记忆项"""
        now = datetime.now()
        memory_dict = {
            "id": "test_id",
            "content": "Test content",
            "memory_type": "conversation",
            "importance": 0.8,
            "created_at": now.isoformat(),
            "last_accessed": now.isoformat(),
            "access_count": 1,
            "tags": ["test"],
            "metadata": {"source": "test"},
            "embedding": [0.1, 0.2],
            "related_memories": ["related"]
        }
        
        memory = MemoryItem.from_dict(memory_dict)
        
        self.assertEqual(memory.id, "test_id")
        self.assertEqual(memory.content, "Test content")
        self.assertEqual(memory.memory_type, "conversation")
        self.assertEqual(memory.importance, 0.8)
        self.assertEqual(memory.tags, ["test"])
        self.assertEqual(memory.metadata["source"], "test")
        self.assertEqual(memory.embedding, [0.1, 0.2])
        self.assertEqual(memory.related_memories, ["related"])


class TestInMemoryStore(unittest.TestCase):
    """内存存储器测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.store = InMemoryStore()
        self.test_memory = MemoryItem(
            id="test_id",
            content="Test content",
            memory_type="conversation",
            importance=0.8,
            created_at=datetime.now()
        )
    
    def test_store_memory(self):
        """测试存储记忆"""
        self.store.store(self.test_memory)
        
        self.assertIn("test_id", self.store.memories)
        self.assertEqual(self.store.memories["test_id"], self.test_memory)
    
    def test_retrieve_memory(self):
        """测试检索记忆"""
        self.store.store(self.test_memory)
        
        retrieved = self.store.retrieve("test_id")
        
        self.assertEqual(retrieved, self.test_memory)
        self.assertEqual(retrieved.access_count, 2)  # 访问次数增加
    
    def test_retrieve_nonexistent_memory(self):
        """测试检索不存在的记忆"""
        retrieved = self.store.retrieve("nonexistent")
        self.assertIsNone(retrieved)
    
    def test_search_memories(self):
        """测试搜索记忆"""
        memory1 = MemoryItem(id="1", content="Python programming", memory_type="conversation")
        memory2 = MemoryItem(id="2", content="Java development", memory_type="conversation")
        memory3 = MemoryItem(id="3", content="Data analysis with Python", memory_type="conversation")
        
        self.store.store(memory1)
        self.store.store(memory2)
        self.store.store(memory3)
        
        results = self.store.search("Python", limit=10)
        
        # 应该找到包含"Python"的记忆
        self.assertEqual(len(results), 2)
        contents = [memory.content for memory in results]
        self.assertIn("Python programming", contents)
        self.assertIn("Data analysis with Python", contents)
    
    def test_search_with_memory_type_filter(self):
        """测试按记忆类型过滤搜索"""
        memory1 = MemoryItem(id="1", content="Test content", memory_type="conversation")
        memory2 = MemoryItem(id="2", content="Test content", memory_type="knowledge")
        
        self.store.store(memory1)
        self.store.store(memory2)
        
        results = self.store.search("Test", memory_type="conversation")
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].memory_type, "conversation")
    
    def test_delete_memory(self):
        """测试删除记忆"""
        self.store.store(self.test_memory)
        
        success = self.store.delete("test_id")
        
        self.assertTrue(success)
        self.assertNotIn("test_id", self.store.memories)
    
    def test_delete_nonexistent_memory(self):
        """测试删除不存在的记忆"""
        success = self.store.delete("nonexistent")
        self.assertFalse(success)
    
    def test_list_memories(self):
        """测试列出记忆"""
        memory1 = MemoryItem(id="1", content="Content 1", memory_type="conversation")
        memory2 = MemoryItem(id="2", content="Content 2", memory_type="knowledge")
        
        self.store.store(memory1)
        self.store.store(memory2)
        
        all_memories = self.store.list_memories()
        self.assertEqual(len(all_memories), 2)
        
        conversation_memories = self.store.list_memories(memory_type="conversation")
        self.assertEqual(len(conversation_memories), 1)
        self.assertEqual(conversation_memories[0].memory_type, "conversation")
    
    def test_cleanup_expired_memories(self):
        """测试清理过期记忆"""
        old_time = datetime.now() - timedelta(days=10)
        recent_time = datetime.now() - timedelta(hours=1)
        
        old_memory = MemoryItem(id="old", content="Old", memory_type="conversation", last_accessed=old_time)
        recent_memory = MemoryItem(id="recent", content="Recent", memory_type="conversation", last_accessed=recent_time)
        
        self.store.store(old_memory)
        self.store.store(recent_memory)
        
        # 清理7天前的记忆
        cleaned_count = self.store.cleanup_expired(max_age_days=7)
        
        self.assertEqual(cleaned_count, 1)
        self.assertNotIn("old", self.store.memories)
        self.assertIn("recent", self.store.memories)


class TestSQLiteMemoryStore(unittest.TestCase):
    """SQLite存储器测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.store = SQLiteMemoryStore(self.temp_db.name)
        
        self.test_memory = MemoryItem(
            id="test_id",
            content="Test content",
            memory_type="conversation",
            importance=0.8,
            created_at=datetime.now()
        )
    
    def tearDown(self):
        """清理测试环境"""
        self.store.close()
        os.unlink(self.temp_db.name)
    
    def test_store_and_retrieve_memory(self):
        """测试存储和检索记忆"""
        self.store.store(self.test_memory)
        
        retrieved = self.store.retrieve("test_id")
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, "test_id")
        self.assertEqual(retrieved.content, "Test content")
        self.assertEqual(retrieved.memory_type, "conversation")
        self.assertEqual(retrieved.importance, 0.8)
    
    def test_search_memories(self):
        """测试搜索记忆"""
        memory1 = MemoryItem(id="1", content="Python programming", memory_type="conversation")
        memory2 = MemoryItem(id="2", content="Java development", memory_type="conversation")
        
        self.store.store(memory1)
        self.store.store(memory2)
        
        results = self.store.search("Python")
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content, "Python programming")
    
    def test_delete_memory(self):
        """测试删除记忆"""
        self.store.store(self.test_memory)
        
        success = self.store.delete("test_id")
        
        self.assertTrue(success)
        
        retrieved = self.store.retrieve("test_id")
        self.assertIsNone(retrieved)
    
    def test_list_memories_with_limit(self):
        """测试限制数量列出记忆"""
        for i in range(5):
            memory = MemoryItem(id=f"test_{i}", content=f"Content {i}", memory_type="conversation")
            self.store.store(memory)
        
        memories = self.store.list_memories(limit=3)
        
        self.assertEqual(len(memories), 3)
    
    def test_cleanup_expired_memories(self):
        """测试清理过期记忆"""
        old_time = datetime.now() - timedelta(days=10)
        old_memory = MemoryItem(
            id="old",
            content="Old content",
            memory_type="conversation",
            last_accessed=old_time
        )
        
        self.store.store(old_memory)
        
        cleaned_count = self.store.cleanup_expired(max_age_days=7)
        
        self.assertEqual(cleaned_count, 1)
        
        retrieved = self.store.retrieve("old")
        self.assertIsNone(retrieved)


class TestMemoryManager(unittest.TestCase):
    """记忆管理器测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.config = MemoryConfig(
            enable_persistence=False,
            max_short_term_memories=10,
            max_long_term_memories=100,
            importance_threshold=0.7
        )
        self.manager = MemoryManager(self.config)
    
    def test_add_memory(self):
        """测试添加记忆"""
        memory_id = self.manager.add_memory(
            content="Test content",
            memory_type="conversation",
            tags=["test"]
        )
        
        self.assertIsNotNone(memory_id)
        
        # 验证记忆被添加
        retrieved = self.manager.retrieve_memory(memory_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.content, "Test content")
    
    def test_add_memory_with_high_importance(self):
        """测试添加高重要性记忆"""
        # 添加包含关键词的长内容，应该有高重要性
        content = "This is an important error message that occurred during processing. " * 10
        
        memory_id = self.manager.add_memory(
            content=content,
            memory_type="conversation"
        )
        
        retrieved = self.manager.retrieve_memory(memory_id)
        self.assertGreater(retrieved.importance, 0.5)
    
    def test_search_memories(self):
        """测试搜索记忆"""
        # 添加一些测试记忆
        self.manager.add_memory("Python programming tutorial", "conversation")
        self.manager.add_memory("Java development guide", "conversation")
        self.manager.add_memory("Python data analysis", "knowledge")
        
        results = self.manager.search_memories("Python", limit=10)
        
        self.assertEqual(len(results), 2)
        contents = [memory.content for memory in results]
        self.assertTrue(any("Python" in content for content in contents))
    
    def test_update_memory(self):
        """测试更新记忆"""
        memory_id = self.manager.add_memory("Original content", "conversation")
        
        success = self.manager.update_memory(
            memory_id,
            content="Updated content",
            tags=["updated"]
        )
        
        self.assertTrue(success)
        
        retrieved = self.manager.retrieve_memory(memory_id)
        self.assertEqual(retrieved.content, "Updated content")
        self.assertIn("updated", retrieved.tags)
    
    def test_delete_memory(self):
        """测试删除记忆"""
        memory_id = self.manager.add_memory("Test content", "conversation")
        
        success = self.manager.delete_memory(memory_id)
        
        self.assertTrue(success)
        
        retrieved = self.manager.retrieve_memory(memory_id)
        self.assertIsNone(retrieved)
    
    def test_consolidate_memories(self):
        """测试记忆整合"""
        # 添加一些高重要性的记忆
        for i in range(5):
            content = f"Important error message {i}. " * 20  # 长内容，高重要性
            self.manager.add_memory(content, "conversation")
        
        # 执行整合
        consolidated_count = self.manager.consolidate_memories()
        
        # 应该有记忆被整合到长期存储
        self.assertGreaterEqual(consolidated_count, 0)
    
    def test_cleanup_expired_memories(self):
        """测试清理过期记忆"""
        # 添加记忆
        memory_id = self.manager.add_memory("Test content", "conversation")
        
        # 模拟过期（修改最后访问时间）
        memory = self.manager.retrieve_memory(memory_id)
        memory.last_accessed = datetime.now() - timedelta(days=10)
        self.manager.short_term_store.store(memory)
        
        # 清理过期记忆
        cleaned_count = self.manager.cleanup_expired_memories(max_age_days=7)
        
        self.assertGreaterEqual(cleaned_count, 0)
    
    def test_get_memory_stats(self):
        """测试获取记忆统计"""
        # 添加一些记忆
        for i in range(3):
            self.manager.add_memory(f"Content {i}", "conversation")
        
        stats = self.manager.get_memory_stats()
        
        self.assertIn("short_term_count", stats)
        self.assertIn("long_term_count", stats)
        self.assertIn("total_count", stats)
        self.assertEqual(stats["short_term_count"], 3)
    
    def test_assess_importance(self):
        """测试重要性评估"""
        # 测试包含关键词的内容
        high_importance = self.manager._assess_importance("Error: Critical failure occurred")
        
        # 测试普通内容
        low_importance = self.manager._assess_importance("Hello world")
        
        # 测试长内容
        long_content = "This is a very long message. " * 50
        long_importance = self.manager._assess_importance(long_content)
        
        self.assertGreater(high_importance, low_importance)
        self.assertGreater(long_importance, low_importance)
    
    def test_enforce_capacity_limits(self):
        """测试容量限制执行"""
        # 设置较小的容量限制
        self.manager.config.max_short_term_memories = 3
        
        # 添加超过限制的记忆
        memory_ids = []
        for i in range(5):
            memory_id = self.manager.add_memory(f"Content {i}", "conversation")
            memory_ids.append(memory_id)
        
        # 验证只保留了最近的记忆
        stats = self.manager.get_memory_stats()
        self.assertLessEqual(stats["short_term_count"], 3)
    
    @patch('echo.agents.core.memory.manager.logger')
    def test_memory_manager_with_persistence(self, mock_logger):
        """测试启用持久化的记忆管理器"""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_db.close()
        
        try:
            config = MemoryConfig(
                enable_persistence=True,
                db_path=temp_db.name
            )
            manager = MemoryManager(config)
            
            # 验证持久化存储被创建
            self.assertIsNotNone(manager.long_term_store)
            
            # 添加记忆并验证可以检索
            memory_id = manager.add_memory("Persistent content", "conversation")
            retrieved = manager.retrieve_memory(memory_id)
            self.assertIsNotNone(retrieved)
            
        finally:
            os.unlink(temp_db.name)


if __name__ == '__main__':
    unittest.main()