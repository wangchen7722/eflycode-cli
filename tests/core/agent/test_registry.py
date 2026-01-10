import unittest

from eflycode.core.agent.base import BaseAgent
from eflycode.core.agent.code_agent import CodeAgent
from eflycode.core.agent.registry import AgentRegistry
from eflycode.core.llm.protocol import ChatCompletion, Message, Usage
from eflycode.core.llm.providers.base import LLMProvider, ProviderCapabilities


class MockProvider(LLMProvider):
    """Mock LLM Provider 用于测试"""

    @property
    def capabilities(self):
        return ProviderCapabilities(supports_streaming=False, supports_tools=False)

    def call(self, request):
        return ChatCompletion(
            id="chatcmpl-mock",
            object="chat.completion",
            created=1234567890,
            model="gpt-4",
            message=Message(role="assistant", content="ok"),
            usage=Usage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )

    def stream(self, request):
        raise NotImplementedError("stream not used in tests")


class TestCodeAgent(unittest.TestCase):
    """CodeAgent 测试类"""

    def test_role(self):
        """测试 CodeAgent ROLE"""
        self.assertEqual(CodeAgent.ROLE, "code")

    def test_init(self):
        """测试 CodeAgent 可正常初始化"""
        agent = CodeAgent(provider=MockProvider(), model="gpt-4")
        try:
            self.assertIsInstance(agent, BaseAgent)
        finally:
            agent.shutdown()


class TestAgentRegistry(unittest.TestCase):
    """AgentRegistry 测试类"""

    def setUp(self):
        """清理注册表"""
        self.registry = AgentRegistry.get_instance()
        self.registry.clear()

    def test_singleton(self):
        """测试单例实例唯一"""
        registry_a = AgentRegistry.get_instance()
        registry_b = AgentRegistry.get_instance()
        self.assertIs(registry_a, registry_b)

    def test_register_and_get(self):
        """测试注册和获取"""
        self.registry.register("code", CodeAgent)
        self.assertIs(self.registry.get("code"), CodeAgent)

    def test_list_agents(self):
        """测试列出注册项"""
        self.registry.register("code", CodeAgent)
        agents = self.registry.list_agents()
        self.assertIn("code", agents)
        self.assertIs(agents["code"], CodeAgent)

    def test_register_invalid(self):
        """测试注册非法类型"""
        with self.assertRaises(ValueError):
            self.registry.register("bad", dict)
