"""Skills 功能集成测试

测试完整的技能系统流程
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from eflycode.core.config.models import Config, ConfigMeta, SkillsSection
from eflycode.core.llm.protocol import LLMRequest, Message
from eflycode.core.skills import SkillsManager
from eflycode.core.skills.activate_tool import ActivateSkillTool
from eflycode.core.skills.skills_advisor import SkillsAdvisor


class TestSkillsIntegration(unittest.TestCase):
    """测试 Skills 功能的完整集成"""

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

        # 创建配置（skills 已启用）
        self.config = Config(
            meta=ConfigMeta(
                workspace_dir=self.project_workspace_dir,
                source="default",
            ),
            skills=SkillsSection(enabled=True),
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

    def test_full_workflow(self):
        """测试完整的工作流程"""
        # 1. 创建技能文件
        self._create_skill_file(
            self.user_config_dir,
            "review-helper",
            "代码审查助手",
            "# Code Review\n\n请按照以下步骤进行代码审查：\n1. 检查安全性\n2. 检查性能\n3. 检查可读性",
        )

        # 2. 重新扫描加载技能
        changes = self.manager.reload_skills()
        self.assertTrue(changes.has_changes)
        self.assertEqual(len(changes.added), 1)

        # 3. 验证技能已加载
        skills = self.manager.get_enabled_skills()
        self.assertEqual(len(skills), 1)
        self.assertEqual(skills[0].name, "review-helper")

        # 4. 创建 ActivateSkillTool
        tool = ActivateSkillTool()

        # 5. 验证工具参数
        params = tool.parameters
        self.assertIn("review-helper", params.properties["skill_name"]["enum"])

        # 6. 执行工具激活技能
        result = tool.run(skill_name="review-helper")

        # 7. 验证返回的 XML 格式
        self.assertIn("<activated_skill", result)
        self.assertIn('name="review-helper"', result)
        self.assertIn("<instructions>", result)
        self.assertIn("# Code Review", result)
        self.assertIn("检查安全性", result)

    def test_skills_advisor_injection(self):
        """测试 SkillsAdvisor 注入到系统提示词"""
        # 创建技能
        self._create_skill_file(
            self.user_config_dir, "test-skill", "测试技能", "# Instructions"
        )

        self.manager.reload_skills()

        # 创建 mock agent
        agent = MagicMock()

        # 创建 advisor
        advisor = SkillsAdvisor(agent=agent, config=self.config)

        # 创建请求
        request = LLMRequest(
            model="test-model",
            messages=[
                Message(role="system", content="原始系统提示词"),
                Message(role="user", content="test"),
            ],
        )

        # 添加可用技能
        modified_request = advisor.before_call(request)

        # 验证系统提示词已更新
        system_msg = modified_request.messages[0]
        self.assertIn("<available_skills>", system_msg.content)
        self.assertIn("<name>test-skill</name>", system_msg.content)
        self.assertIn("activate_skill", system_msg.content)

    def test_disabled_skill_not_included(self):
        """测试禁用的技能不包含在可用列表中"""
        # 创建两个技能
        self._create_skill_file(self.user_config_dir, "skill1", "技能1")
        self._create_skill_file(self.user_config_dir, "skill2", "技能2")

        self.manager.reload_skills()

        # 禁用一个技能
        self.manager.disable_skill("skill2")

        # 创建工具
        tool = ActivateSkillTool()

        # 验证只有启用的技能在 enum 中
        params = tool.parameters
        enum_values = params.properties["skill_name"]["enum"]
        self.assertEqual(enum_values, ["skill1"])

        # 验证禁用的技能无法激活
        result = tool.run(skill_name="skill2")
        self.assertIn("错误", result)

    def test_manifest_persistence(self):
        """测试清单持久化"""
        # 创建技能
        self._create_skill_file(self.user_config_dir, "persistent-skill", "持久化技能")

        self.manager.reload_skills()
        self.manager.disable_skill("persistent-skill")

        # 验证清单文件已创建
        manifest_path = self.user_config_dir / "skills.json"
        self.assertTrue(manifest_path.exists())

        # 重置管理器
        SkillsManager.reset_instance()

        # 重新初始化
        manager = SkillsManager.get_instance()
        manager.initialize(
            user_config_dir=self.user_config_dir,
            project_workspace_dir=self.project_workspace_dir,
        )

        # 重新扫描
        manager.reload_skills()

        # 验证禁用状态已恢复
        skill = manager.get_skill_by_name("persistent-skill")
        self.assertTrue(skill.disabled)

    def test_skill_override(self):
        """测试项目技能覆盖用户技能"""
        # 创建同名技能
        self._create_skill_file(
            self.user_config_dir, "common", "用户技能", "# User Skill"
        )
        self._create_skill_file(
            self.project_workspace_dir / ".eflycode",
            "common",
            "项目技能",
            "# Project Skill",
        )

        self.manager.reload_skills()

        # 验证只有项目技能
        skills = self.manager.get_all_skills()
        self.assertEqual(len(skills), 1)
        self.assertEqual(skills[0].source, "project")
        self.assertEqual(skills[0].description, "项目技能")

        # 验证工具可以激活项目技能
        tool = ActivateSkillTool()
        result = tool.run(skill_name="common")
        self.assertIn("# Project Skill", result)


if __name__ == "__main__":
    unittest.main()
