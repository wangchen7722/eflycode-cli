"""配置管理模块测试用例"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from eflycode.core.config import (
    Config,
    ConfigManager,
    find_config_files,
    load_config_from_file,
    parse_model_config,
    get_model_name_from_config,
)
from eflycode.core.config.config_manager import (
    _deep_merge,
    _merge_entries_by_key,
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
            user_config, project_config, workspace_dir = find_config_files()
            config_path = project_config or user_config
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
            user_config, project_config, workspace_dir = find_config_files()
            config_path = project_config or user_config
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
            
            user_config, project_config, workspace_dir = find_config_files()
            config_path = project_config or user_config
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
            # 重置单例以测试新配置
            ConfigManager._instance = None
            config = ConfigManager.get_instance().load()

            self.assertIsNotNone(config)
            self.assertIsInstance(config, Config)
            self.assertEqual(config.model_name, "gpt-4")
            self.assertEqual(config.workspace_dir, Path(self.temp_dir).resolve())
        finally:
            os.chdir(original_cwd)


class TestConfigMerge(unittest.TestCase):
    """配置合并测试类"""

    def test_merge_entries_by_key_basic(self):
        """测试按 key 合并列表的基本功能"""
        base = [
            {"model": "gpt-4", "api_key": "user-key-1"},
            {"model": "gpt-3.5", "api_key": "user-key-2"},
        ]
        override = [
            {"model": "claude", "api_key": "project-key"},
            {"model": "gpt-4", "api_key": "project-key-override"},
        ]

        result = _merge_entries_by_key(base, override, "model")

        # 检查结果包含所有模型
        model_names = [e["model"] for e in result]
        self.assertIn("gpt-4", model_names)
        self.assertIn("gpt-3.5", model_names)
        self.assertIn("claude", model_names)

        # 检查 gpt-4 被覆盖
        gpt4_entry = next(e for e in result if e["model"] == "gpt-4")
        self.assertEqual(gpt4_entry["api_key"], "project-key-override")

        # 检查 gpt-3.5 保留用户配置
        gpt35_entry = next(e for e in result if e["model"] == "gpt-3.5")
        self.assertEqual(gpt35_entry["api_key"], "user-key-2")

    def test_merge_entries_empty_base(self):
        """测试基础列表为空时的合并"""
        base = []
        override = [{"model": "claude", "api_key": "key"}]

        result = _merge_entries_by_key(base, override, "model")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["model"], "claude")

    def test_merge_entries_empty_override(self):
        """测试覆盖列表为空时的合并"""
        base = [{"model": "gpt-4", "api_key": "key"}]
        override = []

        result = _merge_entries_by_key(base, override, "model")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["model"], "gpt-4")

    def test_deep_merge_basic(self):
        """测试深度合并的基本功能"""
        base = {
            "model": {
                "default": "gpt-4",
                "entries": [{"model": "gpt-4", "api_key": "user-key"}],
            },
            "context": {"strategy": "summary"},
        }
        override = {
            "model": {
                "default": "claude",
                "entries": [{"model": "claude", "api_key": "project-key"}],
            },
        }

        result = _deep_merge(base, override)

        # 检查 default 被覆盖
        self.assertEqual(result["model"]["default"], "claude")

        # 检查 entries 被智能合并
        entries = result["model"]["entries"]
        model_names = [e["model"] for e in entries]
        self.assertIn("gpt-4", model_names)
        self.assertIn("claude", model_names)

        # 检查 context 保留
        self.assertEqual(result["context"]["strategy"], "summary")

    def test_deep_merge_nested_dict(self):
        """测试嵌套字典的深度合并"""
        base = {
            "level1": {
                "level2": {
                    "key1": "value1",
                    "key2": "value2",
                }
            }
        }
        override = {
            "level1": {
                "level2": {
                    "key2": "override2",
                    "key3": "value3",
                }
            }
        }

        result = _deep_merge(base, override)

        self.assertEqual(result["level1"]["level2"]["key1"], "value1")
        self.assertEqual(result["level1"]["level2"]["key2"], "override2")
        self.assertEqual(result["level1"]["level2"]["key3"], "value3")

    def test_deep_merge_override_wins(self):
        """测试非字典/非 entries 列表时覆盖值优先"""
        base = {"key": "base_value", "list": [1, 2, 3]}
        override = {"key": "override_value", "list": [4, 5]}

        result = _deep_merge(base, override)

        self.assertEqual(result["key"], "override_value")
        self.assertEqual(result["list"], [4, 5])


class TestFindConfigFiles(unittest.TestCase):
    """查找配置文件测试类"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_home = os.environ.get("HOME")

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir)
        if self.original_home:
            os.environ["HOME"] = self.original_home
        elif "HOME" in os.environ:
            del os.environ["HOME"]

    @patch('pathlib.Path.home')
    def test_find_both_configs(self, mock_home):
        """测试同时存在用户配置和项目配置"""
        # 创建用户配置
        user_home = Path(self.temp_dir) / "home"
        user_home.mkdir()
        user_config_dir = user_home / ".eflycode"
        user_config_dir.mkdir()
        user_config = user_config_dir / "config.yaml"
        user_config.write_text("model:\n  default: gpt-4\n")

        # 创建项目配置
        project_dir = Path(self.temp_dir) / "project"
        project_dir.mkdir()
        project_config_dir = project_dir / ".eflycode"
        project_config_dir.mkdir()
        project_config = project_config_dir / "config.yaml"
        project_config.write_text("model:\n  default: claude\n")

        mock_home.return_value = user_home

        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            user_path, project_path, workspace = find_config_files()

            self.assertIsNotNone(user_path)
            self.assertIsNotNone(project_path)
            self.assertEqual(user_path.resolve(), user_config.resolve())
            self.assertEqual(project_path.resolve(), project_config.resolve())
            self.assertEqual(workspace, project_dir.resolve())
        finally:
            os.chdir(original_cwd)

    @patch('pathlib.Path.home')
    def test_find_only_user_config(self, mock_home):
        """测试只存在用户配置"""
        # 创建用户配置
        user_home = Path(self.temp_dir) / "home"
        user_home.mkdir()
        user_config_dir = user_home / ".eflycode"
        user_config_dir.mkdir()
        user_config = user_config_dir / "config.yaml"
        user_config.write_text("model:\n  default: gpt-4\n")

        # 创建项目目录（无配置）
        project_dir = Path(self.temp_dir) / "project"
        project_dir.mkdir()

        mock_home.return_value = user_home

        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            user_path, project_path, workspace = find_config_files()

            self.assertIsNotNone(user_path)
            self.assertIsNone(project_path)
            self.assertEqual(user_path.resolve(), user_config.resolve())
        finally:
            os.chdir(original_cwd)


class TestConfigMergeIntegration(unittest.TestCase):
    """配置合并集成测试类"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_home = os.environ.get("HOME")

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir)
        if self.original_home:
            os.environ["HOME"] = self.original_home
        elif "HOME" in os.environ:
            del os.environ["HOME"]
        # 重置单例
        ConfigManager._instance = None

    @patch('pathlib.Path.home')
    def test_config_merge_integration(self, mock_home):
        """测试配置合并的完整流程"""
        # 创建用户配置
        user_home = Path(self.temp_dir) / "home"
        user_home.mkdir()
        user_config_dir = user_home / ".eflycode"
        user_config_dir.mkdir()
        user_config = user_config_dir / "config.yaml"
        user_config.write_text("""
model:
  default: gpt-4
  entries:
    - model: gpt-4
      api_key: user-key-1
    - model: gpt-3.5
      api_key: user-key-2
context:
  strategy: summary
""")

        # 创建项目配置
        project_dir = Path(self.temp_dir) / "project"
        project_dir.mkdir()
        project_config_dir = project_dir / ".eflycode"
        project_config_dir.mkdir()
        project_config = project_config_dir / "config.yaml"
        project_config.write_text("""
model:
  default: claude
  entries:
    - model: claude
      api_key: project-key
    - model: gpt-4
      api_key: project-key-override
""")

        mock_home.return_value = user_home

        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            ConfigManager._instance = None
            config = ConfigManager.get_instance().load()

            # 项目配置的 default 应该覆盖用户配置
            self.assertEqual(config.model_name, "claude")

            # 工作区应该是项目目录
            self.assertEqual(config.workspace_dir, project_dir.resolve())

            # context 应该保留用户配置
            self.assertIsNotNone(config.context_config)
            self.assertEqual(config.context_config.strategy_type, "summary")
        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    unittest.main()

