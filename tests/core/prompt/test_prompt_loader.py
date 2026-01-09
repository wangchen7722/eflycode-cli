"""PromptLoader 测试用例"""

import tempfile
import unittest
from pathlib import Path

from eflycode.core.prompt.loader import PromptLoader


class TestPromptLoader(unittest.TestCase):
    """PromptLoader 测试类"""

    def setUp(self):
        """设置测试环境"""
        self.loader = PromptLoader.get_instance()

    def test_load_default_template(self):
        """测试加载默认模板"""
        template = self.loader.load_template("default")

        self.assertIsNotNone(template)
        self.assertIsInstance(template, str)
        self.assertIn("代码助手", template)

    def test_load_nonexistent_role(self):
        """测试加载不存在的角色模板"""
        template = self.loader.load_template("nonexistent-role")

        # 应该回退到默认模板
        self.assertIsNotNone(template)
        self.assertIn("代码助手", template)

    def test_load_user_template(self):
        """测试加载用户配置模板"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_dir = Path(tmpdir)
            agent_dir = workspace_dir / ".eflycode" / "agents" / "test-role"
            agent_dir.mkdir(parents=True, exist_ok=True)

            user_template = "这是用户自定义的提示词模板\n工作区：{{ workspace.path }}"
            template_path = agent_dir / "system.prompt"
            template_path.write_text(user_template, encoding="utf-8")

            template = self.loader.load_template("test-role", workspace_dir)

            self.assertIsNotNone(template)
            self.assertEqual(template, user_template)

    def test_load_user_template_priority(self):
        """测试用户模板优先级高于内置模板"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_dir = Path(tmpdir)
            agent_dir = workspace_dir / ".eflycode" / "agents" / "default"
            agent_dir.mkdir(parents=True, exist_ok=True)

            user_template = "用户自定义的默认模板"
            template_path = agent_dir / "system.prompt"
            template_path.write_text(user_template, encoding="utf-8")

            template = self.loader.load_template("default", workspace_dir)

            self.assertEqual(template, user_template)

    def test_render_template(self):
        """测试渲染模板"""
        template = "Hello {{ name }}, you have {{ count }} items."
        variables = {"name": "Alice", "count": 5}

        result = self.loader.render(template, variables)

        self.assertEqual(result, "Hello Alice, you have 5 items.")

    def test_render_template_with_loop(self):
        """测试渲染带循环的模板"""
        template = """Items:
{% for item in items %}
- {{ item }}
{% endfor %}"""
        variables = {"items": ["apple", "banana", "cherry"]}

        result = self.loader.render(template, variables)

        self.assertIn("apple", result)
        self.assertIn("banana", result)
        self.assertIn("cherry", result)

    def test_render_template_with_filter(self):
        """测试渲染带过滤器的模板"""
        template = "Count: {{ items|length }}"
        variables = {"items": [1, 2, 3, 4, 5]}

        result = self.loader.render(template, variables)

        self.assertEqual(result, "Count: 5")

    def test_render_template_undefined_variable(self):
        """测试渲染时未定义变量"""
        template = "Hello {{ name }}"
        variables = {}  # 缺少 name 变量

        result = self.loader.render(template, variables)

        # 应该返回空字符串（因为使用了 StrictUndefined）
        self.assertEqual(result, "")

    def test_render_template_invalid_syntax(self):
        """测试渲染无效语法的模板"""
        template = "Hello {% if %} invalid syntax {% endif %}"
        variables = {}

        result = self.loader.render(template, variables)

        # 应该返回空字符串
        self.assertEqual(result, "")

    def test_render_template_nested_variables(self):
        """测试渲染嵌套变量"""
        template = "System: {{ system.version }}, OS: {{ environment.os }}"
        variables = {
            "system": {"version": "1.0.0"},
            "environment": {"os": "Linux"},
        }

        result = self.loader.render(template, variables)

        self.assertIn("1.0.0", result)
        self.assertIn("Linux", result)

    def test_load_template_encoding_error(self):
        """测试加载模板时的编码错误处理"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_dir = Path(tmpdir)
            agent_dir = workspace_dir / ".eflycode" / "agents" / "test-role"
            agent_dir.mkdir(parents=True, exist_ok=True)

            # 创建一个无法用 UTF-8 读取的文件（模拟错误）
            template_path = agent_dir / "system.prompt"
            # 这里我们创建一个正常文件，但测试会回退到默认模板
            template_path.write_bytes(b"\xff\xfe")  # 无效的 UTF-8

            template = self.loader.load_template("test-role", workspace_dir)

            # 应该回退到默认模板
            self.assertIsNotNone(template)

