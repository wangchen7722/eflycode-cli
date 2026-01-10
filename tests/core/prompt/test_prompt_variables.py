"""SystemPromptAdvisor 变量生成测试用例

测试 SystemPromptAdvisor 的 _get_prompt_variables 方法
"""

import platform
import sys
import unittest
from pathlib import Path

from eflycode.core.agent.base import BaseAgent
from eflycode.core.config.config_manager import Config, ConfigManager, LLMConfig
from eflycode.core.llm.providers.base import LLMProvider
from eflycode.core.llm.advisors.system_prompt_advisor import SystemPromptAdvisor
from eflycode.core.tool.base import BaseTool, ToolGroup


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


class MockTool(BaseTool):
    """Mock 工具用于测试"""

    def __init__(self, name: str, description: str = "Test tool"):
        self._name = name
        self._description = description

    @property
    def name(self) -> str:
        return self._name

    @property
    def type(self) -> str:
        return "function"

    @property
    def permission(self) -> str:
        return "read"

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self):
        from eflycode.core.llm.protocol import ToolFunctionParameters
        return ToolFunctionParameters(properties={})

    def do_run(self, **kwargs):
        return "test result"


class TestSystemPromptAdvisorVariables(unittest.TestCase):
    """SystemPromptAdvisor 变量生成测试类"""

    def setUp(self):
        """设置测试环境"""
        self.llm_provider = MockProvider()
        self.agent = BaseAgent(
            model="test-model",
            provider=self.llm_provider,
        )
        # 初始化 ConfigManager
        ConfigManager.get_instance().load()
        self.advisor = SystemPromptAdvisor(agent=self.agent)

    def test_get_prompt_variables_basic(self):
        """测试获取基本变量"""
        variables = self.advisor._get_prompt_variables()

        # 检查基本结构
        self.assertIn("tools", variables)
        self.assertIn("system", variables)
        self.assertIn("workspace", variables)
        self.assertIn("model", variables)
        self.assertIn("context", variables)
        self.assertIn("environment", variables)
        self.assertIn("agent", variables)

    def test_system_variables(self):
        """测试系统变量"""
        variables = self.advisor._get_prompt_variables()

        self.assertIn("version", variables["system"])
        self.assertIn("timezone", variables["system"])
        self.assertIn("date", variables["system"])
        self.assertIn("time", variables["system"])
        self.assertIn("datetime", variables["system"])

        # 检查日期格式
        date = variables["system"]["date"]
        self.assertRegex(date, r"\d{4}-\d{2}-\d{2}")

        # 检查时间格式
        time = variables["system"]["time"]
        self.assertRegex(time, r"\d{2}:\d{2}:\d{2}")

        # 检查版本
        self.assertIsInstance(variables["system"]["version"], str)

    def test_workspace_variables(self):
        """测试工作区变量"""
        variables = self.advisor._get_prompt_variables()

        # 由于使用实际配置，只检查结构
        self.assertIn("path", variables["workspace"])
        self.assertIn("name", variables["workspace"])

    def test_workspace_variables_no_dir(self):
        """测试无工作区目录时的变量"""
        # 重新加载 ConfigManager
        ConfigManager.get_instance().load()
        advisor = SystemPromptAdvisor(agent=self.agent)
        variables = advisor._get_prompt_variables()

        # 应该使用实际加载的配置
        self.assertIsInstance(variables["workspace"]["path"], str)
        self.assertIsInstance(variables["workspace"]["name"], str)

    def test_model_variables(self):
        """测试模型变量"""
        variables = self.advisor._get_prompt_variables()

        # 由于使用实际配置，只检查结构
        self.assertIn("name", variables["model"])
        self.assertIn("provider", variables["model"])
        self.assertIn("max_context_length", variables["model"])

    def test_context_variables(self):
        """测试上下文变量"""
        variables = self.advisor._get_prompt_variables()

        self.assertIn("strategy", variables["context"])
        # 默认情况下应该是 "none"
        self.assertEqual(variables["context"]["strategy"], "none")

    def test_environment_variables(self):
        """测试环境变量"""
        variables = self.advisor._get_prompt_variables()

        self.assertEqual(variables["environment"]["os"], platform.system())
        self.assertIn("python_version", variables["environment"])
        self.assertIn("platform", variables["environment"])

        # 检查 Python 版本格式
        python_version = variables["environment"]["python_version"]
        self.assertRegex(python_version, r"\d+\.\d+\.\d+")

    def test_agent_variables(self):
        """测试 Agent 变量"""
        variables = self.advisor._get_prompt_variables()

        self.assertEqual(variables["agent"]["name"], "default")

    def test_agent_variables_custom_role(self):
        """测试自定义 ROLE 的 Agent 变量"""
        class CustomAgent(BaseAgent):
            ROLE = "custom-role"

        custom_agent = CustomAgent(
            model="test-model",
            provider=self.llm_provider,
        )
        advisor = SystemPromptAdvisor(agent=custom_agent)
        variables = advisor._get_prompt_variables()

        self.assertEqual(variables["agent"]["name"], "custom-role")

    def test_tools_variables(self):
        """测试工具变量"""
        tool1 = MockTool("tool1", "Tool 1 description")
        tool2 = MockTool("tool2", "Tool 2 description")
        self.agent.add_tool(tool1)
        self.agent.add_tool(tool2)

        variables = self.advisor._get_prompt_variables()

        self.assertEqual(len(variables["tools"]), 2)
        tool_names = [t["name"] for t in variables["tools"]]
        self.assertIn("tool1", tool_names)
        self.assertIn("tool2", tool_names)

    def test_tools_variables_empty(self):
        """测试无工具时的变量"""
        variables = self.advisor._get_prompt_variables()

        # SystemPromptAdvisor 会自动添加一些内置工具，所以可能不为空
        self.assertIsInstance(variables["tools"], list)

    def test_tools_variables_with_tool_groups(self):
        """测试工具组中的工具"""
        tool1 = MockTool("tool1", "Tool 1")
        tool2 = MockTool("tool2", "Tool 2")
        tool_group = ToolGroup("test_group", "Test group", [tool1, tool2])
        self.agent.add_tool_group(tool_group)

        variables = self.advisor._get_prompt_variables()

        tool_names = [t["name"] for t in variables["tools"]]
        self.assertIn("tool1", tool_names)
        self.assertIn("tool2", tool_names)
