"""配置 source 属性测试"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from eflycode.core.config.config_manager import ConfigManager


class TestConfigSource(unittest.TestCase):
    """配置 source 属性测试类"""

    def setUp(self):
        """设置测试环境"""
        # 清理单例
        ConfigManager._instance = None

    def tearDown(self):
        """清理测试环境"""
        ConfigManager._instance = None

    def test_config_source_user_only(self):
        """测试只有用户配置时的 source"""
        with tempfile.TemporaryDirectory() as tmpdir:
            user_config_dir = Path(tmpdir) / ".eflycode"
            user_config_dir.mkdir()
            user_config_file = user_config_dir / "config.yaml"
            
            # 创建用户配置
            user_config_file.write_text("""
model:
  default: gpt-4
  entries:
    - model: gpt-4
      api_key: sk-test123
""")
            
            with patch("eflycode.core.config.config_manager.find_config_files") as mock_find:
                mock_find.return_value = (
                    user_config_file,
                    None,  # 无项目配置
                    Path(tmpdir),
                )
                
                config_manager = ConfigManager.get_instance()
                config = config_manager.load()
                
                # 验证 source
                self.assertEqual(config.source, "user")

    def test_config_source_project_only(self):
        """测试只有项目配置时的 source"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_config_file = Path(tmpdir) / ".eflycode" / "config.yaml"
            project_config_file.parent.mkdir(parents=True)
            
            # 创建项目配置
            project_config_file.write_text("""
model:
  default: gpt-4
  entries:
    - model: gpt-4
      api_key: sk-test123
""")
            
            with patch("eflycode.core.config.config_manager.find_config_files") as mock_find:
                mock_find.return_value = (
                    None,  # 无用户配置
                    project_config_file,
                    Path(tmpdir),
                )
                
                config_manager = ConfigManager.get_instance()
                config = config_manager.load()
                
                # 验证 source
                self.assertEqual(config.source, "project")

    def test_config_source_merged(self):
        """测试合并配置时的 source（应该优先使用 project）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            user_config_dir = Path(tmpdir) / "user" / ".eflycode"
            user_config_dir.mkdir(parents=True)
            user_config_file = user_config_dir / "config.yaml"
            
            project_config_file = Path(tmpdir) / ".eflycode" / "config.yaml"
            project_config_file.parent.mkdir(parents=True)
            
            # 创建用户配置
            user_config_file.write_text("""
model:
  default: gpt-4
  entries:
    - model: gpt-4
      api_key: sk-user123
""")
            
            # 创建项目配置
            project_config_file.write_text("""
model:
  default: gpt-3.5-turbo
  entries:
    - model: gpt-3.5-turbo
      api_key: sk-project123
""")
            
            with patch("eflycode.core.config.config_manager.find_config_files") as mock_find:
                mock_find.return_value = (
                    user_config_file,
                    project_config_file,
                    Path(tmpdir),
                )
                
                config_manager = ConfigManager.get_instance()
                config = config_manager.load()
                
                # 验证 source：合并时应该优先使用 project（因为项目配置优先）
                self.assertEqual(config.source, "project")

    def test_config_source_default(self):
        """测试默认配置时的 source"""
        with patch("eflycode.core.config.config_manager.find_config_files") as mock_find:
            mock_find.return_value = (
                None,  # 无用户配置
                None,  # 无项目配置
                Path.cwd(),
            )
            
            config_manager = ConfigManager.get_instance()
            config = config_manager.load()
            
            # 验证 source
            self.assertEqual(config.source, "default")

    def test_get_all_model_entries_source(self):
        """测试模型条目的 source 属性"""
        with tempfile.TemporaryDirectory() as tmpdir:
            user_config_dir = Path(tmpdir) / "user" / ".eflycode"
            user_config_dir.mkdir(parents=True)
            user_config_file = user_config_dir / "config.yaml"
            
            project_config_file = Path(tmpdir) / ".eflycode" / "config.yaml"
            project_config_file.parent.mkdir(parents=True)
            
            # 创建用户配置
            user_config_file.write_text("""
model:
  entries:
    - model: gpt-4
      api_key: sk-user123
    - model: gpt-3.5-turbo
      api_key: sk-user456
""")
            
            # 创建项目配置（覆盖 gpt-4）
            project_config_file.write_text("""
model:
  entries:
    - model: gpt-4
      api_key: sk-project123
""")
            
            with patch("eflycode.core.config.config_manager.find_config_files") as mock_find:
                mock_find.return_value = (
                    user_config_file,
                    project_config_file,
                    Path(tmpdir),
                )
                
                config_manager = ConfigManager.get_instance()
                entries = config_manager.get_all_model_entries()
                
                # 验证所有条目都有 source
                for entry in entries:
                    self.assertIn("_source", entry)
                    self.assertIn(entry["_source"], ["user", "project"])
                
                # 验证项目配置的条目 source 为 "project"
                gpt4_entry = next(
                    (e for e in entries if e.get("model") == "gpt-4"), None
                )
                self.assertIsNotNone(gpt4_entry)
                self.assertEqual(gpt4_entry["_source"], "project")
                
                # 验证用户配置的条目 source 为 "user"
                gpt35_entry = next(
                    (e for e in entries if e.get("model") == "gpt-3.5-turbo"), None
                )
                self.assertIsNotNone(gpt35_entry)
                self.assertEqual(gpt35_entry["_source"], "user")

    def test_get_model_entry_source(self):
        """测试获取模型条目来源"""
        config_manager = ConfigManager.get_instance()
        
        # 测试用户来源
        user_entry = {"model": "gpt-4", "_source": "user"}
        self.assertEqual(
            config_manager.get_model_entry_source(user_entry), "user"
        )
        
        # 测试项目来源
        project_entry = {"model": "gpt-4", "_source": "project"}
        self.assertEqual(
            config_manager.get_model_entry_source(project_entry), "project"
        )
        
        # 测试默认来源（无 _source）
        default_entry = {"model": "gpt-4"}
        self.assertEqual(
            config_manager.get_model_entry_source(default_entry), "user"
        )


if __name__ == "__main__":
    unittest.main()

