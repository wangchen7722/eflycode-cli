"""SystemPromptAdvisor 测试用例"""

import os
import tempfile
import unittest
from pathlib import Path

from eflycode.core.agent.base import BaseAgent
from eflycode.core.config.config_manager import ConfigManager
from eflycode.core.llm.protocol import LLMRequest, Message
from eflycode.core.llm.providers.base import LLMProvider
from eflycode.core.prompt.system_prompt_advisor import SystemPromptAdvisor


class MockProvider(LLMProvider):
    """Mock LLM Provider 用于测试"""

    @property
    def capabilities(self):
        from eflycode.core.llm.providers.base import ProviderCapabilities
        return ProviderCapabilities(supports_streaming=True, supports_tools=True)

    def call(self, request):
        pass

    def stream(self, request):
        pass


class TestSystemPromptAdvisor(unittest.TestCase):
    """SystemPromptAdvisor 测试类"""

    def setUp(self):
        """设置测试环境"""
        self.llm_provider = MockProvider()
        self.agent = BaseAgent(
            model="test-model",
            provider=self.llm_provider,
        )
        # 初始化 ConfigManager
        ConfigManager.get_instance().load()

    def test_before_call_adds_system_message(self):
        """测试 before_call 添加 system message"""
        advisor = SystemPromptAdvisor(agent=self.agent)

        request = LLMRequest(
            model="test-model",
            messages=[
                Message(role="user", content="Hello"),
            ],
        )

        result = advisor.before_call(request)

        # 应该添加了 system message
        self.assertEqual(len(result.messages), 2)
        self.assertEqual(result.messages[0].role, "system")
        self.assertIsNotNone(result.messages[0].content)
        self.assertEqual(result.messages[1].role, "user")

    def test_before_call_no_duplicate_system_message(self):
        """测试已有 system message 时不重复添加"""
        advisor = SystemPromptAdvisor(agent=self.agent)

        request = LLMRequest(
            model="test-model",
            messages=[
                Message(role="system", content="Existing system message"),
                Message(role="user", content="Hello"),
            ],
        )

        result = advisor.before_call(request)

        # 不应该添加新的 system message
        self.assertEqual(len(result.messages), 2)
        self.assertEqual(result.messages[0].content, "Existing system message")

    def test_before_stream_adds_system_message(self):
        """测试 before_stream 添加 system message"""
        advisor = SystemPromptAdvisor(agent=self.agent)

        request = LLMRequest(
            model="test-model",
            messages=[
                Message(role="user", content="Hello"),
            ],
        )

        result = advisor.before_stream(request)

        # 应该添加了 system message
        self.assertEqual(len(result.messages), 2)
        self.assertEqual(result.messages[0].role, "system")
        self.assertIsNotNone(result.messages[0].content)

    def test_before_call_with_workspace_dir(self):
        """测试使用工作区目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_dir = Path(tmpdir)
            agent_dir = workspace_dir / ".eflycode" / "agents" / "default"
            agent_dir.mkdir(parents=True, exist_ok=True)

            user_template = "Custom workspace template: {{ workspace.path }}"
            template_path = agent_dir / "system.prompt"
            template_path.write_text(user_template, encoding="utf-8")

            # 切换到临时目录并重新加载配置
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                # 重置单例以测试新配置
                ConfigManager._instance = None
                ConfigManager.get_instance().load()

                advisor = SystemPromptAdvisor(agent=self.agent)

                request = LLMRequest(
                    model="test-model",
                    messages=[Message(role="user", content="Hello")],
                )

                result = advisor.before_call(request)

                # 应该使用了用户模板
                self.assertIn(str(workspace_dir), result.messages[0].content)
            finally:
                os.chdir(original_cwd)

    def test_before_call_with_custom_role(self):
        """测试使用自定义 ROLE"""
        class CustomAgent(BaseAgent):
            ROLE = "custom-role"

        custom_agent = CustomAgent(
            model="test-model",
            provider=self.llm_provider,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_dir = Path(tmpdir)
            agent_dir = workspace_dir / ".eflycode" / "agents" / "custom-role"
            agent_dir.mkdir(parents=True, exist_ok=True)

            custom_template = "Custom role template"
            template_path = agent_dir / "system.prompt"
            template_path.write_text(custom_template, encoding="utf-8")

            # 切换到临时目录并重新加载配置
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                # 重置单例以测试新配置
                ConfigManager._instance = None
                ConfigManager.get_instance().load()

                advisor = SystemPromptAdvisor(agent=custom_agent)

                request = LLMRequest(
                    model="test-model",
                    messages=[Message(role="user", content="Hello")],
                )

                result = advisor.before_call(request)

                # 应该使用了自定义角色的模板
                self.assertEqual(result.messages[0].content, custom_template)
            finally:
                os.chdir(original_cwd)

    def test_before_call_template_not_found(self):
        """测试模板不存在时的处理"""
        # 使用一个不存在的角色
        class UnknownAgent(BaseAgent):
            ROLE = "unknown-role-that-does-not-exist"

        unknown_agent = UnknownAgent(
            model="test-model",
            provider=self.llm_provider,
        )

        advisor = SystemPromptAdvisor(agent=unknown_agent)

        request = LLMRequest(
            model="test-model",
            messages=[Message(role="user", content="Hello")],
        )

        result = advisor.before_call(request)

        # 应该回退到默认模板
        self.assertEqual(len(result.messages), 2)
        self.assertEqual(result.messages[0].role, "system")

    def test_before_call_template_render_failure(self):
        """测试模板渲染失败时的处理"""
        # 创建一个会导致渲染失败的模板
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_dir = Path(tmpdir)
            agent_dir = workspace_dir / ".eflycode" / "agents" / "default"
            agent_dir.mkdir(parents=True, exist_ok=True)

            # 使用未定义的变量
            invalid_template = "{{ undefined_variable }}"
            template_path = agent_dir / "system.prompt"
            template_path.write_text(invalid_template, encoding="utf-8")

            # 切换到临时目录并重新加载配置
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                # 重置单例以测试新配置
                ConfigManager._instance = None
                ConfigManager.get_instance().load()

                advisor = SystemPromptAdvisor(agent=self.agent)

                request = LLMRequest(
                    model="test-model",
                    messages=[Message(role="user", content="Hello")],
                )

                result = advisor.before_call(request)

                # 渲染失败时不应该添加 system message
                self.assertEqual(len(result.messages), 1)
                self.assertEqual(result.messages[0].role, "user")
            finally:
                os.chdir(original_cwd)

    def test_system_message_contains_variables(self):
        """测试 system message 包含变量内容"""
        advisor = SystemPromptAdvisor(agent=self.agent)

        request = LLMRequest(
            model="test-model",
            messages=[Message(role="user", content="Hello")],
        )

        result = advisor.before_call(request)

        system_content = result.messages[0].content

        # 应该包含模型名称
        self.assertIn("test-model", system_content)
        # 应该包含系统版本
        self.assertIn("0.1.0", system_content)

    def test_before_call_preserves_original_messages(self):
        """测试 before_call 保留原始消息"""
        advisor = SystemPromptAdvisor(agent=self.agent)

        original_messages = [
            Message(role="user", content="First message"),
            Message(role="assistant", content="Response"),
            Message(role="user", content="Second message"),
        ]

        request = LLMRequest(
            model="test-model",
            messages=original_messages.copy(),
        )

        result = advisor.before_call(request)

        # 应该添加了 system message，但保留了所有原始消息
        self.assertEqual(len(result.messages), 4)
        self.assertEqual(result.messages[0].role, "system")
        self.assertEqual(result.messages[1].content, "First message")
        self.assertEqual(result.messages[2].content, "Response")
        self.assertEqual(result.messages[3].content, "Second message")

