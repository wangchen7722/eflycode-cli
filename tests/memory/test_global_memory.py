import unittest

from echo.memory.agent_memory import MemoryType
from echo.memory.global_memory import GlobalMemory


class TestGlobalMemory(unittest.TestCase):
    def setUp(self):
        # 创建临时目录用于测试
        self.vector_db_path = "::memory::"

        # 初始化GlobalMemory实例
        self.memory = GlobalMemory(
            vector_db_path=self.vector_db_path,
            capacity=3
        )

    def test_singleton_pattern(self):
        # 测试单例模式
        another_memory = GlobalMemory(
            vector_db_path=self.vector_db_path,
            capacity=5
        )

        # 验证是同一个实例
        self.assertIs(self.memory, another_memory)
        # 验证配置不会被覆盖
        self.assertEqual(self.memory.capacity, 3)

    def test_add_memory(self):
        # 测试添加全局记忆
        memory_item = self.memory.add_memory("全局记忆测试")

        self.assertEqual(memory_item.content, "全局记忆测试")
        self.assertEqual(memory_item.type, MemoryType.LONG_TERM)
        self.assertEqual(len(self.memory.global_memory), 1)

    def test_capacity_limit(self):
        # 测试容量限制
        for i in range(5):
            self.memory.add_memory(f"全局记忆{i}")

        # 验证记忆数量不超过容量限制
        self.assertEqual(len(self.memory.global_memory), 3)
        # 验证保留最新的记忆
        self.assertEqual(self.memory.global_memory[-1].content, "全局记忆4")

    def test_search_memory(self):
        # 添加测试数据
        self.memory.add_memory("Python全局记忆")
        self.memory.add_memory("机器学习全局记忆")

        # 测试搜索功能
        results = self.memory.search_memory("Python", top_k=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content, "Python全局记忆")

    def test_clear_memory(self):
        # 添加测试数据
        self.memory.add_memory("全局记忆1")
        self.memory.add_memory("全局记忆2")

        # 清除记忆
        self.memory.clear_memory()
        self.assertEqual(len(self.memory.global_memory), 0)

    def test_get_memory_by_id(self):
        # 添加测试数据
        memory_item = self.memory.add_memory("测试全局记忆")

        # 测试根据ID获取记忆
        retrieved_item = self.memory.get_memory_by_id(memory_item.id)
        self.assertIsNotNone(retrieved_item)
        # self.assertEqual(retrieved_item.content, "测试全局记忆")

        # 测试获取不存在的记忆
        non_existent_item = self.memory.get_memory_by_id("non_existent_id")
        self.assertIsNone(non_existent_item)

    def test_get_recent_memories(self):
        # 添加测试数据
        self.memory.add_memory("全局记忆1")
        self.memory.add_memory("全局记忆2")
        self.memory.add_memory("全局记忆3")

        # 测试获取最近记忆
        recent_memories = self.memory.get_recent_memories(limit=2)
        self.assertEqual(len(recent_memories), 2)
        self.assertEqual(recent_memories[0].content, "全局记忆3")


if __name__ == "__main__":
    unittest.main()
