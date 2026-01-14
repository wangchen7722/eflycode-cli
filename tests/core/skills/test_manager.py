"""测试技能管理器"""

import json
import tempfile
import unittest
from pathlib import Path

from eflycode.core.skills.manager import SkillsManager
from eflycode.core.skills.models import SkillMetadata


class TestSkillsManager(unittest.TestCase):
    """测试 SkillsManager"""

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

    def test_singleton(self):
        """测试单例模式"""
        manager1 = SkillsManager.get_instance()
        manager2 = SkillsManager.get_instance()
        self.assertIs(manager1, manager2)

    def test_initialize_creates_directories(self):
        """测试初始化创建目录"""
        self.assertTrue((self.user_config_dir / "skills").exists())
        self.assertTrue((self.project_workspace_dir / ".eflycode" / "skills").exists())

    def test_initialize_with_empty_project(self):
        """测试项目目录为 None 的情况"""
        SkillsManager.reset_instance()
        manager = SkillsManager.get_instance()
        manager.initialize(user_config_dir=self.user_config_dir, project_workspace_dir=None)

        self.assertIsNone(manager.project_skills_dir)
        self.assertIsNotNone(manager.user_skills_dir)

    def test_load_empty_manifest(self):
        """测试加载空清单"""
        self.assertEqual(len(self.manager.manifest.skills), 0)
        self.assertEqual(len(self.manager.skills_cache), 0)

    def test_reload_skills_discovers_new_skills(self):
        """测试重新扫描发现新技能"""
        # 创建技能文件
        self._create_skill_file(self.user_config_dir, "test-skill", "测试技能")

        # 重新扫描
        changes = self.manager.reload_skills()

        # 验证变更
        self.assertTrue(changes.has_changes)
        self.assertEqual(len(changes.added), 1)
        self.assertEqual(changes.added[0].name, "test-skill")

        # 验证缓存
        self.assertIn("test-skill", self.manager.skills_cache)

    def test_reload_skills_detects_removed_skills(self):
        """测试重新扫描检测删除的技能"""
        # 创建技能文件
        skill_path = (
            self.user_config_dir / "skills" / "test-skill.md"
        )
        skill_path.parent.mkdir(parents=True, exist_ok=True)
        skill_path.write_text(
            "---\ndescription: test\n---\n# Test", encoding="utf-8"
        )

        # 第一次扫描
        self.manager.reload_skills()
        self.assertIn("test-skill", self.manager.skills_cache)

        # 删除技能文件
        skill_path.unlink()

        # 第二次扫描
        changes = self.manager.reload_skills()

        # 验证变更
        self.assertTrue(changes.has_changes)
        self.assertEqual(len(changes.removed), 1)
        self.assertEqual(changes.removed[0].name, "test-skill")

    def test_reload_skills_detects_modified_skills(self):
        """测试重新扫描检测修改的技能"""
        # 创建技能文件
        self._create_skill_file(self.user_config_dir, "test-skill", "原始描述")

        # 第一次扫描
        self.manager.reload_skills()
        original_skill = self.manager.skills_cache["test-skill"]
        original_description = original_skill.description

        # 修改技能文件
        import time

        time.sleep(0.01)  # 确保 mtime 变化
        self._create_skill_file(self.user_config_dir, "test-skill", "修改后的描述")

        # 第二次扫描
        changes = self.manager.reload_skills()

        # 验证变更
        self.assertTrue(changes.has_changes)
        self.assertEqual(len(changes.modified), 1)
        self.assertEqual(changes.modified[0].name, "test-skill")

        # 验证描述已更新
        updated_skill = self.manager.skills_cache["test-skill"]
        self.assertNotEqual(updated_skill.description, original_description)
        self.assertEqual(updated_skill.description, "修改后的描述")

    def test_get_enabled_skills(self):
        """测试获取启用的技能"""
        # 创建技能文件
        self._create_skill_file(self.user_config_dir, "skill1", "技能1")
        self._create_skill_file(self.user_config_dir, "skill2", "技能2")

        self.manager.reload_skills()

        # 默认都是启用的
        enabled = self.manager.get_enabled_skills()
        self.assertEqual(len(enabled), 2)

        # 禁用一个技能
        self.manager.disable_skill("skill1")

        enabled = self.manager.get_enabled_skills()
        self.assertEqual(len(enabled), 1)
        self.assertEqual(enabled[0].name, "skill2")

    def test_get_all_skills(self):
        """测试获取所有技能"""
        # 创建技能文件
        self._create_skill_file(self.user_config_dir, "skill1", "技能1")
        self._create_skill_file(self.user_config_dir, "skill2", "技能2")

        self.manager.reload_skills()

        all_skills = self.manager.get_all_skills()
        self.assertEqual(len(all_skills), 2)

    def test_get_skill_by_name(self):
        """测试根据名称获取技能"""
        self._create_skill_file(self.user_config_dir, "test-skill", "测试技能")
        self.manager.reload_skills()

        skill = self.manager.get_skill_by_name("test-skill")
        self.assertIsNotNone(skill)
        self.assertEqual(skill.name, "test-skill")
        self.assertEqual(skill.description, "测试技能")

        # 测试不存在的技能
        skill = self.manager.get_skill_by_name("nonexistent")
        self.assertIsNone(skill)

    def test_enable_skill(self):
        """测试启用技能"""
        self._create_skill_file(self.user_config_dir, "test-skill", "测试技能")
        self.manager.reload_skills()

        # 先禁用
        self.manager.disable_skill("test-skill")
        skill = self.manager.get_skill_by_name("test-skill")
        self.assertTrue(skill.disabled)

        # 再启用
        result = self.manager.enable_skill("test-skill")
        self.assertTrue(result)

        skill = self.manager.get_skill_by_name("test-skill")
        self.assertFalse(skill.disabled)

    def test_enable_nonexistent_skill(self):
        """测试启用不存在的技能"""
        result = self.manager.enable_skill("nonexistent")
        self.assertFalse(result)

    def test_disable_skill(self):
        """测试禁用技能"""
        self._create_skill_file(self.user_config_dir, "test-skill", "测试技能")
        self.manager.reload_skills()

        skill = self.manager.get_skill_by_name("test-skill")
        self.assertFalse(skill.disabled)

        result = self.manager.disable_skill("test-skill")
        self.assertTrue(result)

        skill = self.manager.get_skill_by_name("test-skill")
        self.assertTrue(skill.disabled)

    def test_disable_nonexistent_skill(self):
        """测试禁用不存在的技能"""
        result = self.manager.disable_skill("nonexistent")
        self.assertFalse(result)

    def test_manifest_persistence(self):
        """测试清单持久化"""
        # 创建技能
        self._create_skill_file(self.user_config_dir, "skill1", "技能1")
        self._create_skill_file(self.user_config_dir, "skill2", "技能2")

        self.manager.reload_skills()
        self.manager.disable_skill("skill1")

        # 验证清单文件存在
        manifest_path = self.user_config_dir / "skills.json"
        self.assertTrue(manifest_path.exists())

        # 读取清单文件
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(len(data["skills"]), 2)
        self.assertTrue(data["skills"]["skill1"]["disabled"])
        self.assertFalse(data["skills"]["skill2"]["disabled"])

    def test_get_available_skills_for_prompt(self):
        """测试获取用于提示词的技能列表"""
        self._create_skill_file(self.user_config_dir, "skill1", "描述1")
        self._create_skill_file(self.user_config_dir, "skill2", "描述2")

        self.manager.reload_skills()
        self.manager.disable_skill("skill2")

        available = self.manager.get_available_skills_for_prompt()

        self.assertEqual(len(available), 1)
        self.assertEqual(available[0]["name"], "skill1")
        self.assertEqual(available[0]["description"], "描述1")
        self.assertIn("location", available[0])

    def test_get_skill_content(self):
        """测试获取技能内容"""
        self._create_skill_file(
            self.user_config_dir, "test-skill", "测试技能", "# Test Skill\n\nContent here"
        )

        self.manager.reload_skills()

        content = self.manager.get_skill_content("test-skill")
        self.assertIsNotNone(content)
        self.assertIn("# Test Skill", content)
        self.assertIn("Content here", content)

    def test_project_skill_overrides_user_skill(self):
        """测试项目技能覆盖用户技能"""
        # 创建同名技能
        self._create_skill_file(self.user_config_dir, "common", "用户技能", "# User")
        # 项目技能目录是 <project>/.eflycode/skills
        self._create_skill_file(
            self.project_workspace_dir / ".eflycode",
            "common",
            "项目技能",
            "# Project",
        )

        self.manager.reload_skills()

        # 应该只有一个技能，且是项目技能
        self.assertEqual(len(self.manager.skills_cache), 1)

        skill = self.manager.get_skill_by_name("common")
        self.assertEqual(skill.source, "project")
        self.assertEqual(skill.description, "项目技能")

    def test_disabled_state_persists_across_reload(self):
        """测试禁用状态在重新扫描后保持"""
        # 创建技能
        self._create_skill_file(self.user_config_dir, "test-skill", "测试技能")

        self.manager.reload_skills()
        self.manager.disable_skill("test-skill")

        # 重新扫描
        self.manager.reload_skills()

        # 禁用状态应该保持
        skill = self.manager.get_skill_by_name("test-skill")
        self.assertTrue(skill.disabled)


if __name__ == "__main__":
    unittest.main()
