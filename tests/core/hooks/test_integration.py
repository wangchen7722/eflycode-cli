"""Hooks 系统集成测试"""

import tempfile
import unittest
from pathlib import Path

from eflycode.core.agent.base import BaseAgent
from eflycode.core.hooks.system import HookSystem
from eflycode.core.hooks.types import CommandHook, HookEventName
from eflycode.core.llm.protocol import LLMConfig
from eflycode.core.llm.providers.base import LLMProvider
from eflycode.core.tool.base import BaseTool


class MockProvider(LLMProvider):
    """模拟 LLM Provider"""

    def __init__(self, config=None):
        """初始化 MockProvider
        
        Args:
            config: LLMConfig 实例（可选，用于兼容性）
        """
        self.config = config

    def call(self, request):
        """模拟调用"""
        from eflycode.core.llm.protocol import ChatCompletion, Message

        return ChatCompletion(
            id="test",
            object="chat.completion",
            created=0,
            model="test",
            message=Message(role="assistant", content="test response"),
        )

    def stream(self, request):
        """模拟流式调用"""
        from eflycode.core.llm.protocol import ChatCompletionChunk, DeltaMessage

        yield ChatCompletionChunk(
            id="test",
            object="chat.completion.chunk",
            created=0,
            model="test",
            delta=DeltaMessage(role="assistant", content="test"),
        )

    @property
    def capabilities(self):
        """返回能力"""
        from eflycode.core.llm.providers.base import ProviderCapabilities

        return ProviderCapabilities(supports_streaming=True, supports_tools=True)


class MockTool(BaseTool):
    """模拟工具"""

    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def type(self) -> str:
        from eflycode.core.tool.base import ToolType
        return ToolType.FUNCTION

    @property
    def permission(self) -> str:
        return "read"

    @property
    def description(self) -> str:
        return "Mock tool for testing"

    @property
    def parameters(self):
        from eflycode.core.llm.protocol import ToolFunctionParameters

        return ToolFunctionParameters(properties={})

    def do_run(self, **kwargs) -> str:
        return "mock result"


class TestHooksIntegration(unittest.TestCase):
    """Hooks 系统集成测试"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.workspace_dir = Path(self.temp_dir)
        self.hook_system = HookSystem(workspace_dir=self.workspace_dir)

        # 创建模拟的 Agent
        provider = MockProvider(LLMConfig(api_key="test"))
        self.agent = BaseAgent(
            model="test",
            provider=provider,
            tools=[MockTool()],
            hook_system=self.hook_system,
        )

    def tearDown(self):
        """清理测试环境"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_before_tool_hook_execution(self):
        """测试 BeforeTool hook 执行"""
        # 注册一个 hook
        hook = CommandHook(
            name="test_hook",
            command="echo '{\"decision\": \"allow\"}'",
        )
        self.hook_system.register_hook(HookEventName.BEFORE_TOOL, hook)

        # 执行工具
        result = self.agent.run_tool("mock_tool", arg1="value1")
        self.assertEqual(result, "mock result")

    def test_before_tool_hook_block(self):
        """测试 BeforeTool hook 阻断工具执行"""
        # 注册一个阻断 hook
        hook = CommandHook(
            name="block_hook",
            command="echo '{\"decision\": \"block\", \"systemMessage\": \"Blocked!\"}'",
        )
        self.hook_system.register_hook(HookEventName.BEFORE_TOOL, hook)

        # 执行工具应该被阻断
        from eflycode.core.tool.errors import ToolExecutionError

        with self.assertRaises(ToolExecutionError) as context:
            self.agent.run_tool("mock_tool", arg1="value1")
        self.assertIn("Blocked!", str(context.exception))

    def test_before_model_hook_modifies_request(self):
        """测试 BeforeModel hook 修改请求"""
        # 这个测试需要更复杂的 hook 实现，暂时跳过
        # 因为需要 hook 返回修改后的 llm_request
        pass

    def test_hook_with_tool_matcher(self):
        """测试带工具匹配器的 hook"""
        # 注册只匹配特定工具的 hook
        hook = CommandHook(
            name="matched_hook",
            command="echo 'matched'",
            matcher="mock_tool",
        )
        self.hook_system.register_hook(HookEventName.BEFORE_TOOL, hook)

        # 执行匹配的工具
        result = self.agent.run_tool("mock_tool", arg1="value1")
        self.assertEqual(result, "mock result")

    def test_hook_with_wildcard_matcher(self):
        """测试通配符匹配器"""
        hook = CommandHook(
            name="wildcard_hook",
            command="echo 'wildcard'",
            matcher="*",
        )
        self.hook_system.register_hook(HookEventName.BEFORE_TOOL, hook)

        # 执行任何工具都应该触发 hook
        result = self.agent.run_tool("mock_tool", arg1="value1")
        self.assertEqual(result, "mock result")

    def test_multiple_hooks_sequential(self):
        """测试多个 hooks 串行执行"""
        hook1 = CommandHook(name="hook1", command="echo 'hook1'")
        hook2 = CommandHook(name="hook2", command="echo 'hook2'")
        self.hook_system.register_hook(
            HookEventName.BEFORE_TOOL, hook1, group_matcher="*", sequential=True
        )
        self.hook_system.register_hook(
            HookEventName.BEFORE_TOOL, hook2, group_matcher="*", sequential=True
        )

        result = self.agent.run_tool("mock_tool", arg1="value1")
        self.assertEqual(result, "mock result")


if __name__ == "__main__":
    unittest.main()

