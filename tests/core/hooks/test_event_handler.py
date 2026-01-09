"""HookEventHandler 测试"""

import tempfile
import unittest
from pathlib import Path

from eflycode.core.hooks.aggregator import HookAggregator
from eflycode.core.hooks.event_handler import HookEventHandler
from eflycode.core.hooks.planner import HookPlanner
from eflycode.core.hooks.registry import HookRegistry
from eflycode.core.hooks.runner import HookRunner
from eflycode.core.hooks.types import CommandHook, HookEventName
from eflycode.core.llm.protocol import LLMRequest, Message, ToolDefinition, ToolFunction, ToolFunctionParameters


class TestHookEventHandler(unittest.TestCase):
    """HookEventHandler 测试"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.workspace_dir = Path(self.temp_dir)
        self.registry = HookRegistry()
        self.runner = HookRunner(workspace_dir=self.workspace_dir)
        self.planner = HookPlanner()
        self.aggregator = HookAggregator()
        self.event_handler = HookEventHandler(
            registry=self.registry,
            runner=self.runner,
            planner=self.planner,
            aggregator=self.aggregator,
        )

    def tearDown(self):
        """清理测试环境"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_handle_session_start(self):
        """测试处理会话开始事件"""
        result = self.event_handler.handle_session_start("test_session", self.workspace_dir)
        self.assertIsNotNone(result)
        self.assertTrue(result.continue_)

    def test_handle_before_agent(self):
        """测试处理 BeforeAgent 事件"""
        result = self.event_handler.handle_before_agent(
            "test input", "test_session", self.workspace_dir
        )
        self.assertIsNotNone(result)

    def test_handle_after_agent(self):
        """测试处理 AfterAgent 事件"""
        result = self.event_handler.handle_after_agent(
            "test input", "test result", "test_session", self.workspace_dir
        )
        self.assertIsNotNone(result)

    def test_handle_session_end(self):
        """测试处理会话结束事件"""
        result = self.event_handler.handle_session_end("test_session", self.workspace_dir)
        self.assertIsNotNone(result)

    def test_handle_before_model(self):
        """测试处理 BeforeModel 事件"""
        request = LLMRequest(
            model="test",
            messages=[Message(role="user", content="test")],
        )
        result, modified_request = self.event_handler.handle_before_model(
            request, "test_session", self.workspace_dir
        )
        self.assertIsNotNone(result)
        # 如果没有 hook 修改，modified_request 应该为 None
        self.assertIsNone(modified_request)

    def test_handle_after_model(self):
        """测试处理 AfterModel 事件"""
        request = LLMRequest(
            model="test",
            messages=[Message(role="user", content="test")],
        )
        from eflycode.core.llm.protocol import ChatCompletion

        response = ChatCompletion(
            id="test",
            object="chat.completion",
            created=0,
            model="test",
            message=Message(role="assistant", content="response"),
        )
        result = self.event_handler.handle_after_model(
            request, response, "test_session", self.workspace_dir
        )
        self.assertIsNotNone(result)

    def test_handle_before_tool_selection(self):
        """测试处理 BeforeToolSelection 事件"""
        tools = [
            ToolDefinition(
                type="function",
                function=ToolFunction(
                    name="test_tool",
                    description="Test tool",
                    parameters=ToolFunctionParameters(),
                ),
            )
        ]
        result, modified_tools = self.event_handler.handle_before_tool_selection(
            tools, "test_session", self.workspace_dir
        )
        self.assertIsNotNone(result)
        self.assertEqual(len(modified_tools), 1)

    def test_handle_before_tool(self):
        """测试处理 BeforeTool 事件"""
        hook = CommandHook(name="test", command="echo '{\"decision\": \"allow\"}'")
        self.registry.register_hook(HookEventName.BEFORE_TOOL, hook)
        result = self.event_handler.handle_before_tool(
            "test_tool", {"arg": "value"}, "test_session", self.workspace_dir
        )
        self.assertIsNotNone(result)

    def test_handle_after_tool(self):
        """测试处理 AfterTool 事件"""
        hook = CommandHook(name="test", command="echo test")
        self.registry.register_hook(HookEventName.AFTER_TOOL, hook)
        result = self.event_handler.handle_after_tool(
            "test_tool", {"arg": "value"}, "result", "test_session", self.workspace_dir
        )
        self.assertIsNotNone(result)

    def test_handle_pre_compress(self):
        """测试处理 PreCompress 事件"""
        result = self.event_handler.handle_pre_compress("test_session", self.workspace_dir)
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()

