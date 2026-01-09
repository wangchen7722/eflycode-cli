"""HookSystem 测试"""

import tempfile
import unittest
from pathlib import Path

from eflycode.core.hooks.system import HookSystem
from eflycode.core.hooks.types import CommandHook, HookEventName


class TestHookSystem(unittest.TestCase):
    """HookSystem 测试"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.workspace_dir = Path(self.temp_dir)
        self.hook_system = HookSystem(workspace_dir=self.workspace_dir)

    def tearDown(self):
        """清理测试环境"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_register_hook(self):
        """测试注册 hook"""
        hook = CommandHook(name="test", command="echo test")
        self.hook_system.register_hook(HookEventName.BEFORE_TOOL, hook)
        self.assertTrue(
            self.hook_system.registry.has_hooks(HookEventName.BEFORE_TOOL)
        )

    def test_is_enabled(self):
        """测试启用状态"""
        self.assertTrue(self.hook_system.is_enabled())
        self.hook_system.set_enabled(False)
        self.assertFalse(self.hook_system.is_enabled())

    def test_fire_session_start_event(self):
        """测试触发会话开始事件"""
        result = self.hook_system.fire_session_start_event("test_session")
        self.assertIsNotNone(result)

    def test_fire_before_agent_event(self):
        """测试触发 BeforeAgent 事件"""
        result = self.hook_system.fire_before_agent_event(
            "test input", "test_session"
        )
        self.assertIsNotNone(result)

    def test_fire_after_agent_event(self):
        """测试触发 AfterAgent 事件"""
        result = self.hook_system.fire_after_agent_event(
            "test input", "test result", "test_session"
        )
        self.assertIsNotNone(result)

    def test_fire_session_end_event(self):
        """测试触发会话结束事件"""
        result = self.hook_system.fire_session_end_event("test_session")
        self.assertIsNotNone(result)

    def test_fire_before_tool_event(self):
        """测试触发 BeforeTool 事件"""
        hook = CommandHook(name="test", command="echo test")
        self.hook_system.register_hook(HookEventName.BEFORE_TOOL, hook)
        result = self.hook_system.fire_before_tool_event(
            "test_tool", {"arg": "value"}, "test_session"
        )
        self.assertIsNotNone(result)

    def test_fire_after_tool_event(self):
        """测试触发 AfterTool 事件"""
        hook = CommandHook(name="test", command="echo test")
        self.hook_system.register_hook(HookEventName.AFTER_TOOL, hook)
        result = self.hook_system.fire_after_tool_event(
            "test_tool", {"arg": "value"}, "result", "test_session"
        )
        self.assertIsNotNone(result)

    def test_fire_pre_compress_event(self):
        """测试触发 PreCompress 事件"""
        result = self.hook_system.fire_pre_compress_event("test_session")
        self.assertIsNotNone(result)

    def test_disabled_system_returns_empty_results(self):
        """测试禁用系统时返回空结果"""
        self.hook_system.set_enabled(False)
        result = self.hook_system.fire_before_agent_event(
            "test input", "test_session"
        )
        self.assertIsNone(result.decision)
        self.assertTrue(result.continue_)
        self.assertEqual(len(result.system_messages), 0)


if __name__ == "__main__":
    unittest.main()

