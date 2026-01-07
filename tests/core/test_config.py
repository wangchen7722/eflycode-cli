"""配置管理模块测试用例"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from eflycode.core.config import (
    Config,
    find_config_file,
    load_config_from_file,
    parse_model_config,
    get_model_name_from_config,
    load_config,
)


class TestConfig(unittest.TestCase):
    """配置管理测试类"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_home = os.environ.get("HOME")
        os.environ["HOME"] = self.temp_dir

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir)
        if self.original_home:
            os.environ["HOME"] = self.original_home
        elif "HOME" in os.environ:
            del os.environ["HOME"]

    def test_find_config_file_in_current_dir(self):
        """测试在当前目录查找配置文件"""
        # 创建 .eflycode 目录和配置文件
        config_dir = Path(self.temp_dir) / ".eflycode"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text("model:\n  default: gpt-4\n  entries:\n    - model: gpt-4\n")

        # 切换到临时目录
        original_cwd = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            config_path, workspace_dir = find_config_file()
            self.assertIsNotNone(config_path)
            self.assertIsNotNone(workspace_dir)
            self.assertTrue(config_path.exists())
            self.assertEqual(workspace_dir, Path(self.temp_dir).resolve())
        finally:
            os.chdir(original_cwd)

    def test_find_config_file_in_parent(self):
        """测试在父目录查找配置文件"""
        # 在父目录创建配置
        parent_dir = Path(self.temp_dir) / "parent"
        parent_dir.mkdir()
        config_dir = parent_dir / ".eflycode"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text("model:\n  default: gpt-4\n  entries:\n    - model: gpt-4\n")

        # 在子目录中查找
        child_dir = parent_dir / "child"
        child_dir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(child_dir)
            config_path, workspace_dir = find_config_file()
            self.assertIsNotNone(config_path)
            self.assertIsNotNone(workspace_dir)
            self.assertEqual(config_path.parent.parent, parent_dir.resolve())
            self.assertEqual(workspace_dir, parent_dir.resolve())
        finally:
            os.chdir(original_cwd)

    @patch('pathlib.Path.home')
    def test_find_config_file_in_home(self, mock_home):
        """测试在用户目录查找配置文件"""
        # 在用户目录创建配置
        home_config_dir = Path(self.temp_dir) / ".eflycode"
        home_config_dir.mkdir()
        home_config_file = home_config_dir / "config.yaml"
        home_config_file.write_text("model:\n  default: gpt-4\n  entries:\n    - model: gpt-4\n")

        # 模拟 Path.home() 返回临时目录
        mock_home.return_value = Path(self.temp_dir)

        # 创建一个独立的目录，确保向上查找时不会找到配置
        import tempfile as tf
        other_base = tf.mkdtemp()
        other_dir = Path(other_base) / "other"
        other_dir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(other_dir)
            # 确保当前目录已切换
            current_dir = Path.cwd().resolve()
            self.assertEqual(current_dir, other_dir.resolve(), "测试环境：当前目录应该是 other_dir")
            
            config_path, workspace_dir = find_config_file()
            self.assertIsNotNone(config_path)
            self.assertIsNotNone(workspace_dir)
            self.assertEqual(config_path.parent, home_config_dir)
            # 用户目录的配置，工作区目录应该是当前执行目录
            expected_workspace = Path.cwd().resolve()
            self.assertEqual(workspace_dir, expected_workspace, 
                           f"工作区目录应该是当前目录 {expected_workspace}，但得到 {workspace_dir}")
        finally:
            os.chdir(original_cwd)
            import shutil
            shutil.rmtree(other_base)

    def test_load_config_from_file(self):
        """测试从文件加载配置"""
        config_file = Path(self.temp_dir) / "config.yaml"
        config_file.write_text("""
model:
  default: gpt-4
  entries:
    - model: gpt-4
      api_key: test_key
workspace: /tmp/test
""")

        config = load_config_from_file(config_file)

        self.assertIsNotNone(config)
        self.assertEqual(config.get("model", {}).get("default"), "gpt-4")
        self.assertEqual(config.get("workspace"), "/tmp/test")

    def test_parse_model_config(self):
        """测试解析模型配置"""
        config = {
            "model": {
                "default": "gpt-4",
                "entries": [
                    {
                        "model": "gpt-4",
                        "api_key": "test_key",
                        "base_url": "https://api.openai.com/v1",
                    }
                ],
            }
        }

        model_config = parse_model_config(config)

        self.assertEqual(model_config.api_key, "test_key")
        self.assertEqual(model_config.base_url, "https://api.openai.com/v1")

    def test_parse_model_config_with_env_key(self):
        """测试从环境变量读取 API key"""
        config = {
            "model": {
                "default": "gpt-4",
                "entries": [
                    {
                        "model": "gpt-4",
                    }
                ],
            }
        }

        os.environ["OPENAI_API_KEY"] = "env_key"

        try:
            model_config = parse_model_config(config)
            self.assertEqual(model_config.api_key, "env_key")
        finally:
            del os.environ["OPENAI_API_KEY"]

    def test_get_model_name_from_config(self):
        """测试从配置获取模型名称"""
        config = {
            "model": {
                "default": "gpt-4",
                "entries": [
                    {
                        "model": "gpt-4",
                    }
                ],
            }
        }

        model_name = get_model_name_from_config(config)

        self.assertEqual(model_name, "gpt-4")

    def test_get_model_name_default(self):
        """测试默认模型名称"""
        config = {}

        model_name = get_model_name_from_config(config)

        self.assertEqual(model_name, "gpt-4")  # 或其他默认值

    def test_load_config(self):
        """测试加载完整配置"""
        # 创建配置文件
        config_dir = Path(self.temp_dir) / ".eflycode"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text("""
model:
  default: gpt-4
  entries:
    - model: gpt-4
      api_key: test_key
workspace: /tmp/test
""")

        original_cwd = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            config = load_config()

            self.assertIsNotNone(config)
            self.assertIsInstance(config, Config)
            self.assertEqual(config.model_name, "gpt-4")
            self.assertEqual(config.workspace_dir, Path(self.temp_dir).resolve())
        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    unittest.main()

