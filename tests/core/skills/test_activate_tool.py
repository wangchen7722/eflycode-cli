"""测试激活技能工具"""

import tempfile
import unittest
from pathlib import Path

from eflycode.core.skills.activate_tool import ActivateSkillTool
from eflycode.core.skills.manager import SkillsManager


class TestActivateSkillTool(unittest.TestCase):
    """测试 ActivateSkillTool"""

    def setUp(self):
        """设置测试环境"""
        self.test_dir = tempfile.mkdtemp()
        self.user_config_dir = Path(self.test_dir) / "user" / ".eflycode"
        self.project_workspace_dir = Path(self.test_dir) / "project"
        self.user_config_dir.mkdir(parents=True)
        self.project_workspace_dir.mkdir(parents=True)

        # 重置单例
        SkillsManager.reset_instance()

        # 初始化管理器
        self.manager = SkillsManager.get_instance()
        self.manager.initialize(
            user_config_dir=self.user_config_dir,
            project_workspace_dir=self.project_workspace_dir,
        )

        # 创建工具
        self.tool = ActivateSkillTool()

    def tearDown(self):
        """清理测试环境"""
        SkillsManager.reset_instance()
        import shutil

        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_skill_file(
        self, dir_path: Path, name: str, description: str, content: str = "# Test"
    ):
        """创建技能文件"""
        skill_dir = dir_path / "skills"
        skill_dir.mkdir(parents=True, exist_ok=True)
        file_path = skill_dir / f"{name}.md"
        full_content = f"""---
description: {description}
---

{content}
"""
        file_path.write_text(full_content, encoding="utf-8")

    def test_tool_properties(self):
        """测试工具属性"""
        self.assertEqual(self.tool.name, "activate_skill")
        self.assertEqual(self.tool.type, "function")
        self.assertEqual(self.tool.permission, "read")

    def test_description_with_no_skills(self):
        """测试没有技能时的描述"""
        description = self.tool.description
        self.assertIn("没有可用的技能", description)

    def test_description_with_skills(self):
        """测试有技能时的描述"""
        self._create_skill_file(self.user_config_dir, "skill1", "技能1")
        self._create_skill_file(self.user_config_dir, "skill2", "技能2")

        self.manager.reload_skills()

        description = self.tool.description
        self.assertIn("skill1", description)
        self.assertIn("skill2", description)

    def test_parameters_with_no_skills(self):
        """测试没有技能时的参数"""
        params = self.tool.parameters
        self.assertEqual(params.type, "object")
        self.assertIn("skill_name", params.properties)
        self.assertNotIn("enum", params.properties["skill_name"])

    def test_parameters_with_skills(self):
        """测试有技能时的参数"""
        self._create_skill_file(self.user_config_dir, "skill1", "技能1")
        self._create_skill_file(self.user_config_dir, "skill2", "技能2")

        self.manager.reload_skills()

        params = self.tool.parameters
        self.assertEqual(params.type, "object")
        self.assertIn("skill_name", params.properties)
        self.assertIn("enum", params.properties["skill_name"])
        self.assertEqual(params.properties["skill_name"]["enum"], ["skill1", "skill2"])

    def test_parameters_with_disabled_skill(self):
        """测试禁用的技能不在 enum 中"""
        self._create_skill_file(self.user_config_dir, "skill1", "技能1")
        self._create_skill_file(self.user_config_dir, "skill2", "技能2")

        self.manager.reload_skills()
        self.manager.disable_skill("skill2")

        params = self.tool.parameters
        enum_values = params.properties["skill_name"]["enum"]
        self.assertEqual(enum_values, ["skill1"])
        self.assertNotIn("skill2", enum_values)

    def test_activate_skill(self):
        """测试激活技能"""
        self._create_skill_file(
            self.user_config_dir, "test-skill", "测试技能", "# Instructions\n\nDo this"
        )

        self.manager.reload_skills()

        result = self.tool.run(skill_name="test-skill")

        self.assertIn("<activated_skill", result)
        self.assertIn('name="test-skill"', result)
        self.assertIn("<instructions>", result)
        self.assertIn("# Instructions", result)
        self.assertIn("Do this", result)
        self.assertIn("<location>", result)

    def test_activate_nonexistent_skill(self):
        """测试激活不存在的技能"""
        result = self.tool.run(skill_name="nonexistent")
        self.assertIn("错误", result)
        self.assertIn("不存在", result)

    def test_activate_disabled_skill(self):
        """测试激活已禁用的技能"""
        self._create_skill_file(
            self.user_config_dir, "test-skill", "测试技能", "# Instructions"
        )

        self.manager.reload_skills()
        self.manager.disable_skill("test-skill")

        result = self.tool.run(skill_name="test-skill")
        self.assertIn("错误", result)

    def test_xml_escaping(self):
        """测试 XML 转义"""
        self._create_skill_file(
            self.user_config_dir,
            "test-skill",
            "测试技能",
            'Use <tag> & "quotes"',
        )

        self.manager.reload_skills()

        result = self.tool.run(skill_name="test-skill")

        # 检查特殊字符被转义
        self.assertIn("&lt;tag&gt;", result)
        self.assertIn("&amp;", result)
        self.assertIn("&quot;", result)

    def test_escape_xml_method(self):
        """测试 _escape_xml 方法"""
        test_cases = [
            ("<", "&lt;"),
            (">", "&gt;"),
            ("&", "&amp;"),
            ('"', "&quot;"),
            ("'", "&apos;"),
            ("<tag> & 'quote'", "&lt;tag&gt; &amp; &apos;quote&apos;"),
        ]

        for input_text, expected in test_cases:
            result = self.tool._escape_xml(input_text)
            self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
