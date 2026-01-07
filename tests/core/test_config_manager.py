"""ConfigManager 测试用例"""

import unittest
from pathlib import Path

from eflycode.core.config.config_manager import Config, ConfigManager, LLMConfig


class TestConfigManager(unittest.TestCase):
    """ConfigManager 测试类"""

    def setUp(self):
        """设置测试环境"""
        # 重置单例实例
        ConfigManager._instance = None

    def test_singleton_pattern(self):
        """测试单例模式"""
        instance1 = ConfigManager.get_instance()
        instance2 = ConfigManager.get_instance()

        self.assertIs(instance1, instance2)


    def test_load(self):
        """测试显式加载配置"""
        manager = ConfigManager.get_instance()
        config = manager.load()

        self.assertIsNotNone(config)
        self.assertIsInstance(config, Config)
        self.assertTrue(manager._initialized)

    def test_get_config_lazy_load(self):
        """测试懒加载配置"""
        manager = ConfigManager.get_instance()
        # 重置状态
        manager.config = None
        manager._initialized = False

        # 首次访问应该自动加载
        config = manager.get_config()

        self.assertIsNotNone(config)
        self.assertIsInstance(config, Config)
        self.assertTrue(manager._initialized)

    def test_get_config_already_loaded(self):
        """测试已加载配置时直接返回"""
        manager = ConfigManager.get_instance()
        manager.load()
        original_config = manager.config

        # 再次获取应该返回同一个对象
        config = manager.get_config()

        self.assertIs(config, original_config)

    def test_get_max_context_length(self):
        """测试获取最大上下文长度"""
        manager = ConfigManager.get_instance()
        manager.load()

        max_length = manager.get_max_context_length()

        self.assertIsInstance(max_length, int)
        self.assertGreater(max_length, 0)

    def test_get_system_info(self):
        """测试获取系统信息"""
        manager = ConfigManager.get_instance()
        manager.load()

        system_info = manager.get_system_info()

        self.assertIn("version", system_info)
        self.assertIn("timezone", system_info)
        self.assertIn("date", system_info)
        self.assertIn("time", system_info)
        self.assertIn("datetime", system_info)

        # 检查日期格式
        self.assertRegex(system_info["date"], r"\d{4}-\d{2}-\d{2}")
        self.assertRegex(system_info["time"], r"\d{2}:\d{2}:\d{2}")

    def test_get_workspace_info(self):
        """测试获取工作区信息"""
        manager = ConfigManager.get_instance()
        manager.load()

        workspace_info = manager.get_workspace_info()

        # 由于使用实际配置，只检查结构
        self.assertIn("path", workspace_info)
        self.assertIn("name", workspace_info)

    def test_get_workspace_info_no_config(self):
        """测试无配置时获取工作区信息（会自动懒加载）"""
        manager = ConfigManager.get_instance()
        # 重置状态
        manager.config = None
        manager._initialized = False

        workspace_info = manager.get_workspace_info()

        # 由于懒加载，应该会返回实际的工作区信息
        self.assertIn("path", workspace_info)
        self.assertIn("name", workspace_info)
        # 应该已经自动加载了配置
        self.assertTrue(manager._initialized)

    def test_get_time_info(self):
        """测试获取时间信息"""
        manager = ConfigManager.get_instance()
        manager.load()

        time_info = manager.get_time_info()

        self.assertIn("timezone", time_info)
        self.assertIn("date", time_info)
        self.assertIn("time", time_info)
        self.assertIn("datetime", time_info)

    def test_get_environment_info(self):
        """测试获取环境信息"""
        manager = ConfigManager.get_instance()
        manager.load()

        env_info = manager.get_environment_info()

        self.assertIn("os", env_info)
        self.assertIn("python_version", env_info)
        self.assertIn("platform", env_info)

        # 检查 Python 版本格式
        self.assertRegex(env_info["python_version"], r"\d+\.\d+\.\d+")

    def test_load_version(self):
        """测试加载版本"""
        manager = ConfigManager.get_instance()
        manager.load()

        version = manager._load_version()

        self.assertIsInstance(version, str)
        # 版本应该被缓存
        version2 = manager._load_version()
        self.assertEqual(version, version2)

