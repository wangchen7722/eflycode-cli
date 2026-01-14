"""测试技能加载器"""

import os
import tempfile
import unittest
from pathlib import Path

from eflycode.core.skills.loader import SkillLoader, parse_frontmatter
from eflycode.core.skills.models import SkillManifest


class TestParseFrontmatter(unittest.TestCase):
    """测试 frontmatter 解析"""

    def test_parse_valid_frontmatter(self):
        """测试解析有效的 frontmatter"""
        content = """---
description: 这是一个测试技能
tags:
  - test
  - example
---

# 技能内容

这是正文部分
"""
        frontmatter, body = parse_frontmatter(content)

        self.assertIsNotNone(frontmatter)
        self.assertEqual(frontmatter["description"], "这是一个测试技能")
        self.assertEqual(frontmatter["tags"], ["test", "example"])
        self.assertIn("# 技能内容", body)
        self.assertIn("这是正文部分", body)

    def test_parse_no_frontmatter(self):
        """测试没有 frontmatter 的情况"""
        content = "# 技能内容\n\n这是正文部分"
        frontmatter, body = parse_frontmatter(content)

        self.assertIsNone(frontmatter)
        self.assertEqual(body, content)

    def test_parse_empty_frontmatter(self):
        """测试空的 frontmatter"""
        content = """---
---

# 技能内容
"""
        frontmatter, body = parse_frontmatter(content)

        self.assertIsNotNone(frontmatter)
        self.assertEqual(body, "# 技能内容")

    def test_parse_frontmatter_with_windows_line_endings(self):
        """测试 Windows 行结尾"""
        content = "---\r\ndescription: test\r\n---\r\n\r\n# Content\r\n"
        frontmatter, body = parse_frontmatter(content)

        self.assertIsNotNone(frontmatter)
        self.assertEqual(frontmatter["description"], "test")
        self.assertIn("# Content", body)

    def test_parse_invalid_yaml(self):
        """测试无效的 YAML"""
        content = """---
description: test
  invalid: yaml
    structure
---

# Content
"""
        frontmatter, body = parse_frontmatter(content)

        # YAML 解析失败，应该返回 None
        self.assertIsNone(frontmatter)
        self.assertEqual(body, content)


class TestSkillLoader(unittest.TestCase):
    """测试技能加载器"""

    def setUp(self):
        """设置测试环境"""
        self.test_dir = tempfile.mkdtemp()
        self.user_skills_dir = Path(self.test_dir) / "user" / "skills"
        self.project_skills_dir = Path(self.test_dir) / "project" / "skills"
        self.user_skills_dir.mkdir(parents=True)
        self.project_skills_dir.mkdir(parents=True)

    def tearDown(self):
        """清理测试环境"""
        import shutil

        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_skill_file(self, dir_path: Path, name: str, description: str, content: str = "# Test"):
        """创建技能文件

        Args:
            dir_path: 技能目录
            name: 技能名称（不含 .md）
            description: 技能描述
            content: 技能内容
        """
        file_path = dir_path / f"{name}.md"
        full_content = f"""---
description: {description}
---

{content}
"""
        file_path.write_text(full_content, encoding="utf-8")

    def test_scan_empty_directory(self):
        """测试扫描空目录"""
        loader = SkillLoader(
            user_skills_dir=self.user_skills_dir,
            project_skills_dir=self.project_skills_dir,
        )

        skills = loader.scan_skills()
        self.assertEqual(len(skills), 0)

    def test_scan_user_skills(self):
        """测试扫描用户技能"""
        self._create_skill_file(
            self.user_skills_dir, "test-skill", "测试技能", "# Test Skill\n\n这是测试"
        )

        loader = SkillLoader(
            user_skills_dir=self.user_skills_dir,
            project_skills_dir=None,
        )

        skills = loader.scan_skills()
        self.assertEqual(len(skills), 1)

        skill = skills["test-skill"]
        self.assertEqual(skill.name, "test-skill")
        self.assertEqual(skill.description, "测试技能")
        self.assertEqual(skill.source, "user")
        self.assertIn("# Test Skill", skill.content)

    def test_scan_project_skills_override(self):
        """测试项目技能覆盖用户技能"""
        # 创建同名技能
        self._create_skill_file(
            self.user_skills_dir, "common-skill", "用户技能描述", "# User Skill"
        )
        self._create_skill_file(
            self.project_skills_dir, "common-skill", "项目技能描述", "# Project Skill"
        )

        loader = SkillLoader(
            user_skills_dir=self.user_skills_dir,
            project_skills_dir=self.project_skills_dir,
        )

        skills = loader.scan_skills()
        self.assertEqual(len(skills), 1)

        skill = skills["common-skill"]
        # 应该是项目技能（覆盖用户技能）
        self.assertEqual(skill.source, "project")
        self.assertEqual(skill.description, "项目技能描述")
        self.assertIn("# Project Skill", skill.content)

    def test_scan_multiple_skills(self):
        """测试扫描多个技能"""
        self._create_skill_file(self.user_skills_dir, "skill1", "技能1")
        self._create_skill_file(self.user_skills_dir, "skill2", "技能2")
        self._create_skill_file(self.user_skills_dir, "skill3", "技能3")

        loader = SkillLoader(
            user_skills_dir=self.user_skills_dir,
            project_skills_dir=None,
        )

        skills = loader.scan_skills()
        self.assertEqual(len(skills), 3)
        self.assertIn("skill1", skills)
        self.assertIn("skill2", skills)
        self.assertIn("skill3", skills)

    def test_skip_skill_without_description(self):
        """测试跳过没有 description 的技能"""
        file_path = self.user_skills_dir / "invalid-skill.md"
        file_path.write_text(
            """---
name: invalid-skill
---

# Content
""",
            encoding="utf-8",
        )

        loader = SkillLoader(
            user_skills_dir=self.user_skills_dir,
            project_skills_dir=None,
        )

        skills = loader.scan_skills()
        self.assertEqual(len(skills), 0)

    def test_skip_skill_without_frontmatter(self):
        """测试跳过没有 frontmatter 的技能"""
        file_path = self.user_skills_dir / "no-frontmatter.md"
        file_path.write_text("# Just markdown content", encoding="utf-8")

        loader = SkillLoader(
            user_skills_dir=self.user_skills_dir,
            project_skills_dir=None,
        )

        skills = loader.scan_skills()
        self.assertEqual(len(skills), 0)

    def test_skip_non_markdown_files(self):
        """测试跳过非 .md 文件"""
        (self.user_skills_dir / "test.txt").write_text("not a skill file")
        (self.user_skills_dir / "test.json").write_text("{}")

        loader = SkillLoader(
            user_skills_dir=self.user_skills_dir,
            project_skills_dir=None,
        )

        skills = loader.scan_skills()
        self.assertEqual(len(skills), 0)

    def test_detect_changes_new_skills(self):
        """测试检测新技能"""
        self._create_skill_file(self.user_skills_dir, "new-skill", "新技能")

        loader = SkillLoader(
            user_skills_dir=self.user_skills_dir,
            project_skills_dir=None,
        )

        new_skills = loader.scan_skills()
        changes = loader.detect_changes(new_skills, old_manifest=None)

        self.assertTrue(changes.has_changes)
        self.assertEqual(len(changes.added), 1)
        self.assertEqual(changes.added[0].name, "new-skill")
        self.assertEqual(len(changes.modified), 0)
        self.assertEqual(len(changes.removed), 0)

    def test_detect_changes_modified_skills(self):
        """测试检测修改的技能"""
        # 创建初始技能
        self._create_skill_file(self.user_skills_dir, "test-skill", "原始描述")

        loader = SkillLoader(
            user_skills_dir=self.user_skills_dir,
            project_skills_dir=None,
        )

        # 第一次扫描
        new_skills = loader.scan_skills()
        changes = loader.detect_changes(new_skills, old_manifest=None)
        self.assertEqual(len(changes.added), 1)

        # 创建清单
        manifest = SkillManifest()
        for skill in new_skills.values():
            manifest.add_skill(skill)

        # 修改技能文件
        import time

        time.sleep(0.01)  # 确保_mtime 变化
        self._create_skill_file(self.user_skills_dir, "test-skill", "修改后的描述")

        # 重新扫描
        new_skills = loader.scan_skills()
        changes = loader.detect_changes(new_skills, old_manifest=manifest)

        self.assertEqual(len(changes.added), 0)
        self.assertEqual(len(changes.modified), 1)
        self.assertEqual(changes.modified[0].name, "test-skill")
        self.assertEqual(changes.modified[0].description, "修改后的描述")

    def test_detect_changes_removed_skills(self):
        """测试检测删除的技能"""
        # 创建初始技能
        self._create_skill_file(self.user_skills_dir, "test-skill", "测试技能")

        loader = SkillLoader(
            user_skills_dir=self.user_skills_dir,
            project_skills_dir=None,
        )

        # 第一次扫描
        new_skills = loader.scan_skills()
        manifest = SkillManifest()
        for skill in new_skills.values():
            manifest.add_skill(skill)

        # 删除技能文件
        (self.user_skills_dir / "test-skill.md").unlink()

        # 重新扫描
        new_skills = loader.scan_skills()
        changes = loader.detect_changes(new_skills, old_manifest=manifest)

        self.assertEqual(len(changes.added), 0)
        self.assertEqual(len(changes.modified), 0)
        self.assertEqual(len(changes.removed), 1)
        self.assertEqual(changes.removed[0].name, "test-skill")

    def test_nonexistent_directory(self):
        """测试不存在的目录"""
        loader = SkillLoader(
            user_skills_dir=Path("/nonexistent/user/skills"),
            project_skills_dir=Path("/nonexistent/project/skills"),
        )

        skills = loader.scan_skills()
        self.assertEqual(len(skills), 0)


if __name__ == "__main__":
    unittest.main()
