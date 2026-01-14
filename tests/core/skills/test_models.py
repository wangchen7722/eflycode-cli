"""测试技能数据模型"""

import unittest
from pathlib import Path

from eflycode.core.skills.models import (
    SkillChanges,
    SkillManifest,
    SkillManifestEntry,
    SkillMetadata,
)


class TestSkillMetadata(unittest.TestCase):
    """测试 SkillMetadata 模型"""

    def test_create_skill_metadata(self):
        """测试创建技能元数据"""
        skill = SkillMetadata(
            name="test-skill",
            description="测试技能",
            content="# Test Skill\n\n这是测试内容",
            file_path=Path("/test/skills/test-skill.md"),
            source="user",
            mtime=1704067200.0,
        )

        self.assertEqual(skill.name, "test-skill")
        self.assertEqual(skill.description, "测试技能")
        self.assertEqual(skill.source, "user")
        self.assertFalse(skill.disabled)

    def test_skill_equality(self):
        """测试技能相等性"""
        skill1 = SkillMetadata(
            name="test-skill",
            description="测试技能",
            content="# Test",
            file_path=Path("/test/skills/test-skill.md"),
            source="user",
            mtime=1704067200.0,
        )

        skill2 = SkillMetadata(
            name="test-skill",
            description="不同的描述",  # 描述不同
            content="# Different",
            file_path=Path("/test/skills/test-skill.md"),
            source="user",
            mtime=1704067201.0,  # mtime 也不同
        )

        # 应该相等，因为 name, source, file_path 相同
        self.assertEqual(skill1, skill2)

    def test_skill_inequality(self):
        """测试技能不相等"""
        skill1 = SkillMetadata(
            name="test-skill",
            description="测试技能",
            content="# Test",
            file_path=Path("/test/skills/test-skill.md"),
            source="user",
            mtime=1704067200.0,
        )

        skill2 = SkillMetadata(
            name="test-skill",
            description="测试技能",
            content="# Test",
            file_path=Path("/test/skills/test-skill.md"),
            source="project",  # 来源不同
            mtime=1704067200.0,
        )

        self.assertNotEqual(skill1, skill2)

    def test_skill_hash(self):
        """测试技能哈希"""
        skill = SkillMetadata(
            name="test-skill",
            description="测试技能",
            content="# Test",
            file_path=Path("/test/skills/test-skill.md"),
            source="user",
            mtime=1704067200.0,
        )

        # 相同的技能应该有相同的哈希值
        skill_set = {skill}
        self.assertIn(skill, skill_set)


class TestSkillManifest(unittest.TestCase):
    """测试 SkillManifest 模型"""

    def test_empty_manifest(self):
        """测试空清单"""
        manifest = SkillManifest()
        self.assertEqual(len(manifest.skills), 0)

    def test_add_skill(self):
        """测试添加技能"""
        manifest = SkillManifest()
        skill = SkillMetadata(
            name="test-skill",
            description="测试技能",
            content="# Test",
            file_path=Path("/test/skills/test-skill.md"),
            source="user",
            mtime=1704067200.0,
        )

        manifest.add_skill(skill)

        self.assertEqual(len(manifest.skills), 1)
        self.assertIn("test-skill", manifest.skills)

        entry = manifest.get_skill("test-skill")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.name, "test-skill")
        self.assertEqual(entry.description, "测试技能")

    def test_remove_skill(self):
        """测试移除技能"""
        manifest = SkillManifest()
        skill = SkillMetadata(
            name="test-skill",
            description="测试技能",
            content="# Test",
            file_path=Path("/test/skills/test-skill.md"),
            source="user",
            mtime=1704067200.0,
        )

        manifest.add_skill(skill)
        self.assertEqual(len(manifest.skills), 1)

        # 移除存在的技能
        result = manifest.remove_skill("test-skill")
        self.assertTrue(result)
        self.assertEqual(len(manifest.skills), 0)

        # 移除不存在的技能
        result = manifest.remove_skill("nonexistent")
        self.assertFalse(result)

    def test_get_enabled_skills(self):
        """测试获取启用的技能"""
        manifest = SkillManifest()

        # 添加启用的技能
        skill1 = SkillMetadata(
            name="enabled-skill",
            description="启用的技能",
            content="# Test",
            file_path=Path("/test/skills/enabled-skill.md"),
            source="user",
            disabled=False,
            mtime=1704067200.0,
        )
        manifest.add_skill(skill1)

        # 添加禁用的技能
        skill2 = SkillMetadata(
            name="disabled-skill",
            description="禁用的技能",
            content="# Test",
            file_path=Path("/test/skills/disabled-skill.md"),
            source="user",
            disabled=True,
            mtime=1704067200.0,
        )
        manifest.add_skill(skill2)

        enabled = manifest.get_enabled_skills()
        self.assertEqual(len(enabled), 1)
        self.assertEqual(enabled[0].name, "enabled-skill")

    def test_update_skill(self):
        """测试更新技能"""
        manifest = SkillManifest()

        skill1 = SkillMetadata(
            name="test-skill",
            description="原始描述",
            content="# Test",
            file_path=Path("/test/skills/test-skill.md"),
            source="user",
            mtime=1704067200.0,
        )
        manifest.add_skill(skill1)

        # 更新为新的描述
        skill2 = SkillMetadata(
            name="test-skill",
            description="新的描述",
            content="# Updated",
            file_path=Path("/test/skills/test-skill.md"),
            source="user",
            mtime=1704067201.0,
        )
        manifest.add_skill(skill2)

        # 应该只有一个技能，且是更新后的版本
        self.assertEqual(len(manifest.skills), 1)
        entry = manifest.get_skill("test-skill")
        self.assertEqual(entry.description, "新的描述")
        self.assertEqual(entry.mtime, 1704067201.0)


class TestSkillChanges(unittest.TestCase):
    """测试 SkillChanges 模型"""

    def test_empty_changes(self):
        """测试空变更"""
        changes = SkillChanges()
        self.assertFalse(changes.has_changes)
        self.assertEqual(len(changes.added), 0)
        self.assertEqual(len(changes.modified), 0)
        self.assertEqual(len(changes.removed), 0)

    def test_has_changes(self):
        """测试变更检测"""
        changes = SkillChanges()

        # 没有变更
        self.assertFalse(changes.has_changes)

        # 有新增
        changes.added.append(
            SkillMetadata(
                name="new-skill",
                description="新技能",
                content="# Test",
                file_path=Path("/test/new.md"),
                source="user",
                mtime=1704067200.0,
            )
        )
        self.assertTrue(changes.has_changes)

    def test_multiple_change_types(self):
        """测试多种变更类型"""
        changes = SkillChanges()

        # 新增
        changes.added.append(
            SkillMetadata(
                name="added-skill",
                description="新增技能",
                content="# Test",
                file_path=Path("/test/added.md"),
                source="user",
                mtime=1704067200.0,
            )
        )

        # 修改
        changes.modified.append(
            SkillMetadata(
                name="modified-skill",
                description="修改技能",
                content="# Test",
                file_path=Path("/test/modified.md"),
                source="user",
                mtime=1704067201.0,
            )
        )

        # 删除
        changes.removed.append(
            SkillManifestEntry(
                name="removed-skill",
                description="删除技能",
                file_path="/test/removed.md",
                mtime=1704067200.0,
            )
        )

        self.assertTrue(changes.has_changes)
        self.assertEqual(len(changes.added), 1)
        self.assertEqual(len(changes.modified), 1)
        self.assertEqual(len(changes.removed), 1)


if __name__ == "__main__":
    unittest.main()
