"""测试 Skills Advisor"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from eflycode.core.config.models import Config, ConfigMeta, SkillsSection
from eflycode.core.llm.protocol import LLMRequest, Message
from eflycode.core.skills.manager import SkillsManager
from eflycode.core.skills.skills_advisor import SkillsAdvisor


class TestSkillsAdvisor(unittest.TestCase):
    """测试 SkillsAdvisor"""

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

        # 创建 mock agent
        self.agent = MagicMock()

        # 创建配置（skills 未启用）
        self.config_disabled = Config(
            meta=ConfigMeta(
                workspace_dir=self.project_workspace_dir,
                source="default",
            ),
            skills=None,
        )

        # 创建配置（skills 已启用）
        self.config_enabled = Config(
            meta=ConfigMeta(
                workspace_dir=self.project_workspace_dir,
                source="default",
            ),
            skills=SkillsSection(enabled=True),
        )

        # 创建 advisor
        self.advisor = SkillsAdvisor(self.agent, self.config_enabled)

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

    def test_disabled_skills(self):
        """测试 skills 未启用时不添加内容"""
        advisor = SkillsAdvisor(self.agent, self.config_disabled)

        request = LLMRequest(
            model="test-model", messages=[Message(role="user", content="test")]
        )
        modified_request = advisor.before_call(request)

        # 消息数量应该不变
        self.assertEqual(len(modified_request.messages), len(request.messages))

    def test_no_available_skills(self):
        """测试没有可用技能时不添加内容"""
        advisor = SkillsAdvisor(self.agent, self.config_enabled)

        request = LLMRequest(
            model="test-model", messages=[Message(role="user", content="test")]
        )
        modified_request = advisor.before_call(request)

        # 消息数量应该不变
        self.assertEqual(len(modified_request.messages), len(request.messages))

    def test_add_to_existing_system_message(self):
        """测试添加到现有的系统消息"""
        self._create_skill_file(self.user_config_dir, "skill1", "技能1")
        self._create_skill_file(self.user_config_dir, "skill2", "技能2")

        self.manager.reload_skills()

        advisor = SkillsAdvisor(self.agent, self.config_enabled)

        request = LLMRequest(
            model="test-model",
            messages=[
                Message(role="system", content="原始系统提示词"),
                Message(role="user", content="test"),
            ],
        )

        modified_request = advisor.before_call(request)

        # 消息数量应该不变
        self.assertEqual(len(modified_request.messages), 2)

        # 第一个消息应该是 system，且包含原始内容和可用技能
        system_msg = modified_request.messages[0]
        self.assertEqual(system_msg.role, "system")
        self.assertIn("原始系统提示词", system_msg.content)
        self.assertIn("<available_skills>", system_msg.content)
        self.assertIn("<name>skill1</name>", system_msg.content)
        self.assertIn("<name>skill2</name>", system_msg.content)
        self.assertIn("activate_skill", system_msg.content)

    def test_create_new_system_message(self):
        """测试创建新的系统消息"""
        self._create_skill_file(self.user_config_dir, "skill1", "技能1")

        self.manager.reload_skills()

        advisor = SkillsAdvisor(self.agent, self.config_enabled)

        request = LLMRequest(
            model="test-model", messages=[Message(role="user", content="test")]
        )

        modified_request = advisor.before_call(request)

        # 应该有两个消息（新增一个 system message）
        self.assertEqual(len(modified_request.messages), 2)

        # 第一个消息应该是 system
        system_msg = modified_request.messages[0]
        self.assertEqual(system_msg.role, "system")
        self.assertIn("<available_skills>", system_msg.content)

        # 第二个消息应该是原始的 user message
        user_msg = modified_request.messages[1]
        self.assertEqual(user_msg.role, "user")
        self.assertEqual(user_msg.content, "test")

    def test_disabled_skills_not_included(self):
        """测试禁用的技能不包含在可用技能中"""
        self._create_skill_file(self.user_config_dir, "skill1", "技能1")
        self._create_skill_file(self.user_config_dir, "skill2", "技能2")

        self.manager.reload_skills()
        self.manager.disable_skill("skill2")

        advisor = SkillsAdvisor(self.agent, self.config_enabled)

        request = LLMRequest(
            model="test-model",
            messages=[
                Message(role="system", content="系统提示词"),
                Message(role="user", content="test"),
            ],
        )

        modified_request = advisor.before_call(request)

        system_msg = modified_request.messages[0]
        self.assertIn("<name>skill1</name>", system_msg.content)
        self.assertNotIn("<name>skill2</name>", system_msg.content)

    def test_available_skills_format(self):
        """测试可用技能的 XML 格式"""
        self._create_skill_file(
            self.user_config_dir, "test-skill", "测试技能", "# Instructions"
        )

        self.manager.reload_skills()

        advisor = SkillsAdvisor(self.agent, self.config_enabled)

        request = LLMRequest(
            model="test-model", messages=[Message(role="user", content="test")]
        )
        modified_request = advisor.before_stream(request)

        system_msg = modified_request.messages[0]
        content = system_msg.content

        # 检查 XML 格式
        self.assertIn("<available_skills>", content)
        self.assertIn("<skill>", content)
        self.assertIn("<name>test-skill</name>", content)
        self.assertIn("<description>测试技能</description>", content)
        self.assertIn("<location>", content)
        self.assertIn("</skill>", content)
        self.assertIn("</available_skills>", content)

        # 检查提示文本
        self.assertIn("activate_skill 工具", content)
        self.assertIn("<activated_skill>", content)

    def test_before_stream(self):
        """测试 before_stream 方法"""
        self._create_skill_file(self.user_config_dir, "skill1", "技能1")

        self.manager.reload_skills()

        advisor = SkillsAdvisor(self.agent, self.config_enabled)

        request = LLMRequest(
            model="test-model", messages=[Message(role="user", content="test")]
        )
        modified_request = advisor.before_stream(request)

        # 应该添加 system message
        self.assertEqual(len(modified_request.messages), 2)
        self.assertEqual(modified_request.messages[0].role, "system")


if __name__ == "__main__":
    unittest.main()
