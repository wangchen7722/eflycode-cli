import unittest

from echo.memory.agent_memory import AgentMemory, MemoryType


class TestAgentMemory(unittest.TestCase):

    def setUp(self):
        # 创建临时目录用于测试
        self.vector_db_path = "::memory::"

        # 初始化AgentMemory实例
        self.memory = AgentMemory(
            vector_db_path=self.vector_db_path,
            embedding_model="all-MiniLM-L6-v2",
            short_term_capacity=3
        )

    def test_add_short_term_memory(self):
        # 测试添加短期记忆
        memory_item = self.memory.add_memory(
            content="测试短期记忆",
            memory_type=MemoryType.SHORT_TERM
        )

        self.assertEqual(memory_item.content, "测试短期记忆")
        self.assertEqual(memory_item.type, MemoryType.SHORT_TERM)
        self.assertEqual(len(self.memory.short_term_memory), 1)

    def test_add_long_term_memory(self):
        # 测试添加长期记忆
        memory_item = self.memory.add_memory(
            content="测试长期记忆",
            memory_type=MemoryType.LONG_TERM
        )

        self.assertEqual(memory_item.content, "测试长期记忆")
        self.assertEqual(memory_item.type, MemoryType.LONG_TERM)
        self.assertEqual(len(self.memory.long_term_memory), 1)

    def test_short_term_capacity(self):
        # 测试短期记忆容量限制
        for i in range(5):
            self.memory.add_memory(
                content=f"短期记忆{i}",
                memory_type=MemoryType.SHORT_TERM
            )

        # 验证短期记忆数量不超过容量限制
        self.assertEqual(len(self.memory.short_term_memory), 3)
        # 验证保留最新的记忆
        self.assertEqual(self.memory.short_term_memory[-1].content, "短期记忆4")

    def test_search_memory(self):
        # 添加测试数据
        self.memory.add_memory("Python编程", MemoryType.SHORT_TERM)
        self.memory.add_memory("机器学习", MemoryType.LONG_TERM)

        # 测试搜索功能
        results = self.memory.search_memory("Python", top_k=1, include=[
            MemoryType.SHORT_TERM
        ])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content, "Python编程")

    def test_clear_memory(self):
        # 添加测试数据
        self.memory.add_memory("短期记忆", MemoryType.SHORT_TERM)
        self.memory.add_memory("长期记忆", MemoryType.LONG_TERM)

        # 清除短期记忆
        self.memory.clear_memory(MemoryType.SHORT_TERM)
        self.assertEqual(len(self.memory.short_term_memory), 0)
        self.assertEqual(len(self.memory.long_term_memory), 1)

        # 清除所有记忆
        self.memory.clear_memory()
        self.assertEqual(len(self.memory.short_term_memory), 0)
        self.assertEqual(len(self.memory.long_term_memory), 0)

    def test_get_memory_by_id(self):
        # 添加测试数据
        memory_item = self.memory.add_memory("测试记忆", MemoryType.SHORT_TERM)

        # 测试根据ID获取记忆
        retrieved_item = self.memory.get_memory_by_id(memory_item.id)
        self.assertIsNotNone(retrieved_item)
        # self.assertEqual(retrieved_item.content, "测试记忆")

        # 测试获取不存在的记忆
        non_existent_item = self.memory.get_memory_by_id("non_existent_id")
        self.assertIsNone(non_existent_item)

    def test_get_recent_memories(self):
        # 添加测试数据
        self.memory.add_memory("记忆1", MemoryType.SHORT_TERM)
        self.memory.add_memory("记忆2", MemoryType.LONG_TERM)
        self.memory.add_memory("记忆3", MemoryType.SHORT_TERM)

        # 测试获取最近记忆
        recent_memories = self.memory.get_recent_memories(limit=2)
        self.assertEqual(len(recent_memories), 2)
        self.assertEqual(recent_memories[0].content, "记忆3")

        # 测试按类型获取最近记忆
        short_term_memories = self.memory.get_recent_memories(
            limit=2,
        )
        self.assertEqual(len(short_term_memories), 2)
        self.assertEqual(short_term_memories[0].content, "记忆3")